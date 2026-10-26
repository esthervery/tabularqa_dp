"""예산 관리 (관리자) — 분석가의 Utility 상향 신청 결재.

Renders (위→아래):
    1) 페이지 제목
    2) 요약 줄 : 대기 · 승인(조정 포함) · 거절 · 전체 건수
    3) 상태 필터 : 대기 / 승인됨 / 거절됨 / 전체  (st.segmented_control, 기본 '대기')
    4) 신청 표 : 시각 · 계정 · 데이터셋 · 신청 내용 · 상태 · [자세히 보기]  + 페이지 번호
    5) 상세 대화상자 : 신청 정보 · 사유 · (대기 건) 승인 레벨 · 메모 · [거절] [승인]

requests.decide() 를 호출하면 상태가 바뀌고, 승인/조정이면
db.set_user_override() 가 (사용자 × 데이터셋) 오버라이드를 만들어
해당 분석가의 다음 콘솔 진입부터 새 레벨이 적용된다. (결재 로직은 기존과 동일)
"""
from __future__ import annotations

import html

import streamlit as st

from ui import db, design, requests

E = db.RISK_TO_EPSILON
PAGE_SIZE = 10                                    # 한 페이지 행 수 (두 줄 행이라 히스토리보다 적게)
QLOG_LIMIT = 100                                  # 상세 대화상자 질의 기록 최대 건수

TABS = {"pending": "대기", "approved": "승인됨", "rejected": "거절됨", "all": "전체"}

COLS = (1.1, 1.0, 1.3, 2.1, 0.9, 0.9)
HEAD = ("신청 시각", "계정", "데이터셋", "신청 내용", "상태", "상세")


def render() -> None:
    design.inject()
    msg = st.session_state.pop("adm_msg", None)           # 결재 직후 rerun 에서 알림
    if msg:
        st.toast(msg)

    ds = st.session_state.get("adm_ds", "전체")           # 상단 바에서 고른 값 (기본 '전체')
    scope = None if ds == "전체" else ds

    admin = st.session_state.get("username") or "admin"
    s = requests.stats(db_name=scope)
    n_ok = s["approved"] + s["partial"]
    n_all = sum(s.values())

    # ── 상태 필터 탭 (건수 표시 겸용 — 요약 줄 대체) ──
    counts = {"pending": s["pending"], "approved": n_ok,
              "rejected": s["rejected"], "all": n_all}
    tab = st.segmented_control(
        "상태", list(TABS), default="pending", required=True,
        format_func=lambda k: f"{TABS[k]} {counts[k]}",
        label_visibility="collapsed", key="adm_tab") or "pending"

    rows = [r for r in requests.list_all(db_name=scope) if _match(r, tab)]

    if not rows:
        where = "전체 데이터셋" if scope is None else ds
        st.markdown(design.empty(f"{where} · {TABS[tab]} 신청이 없습니다"), unsafe_allow_html=True)
        return

    # ── 표 + 페이지 번호 ──
    slot = st.container()
    start, end = design.pager(len(rows), PAGE_SIZE, "adm_page", reset_on=(scope, tab))
    with slot:
        _table(rows[start:end])

    # ── 상세 대화상자 ──
    sel = st.session_state.get("adm_sel")
    if sel is not None:
        row = next((r for r in rows if int(r["id"]) == int(sel)), None)
        if row is None:                                   # 필터·범위가 바뀌어 사라진 경우
            st.session_state["adm_sel"] = None
        else:
            _detail(row, admin)


def _match(r: dict, tab: str) -> bool:
    s = r["status"]
    return (tab == "all"
            or (tab == "pending" and s == "pending")
            or (tab == "approved" and s in ("approved", "partial"))
            or (tab == "rejected" and s == "rejected"))


