"""예산 관리 (관리자) — 분석가의 리스크 상향 신청 결재.

Renders (위→아래):
    1) 페이지 제목
    2) 상태별 통계 카드 4개 (대기/승인/조정/거절)
    3) 상태 필터 (세그먼트)
    4) 대기 큐 카드 : 신청 1건마다 사유 + 승인 레벨 · 메모 · [승인] [거절]
    5) 처리 완료 카드 : 표 형태 + 상태 뱃지

requests.decide() 를 호출하면 상태가 바뀌고, 승인/조정이면
db.set_user_override() 가 (사용자 × 데이터셋) 오버라이드를 만들어
해당 분석가의 다음 콘솔 진입부터 새 리스크 레벨이 적용된다.
(로직은 demo 브랜치 원본과 동일 — 레이아웃·스타일만 변경)
"""
from __future__ import annotations

import streamlit as st

from ui import db, design, requests

STATUS = {"pending": "대기", "approved": "승인", "partial": "조정", "rejected": "거절"}


def render() -> None:
    design.inject()
    ds_now = st.session_state.get("adm_ds", "전체")
    st.markdown(design.page_hero(
        "예산 관리",
        f"분석가의 Utility 상향 신청을 검토하고 승인 · 조정 · 거절합니다 — "
        f"대상: {'전체 데이터셋' if ds_now == '전체' else ds_now}"),
        unsafe_allow_html=True)


    admin = st.session_state.get("username") or "admin"
    ds = st.session_state.get("adm_ds", "전체")          # 상단 바에서 고른 값 (기본 '전체')
    scope = None if ds == "전체" else ds
    s = requests.stats(db_name=scope)

    c = st.columns(4)
    for col, (key, label, tone) in zip(c, [("pending", "대기", "p"), ("approved", "승인", "a"),
                                           ("partial", "조정", "c"), ("rejected", "거절", "r")]):
        with col:
            st.markdown(design.stat(label, s.get(key, 0), tone), unsafe_allow_html=True)

    filt = st.radio("상태", ["전체", "pending", "approved", "partial", "rejected"],
                    horizontal=True,
                    format_func=lambda k: STATUS.get(k, k) if k != "전체" else "전체",
                    label_visibility="collapsed", key="adm_filter")

    rows = requests.list_all(status=None if filt == "전체" else filt, db_name=scope)

    if not rows:
        where = "전체 데이터셋" if scope is None else scope
        st.markdown(design.empty(f"{where} · 해당 상태의 신청이 없습니다"), unsafe_allow_html=True)
        return


    pending = [r for r in rows if r["status"] == "pending"]
    if pending:
        with st.container(border=True, key="card_queue"):
            st.markdown(design.card_head("대기 큐 · 결재", f"{len(pending)}건 대기 중"),
                        unsafe_allow_html=True)
            for i, r in enumerate(pending):
                if i:
                    st.markdown('<div class="reqdiv"></div>', unsafe_allow_html=True)
                _decide_row(r, admin)

    done = [r for r in rows if r["status"] != "pending"]
    if done:
        with st.container(border=True, key="card_done"):
            st.markdown(design.card_head("처리 완료", f"최근 {min(len(done), 30)}건"),
                        unsafe_allow_html=True)
            grid = "grid-template-columns:96px 100px 120px 1fr 110px 64px"
            out = [f'<div class="trow head" style="{grid}"><span>신청</span><span>사용자</span>'
                   '<span>데이터셋</span><span>사유</span><span>레벨</span>'
                   '<span class="r">상태</span></div>']
            for r in done[:30]:
                out.append(
                    f'<div class="trow" style="{grid}">'
                    f'<span class="t">{_t(r.get("created_at"))}</span>'
                    f'<span class="m">{_esc(r.get("username"))}</span>'
                    f'<span class="m">{r.get("db_name")}</span>'
                    f'<span class="x">{_esc(r.get("reason") or "")}</span>'
                    f'<span class="m">Utility {r.get("current_level")} → '
                    f'{r.get("approved_level") or r.get("requested_level")}</span>'
                    f'<span class="r">{design.status_pill(r.get("status"))}</span></div>'
                )
            st.markdown("".join(out), unsafe_allow_html=True)


def _decide_row(r: dict, admin: str) -> None:
    """신청 1건 — 승인 레벨 선택 + 메모 + 승인/거절."""
    rid = int(r["id"])
    cur_lv, req_lv = int(r["current_level"]), int(r["requested_level"])
    options = [lv for lv in sorted(db.RISK_TO_EPSILON) if lv > cur_lv]

    req_badge = design.pill("요청 ε %.0f" % db.RISK_TO_EPSILON[req_lv], "warning")
    st.markdown(
        '<div class="decide"><div class="grow">'
        f'<div class="h">{_esc(r["username"])} · <code>{r["db_name"]}</code> · '
        f'Utility {cur_lv} → {req_lv} {req_badge}</div>'
        f'<div class="why">{_esc(r.get("reason") or "")}</div></div>'
        f'<span class="id">#{rid} · {_t(r.get("created_at"))}</span></div>',
        unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1.2, 1.8, 0.7, 0.7], vertical_alignment="bottom")
    with c1:
        lv = st.selectbox("승인 레벨", options,
                          index=options.index(req_lv) if req_lv in options else 0,
                          format_func=lambda x: f"Utility {x} ({db.RISK_TO_EPSILON[x]:.0f} ε)",
                          key=f"lv_{rid}")
    with c2:
        note = st.text_input("메모", key=f"note_{rid}", placeholder="승인 사유·조정 근거 (선택)")
    with c3:
        if st.button("✓ 승인", key=f"ok_{rid}", type="primary", use_container_width=True):
            _apply(rid, admin, lv, note, req_lv)
    with c4:
        if st.button("✕ 거절", key=f"no_{rid}", use_container_width=True):
            _apply(rid, admin, None, note, req_lv, reject=True)


def _apply(rid: int, admin: str, lv: int | None, note: str,
           req_lv: int, reject: bool = False) -> None:
    try:
        if reject:
            requests.decide(rid, reviewer=admin, status="rejected", note=note)
            st.toast(f"신청 #{rid} 을 거절했습니다.")
        else:
            status = "approved" if lv == req_lv else "partial"
            requests.decide(rid, reviewer=admin, status=status,
                            approved_level=lv, note=note)
            st.toast(f"신청 #{rid} 을 Utility {lv} 로 "
                     f"{'승인' if status == 'approved' else '조정 승인'}했습니다.")
        st.rerun()
    except Exception as e:
        st.error(f"결재를 처리하지 못했습니다 ({type(e).__name__}: {e})")


def _t(v) -> str:
    if not v:
        return "-"
    return str(v).replace("T", " ")[5:16]


def _esc(s) -> str:
    return str(s).replace("<", "&lt;").replace(">", "&gt;")


# Streamlit 은 페이지 파일을 '스크립트'로 실행한다 — render() 를 직접 호출해야 한다.
render()