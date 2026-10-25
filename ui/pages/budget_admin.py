"""예산 관리 (관리자) — 분석가의 리스크 상향 신청 결재.

requests.decide() 를 호출하면 상태가 바뀌고, 승인/조정이면
db.set_user_override() 가 (사용자 × 데이터셋) 오버라이드를 만들어
해당 분석가의 다음 콘솔 진입부터 새 리스크 레벨이 적용된다.
"""
from __future__ import annotations

import streamlit as st

from ui import db, design, requests

STATUS = {"pending": "대기", "approved": "승인", "partial": "조정", "rejected": "거절"}
TAG = {"pending": "p", "approved": "a", "partial": "a", "rejected": "r"}


def render() -> None:
    design.inject()
    st.markdown(design.topbar("예산 관리", "Admin"), unsafe_allow_html=True)
    st.markdown(design.page_head("예산 관리",
                                 "분석가의 리스크 상향 신청을 검토 · 승인 / 조정 / 거절"),
                unsafe_allow_html=True)

    admin = st.session_state.get("username") or "admin"
    s = requests.stats()

    c = st.columns(4)
    for col, (key, label) in zip(c, [("pending", "대기"), ("approved", "승인"),
                                     ("partial", "조정"), ("rejected", "거절")]):
        with col:
            st.markdown(
                f'<div class="card" style="margin-bottom:6px;padding:10px 12px">'
                f'<div class="dim" style="font-size:9px">{label}</div>'
                f'<div class="mono" style="font-size:18px;font-weight:600;color:#101828">'
                f'{s.get(key, 0)}</div></div>', unsafe_allow_html=True)

    filt = st.radio("상태", ["전체", "pending", "approved", "partial", "rejected"],
                    horizontal=True, format_func=lambda k: STATUS.get(k, k) if k != "전체" else "전체",
                    label_visibility="collapsed", key="adm_filter")

    rows = requests.list_all(status=None if filt == "전체" else filt)
    if not rows:
        st.markdown(design.empty("해당 상태의 신청이 없습니다"), unsafe_allow_html=True)
        return

    pending = [r for r in rows if r["status"] == "pending"]
    if pending:
        st.markdown('<div class="card"><div class="rh">대기 큐 · 결재</div>',
                    unsafe_allow_html=True)
        for r in pending:
            _decide_row(r, admin)
        st.markdown("</div>", unsafe_allow_html=True)

    done = [r for r in rows if r["status"] != "pending"]
    if done:
        st.markdown('<div class="card"><div class="rh">처리 완료</div>', unsafe_allow_html=True)
        out = []
        for r in done[:30]:
            out.append(
                '<div style="display:grid;grid-template-columns:72px 88px 70px 1fr 88px 52px;'
                'gap:8px;align-items:center;border-bottom:1px solid #eef1f5;padding:6px 0;font-size:9.5px">'
                f'<span class="mono dim" style="font-size:8px">{_t(r.get("created_at"))}</span>'
                f'<span class="mono" style="font-size:9px">{_esc(r.get("username"))}</span>'
                f'<span class="mono" style="font-size:9px">{r.get("db_name")}</span>'
                f'<span style="color:#5a6779">{_esc((r.get("reason") or "")[:52])}</span>'
                f'<span class="mono dim" style="font-size:8.5px">Risk {r.get("current_level")} → '
                f'{r.get("approved_level") or r.get("requested_level")}</span>'
                f'<span class="tag {TAG.get(r.get("status"), "")}" style="text-align:center">'
                f'{STATUS.get(r.get("status"), r.get("status"))}</span></div>'
            )
        st.markdown("".join(out), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def _decide_row(r: dict, admin: str) -> None:
    """신청 1건 — 승인 레벨 선택 + 사유 + 승인/조정/거절."""
    rid = int(r["id"])
    cur_lv, req_lv = int(r["current_level"]), int(r["requested_level"])
    options = [lv for lv in sorted(db.RISK_TO_EPSILON) if lv > cur_lv]

    st.markdown('<div class="reqdiv"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="row between"><div class="grow">'
        f'<div style="font-size:10.5px;font-weight:600;color:#101828">'
        f'{_esc(r["username"])} · {r["db_name"]} · Risk {cur_lv} → {req_lv}</div>'
        f'<div class="dim" style="font-size:9px;margin-top:2px">'
        f'{_esc(r.get("reason") or "")}</div></div>'
        f'<span class="mono dim" style="font-size:8px">#{rid} · {_t(r.get("created_at"))}</span></div>',
        unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1.1, 1.6, 0.75, 0.75], vertical_alignment="bottom")
    with c1:
        lv = st.selectbox("승인 레벨", options, index=options.index(req_lv) if req_lv in options else 0,
                          format_func=lambda x: f"Risk {x} ({db.RISK_TO_EPSILON[x]:.1f} ε)",
                          key=f"lv_{rid}")
    with c2:
        note = st.text_input("메모", key=f"note_{rid}", placeholder="승인 사유·조정 근거 (선택)")
    with c3:
        if st.button("승인", key=f"ok_{rid}", type="primary", use_container_width=True):
            _apply(rid, admin, lv, note, req_lv)
    with c4:
        if st.button("거절", key=f"no_{rid}", use_container_width=True):
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
            st.toast(f"신청 #{rid} 을 Risk {lv} 로 {'승인' if status == 'approved' else '조정 승인'}했습니다.")
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