# ── 표 (히스토리 표와 같은 key 패턴 → 같은 CSS) ─────────────
def _table(rows: list[dict]) -> None:
    with st.container(key="htable"):
        with st.container(key="hhead"):
            h = st.columns(COLS, vertical_alignment="center")
            for i, t in enumerate(HEAD):
                h[i].html(f'<div class="hcol">{t}</div>')

        for r in rows:
            cur, req = int(r["current_level"]), int(r["requested_level"])
            # sub = f"ε {E[cur]:.0f} → {E[req]:.0f}"
            # if r["status"] == "partial" and r.get("approved_level"):
            #     sub += f" · Utility {r['approved_level']} 로 조정"
            with st.container(key=f"hrow_{r['id']}"):
                c = st.columns(COLS, vertical_alignment="center")
                c[0].html(f'<div class="hcell tm">{_t(r.get("created_at"))}</div>')
                c[1].html(f'<div class="hcell mono">{_e(r.get("username"))}</div>')
                c[2].html(f'<div class="hcell mono">{_e(r.get("db_name"))}</div>')
                c[3].html(f'<div class="hcell"><b>Utility {cur} → {req}</b>')
                          # f'<span class="hs">{sub}</span></div>')
                c[4].html(design.status_pill(r.get("status")))
                if c[5].button("자세히 보기", key=f"det_{r['id']}", type="tertiary"):
                    st.session_state["adm_sel"] = int(r["id"])
                    st.rerun()


# ── 상세 대화상자 ──────────────────────────────────────────
def _close() -> None:
    """X / ESC / 바깥 클릭으로 닫아도 선택 상태를 지운다."""
    st.session_state["adm_sel"] = None


@st.dialog("신청 상세", width="medium", on_dismiss=_close)
def _detail(r: dict, admin: str) -> None:
    rid = int(r["id"])
    user, ds = r["username"], r["db_name"]
    cur, req = int(r["current_level"]), int(r["requested_level"])
    spent = db.spent_epsilon(user, ds)
    n_all = db.count_queries(user, ds, only_ok=False)
    n_bad = n_all - db.count_queries(user, ds, only_ok=True)

    # ── 요약 (카드 없이 정의 목록 한 덩어리) ──
    st.html(
        f'<div class="rqtop">{design.status_pill(r["status"])}'
        f'<span class="tm">{_t(r.get("created_at"))} 신청</span></div>'
        '<dl class="rqdl">'
        f'<dt>신청자</dt><dd><b>{_e(user)}</b><span class="dot">·</span>'
        f'<span class="mono">{_e(ds)}</span></dd>'
        f'<dt>정책 변경</dt><dd><b>Utility {cur}</b><span class="arr">→</span>'
        f'<b class="up">Utility {req}</b>'
        f'<span class="sub">ε {E[cur]:.0f} → {E[req]:.0f}</span></dd>'
        f'<dt>사용한 ε</dt><dd><b class="mono">{spent:.2f}</b>'
        f'<span class="sub">질의 {n_all}건 · 차단 {n_bad}건</span></dd>'
        f'<dt>신청 사유</dt><dd class="why">{_e(r.get("reason") or "-")}</dd>'
        '</dl>')

    # ── 신청자의 질의 기록 (이 영역만 스크롤) ──
    _query_log(user, ds, n_all)

    # ── 결재 / 처리 결과 ──
    if r["status"] == "pending":
        options = [lv for lv in sorted(E) if lv > cur]
        c1, c2 = st.columns([1, 1.6], vertical_alignment="bottom")
        lv = c1.selectbox("승인 레벨", options,
                          index=options.index(req) if req in options else len(options) - 1,
                          format_func=lambda x: f"Utility {x} (ε {E[x]:.0f})",
                          key=f"lv_{rid}")
        note = c2.text_input("메모", key=f"note_{rid}", placeholder="승인 사유 · 조정 근거 (선택)")
        with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
            if st.button("거절", key=f"no_{rid}"):
                _apply(r, admin, None, note, reject=True)
            label = "승인" if lv == req else f"Utility {lv} 로 조정 승인"
            if st.button(label, key=f"ok_{rid}", type="primary"):
                _apply(r, admin, lv, note)
    else:
        ap = r.get("approved_level")
        result = {"approved": f"Utility {ap} 승인", "partial": f"Utility {ap} 로 조정 승인",
                  "rejected": "거절"}.get(r["status"], r["status"])
        st.html(
            '<dl class="rqdl">'
            f'<dt>처리 결과</dt><dd><b>{result}</b>'
            f'<span class="sub">{_e(r.get("reviewer") or "-")} · {_t(r.get("reviewed_at"))}</span></dd>'
            f'<dt>관리자 메모</dt><dd class="why">{_e(r.get("admin_note") or "-")}</dd>'
            '</dl>')


def _query_log(user: str, ds: str, total: int) -> None:
    rows = db.list_queries(user, ds, limit=QLOG_LIMIT)
    more = f"최근 {len(rows)}건" + (f" / 전체 {total}건" if total > len(rows) else "")
    st.html(f'<div class="rqsec">질의 기록<span>{more}</span></div>')
    if not rows:
        st.html('<div class="rqnone">이 데이터셋에서 질의한 기록이 없습니다</div>')
        return
    body = ""
    for q in rows:
        ok = bool(q.get("ok"))
        ans = (q.get("answer") or "").strip()
        body += (
            "<tr>"
            f'<td class="tm">{_t(q.get("asked_at"))}</td>'
            f'<td class="q">{_e(q.get("question") or "")}</td>'
            f'<td>{design.pill("성공", "success") if ok else design.pill("차단", "danger")}</td>'
            f'<td class="mono">{_e(_short(ans)) if ok and ans else "–"}</td>'
            "</tr>")
    with st.container(height=240, key="rqlog"):          # 고정 높이 → 이 안에서만 스크롤
        st.html('<table class="rqtbl"><thead><tr><th>시각</th><th>질의</th>'
                f'<th>결과</th><th>응답</th></tr></thead><tbody>{body}</tbody></table>')


def _apply(r: dict, admin: str, lv: int | None, note: str, reject: bool = False) -> None:
    rid, req_lv = int(r["id"]), int(r["requested_level"])
    who = f"{r['username']} · {r['db_name']}"
    try:
        if reject:
            requests.decide(rid, reviewer=admin, status="rejected", note=note)
            msg = f"{who} 신청을 거절했습니다."
        else:
            status = "approved" if lv == req_lv else "partial"
            requests.decide(rid, reviewer=admin, status=status, approved_level=lv, note=note)
            msg = (f"{who} 신청을 Utility {lv} 로 "
                   f"{'승인' if status == 'approved' else '조정 승인'}했습니다.")
    except Exception as e:
        st.error(f"결재를 처리하지 못했습니다 ({type(e).__name__}: {e})")
        return
    st.session_state["adm_sel"] = None
    st.session_state["adm_msg"] = msg
    st.rerun()


def _apply(rid: int, admin: str, lv: int | None, note: str,
           req_lv: int, reject: bool = False) -> None:
    try:
        if reject:
            requests.decide(rid, reviewer=admin, status="rejected", note=note)
            msg = f"신청 #{rid} 을 거절했습니다."
        else:
            status = "approved" if lv == req_lv else "partial"
            requests.decide(rid, reviewer=admin, status=status, approved_level=lv, note=note)
            msg = (f"신청 #{rid} 을 Utility {lv} 로 "
                   f"{'승인' if status == 'approved' else '조정 승인'}했습니다.")
    except Exception as e:
        st.error(f"결재를 처리하지 못했습니다 ({type(e).__name__}: {e})")
        return
    st.session_state["adm_sel"] = None
    st.session_state["adm_msg"] = msg
    st.rerun()                                            # 대화상자 닫기 + 표·요약 갱신


# ── 헬퍼 ──────────────────────────────────────────────
def _t(v) -> str:
    return str(v).replace("T", " ")[5:16] if v else "-"


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _short(s, n: int = 28) -> str:
    v = " ".join(design.fmt_answer(s).split())
    return v if len(v) <= n else v[: n - 1] + "…"


# Streamlit 은 페이지 파일을 '스크립트'로 실행한다 — render() 를 직접 호출해야 한다.
render()