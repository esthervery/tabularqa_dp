"""채팅 히스토리 — (계정 × 데이터셋) 질의·응답 기록.

단일 출처는 SQLite 의 query_log 다. 세션 상태(messages)는 '지금 화면의 대화'일 뿐이고,
데이터셋을 바꾸거나 로그아웃해도 남는 기록은 여기서 본다.
"""
from __future__ import annotations

import streamlit as st

from ui import db, design, fields

ORD = [k for k, v in fields.SPECS.items() if v.get("enabled")]
TL = {k: fields.SPECS[k]["title"] for k in ORD}
EPS = 0.1


def render() -> None:
    design.inject()
    is_admin = bool(st.session_state.get("is_admin"))
    st.markdown(design.topbar("채팅 히스토리", "Admin" if is_admin else "Workspace"),
                unsafe_allow_html=True)
    st.markdown(design.page_head("채팅 히스토리",
                                 "데이터셋별 질의·응답 기록 — 감사 추적용으로 삭제되지 않습니다"),
                unsafe_allow_html=True)

    cur = st.session_state.get("db_name")
    if cur not in ORD:
        cur = ORD[0]

    left, right = st.columns([1.6, 2], vertical_alignment="center")
    with left:
        pick = st.selectbox("데이터셋", ORD, index=ORD.index(cur),
                            format_func=lambda k: f"{TL.get(k, k)}  ·  {k}", key="hist_ds")
    with right:
        limit = st.selectbox("표시 개수", [20, 50, 100, 200], index=1, key="hist_limit")

    user = st.session_state.get("username") or "analyst"
    rows = db.list_queries(user, pick, limit=int(limit))
    spent = db.spent_epsilon(user, pick)
    ok_n = db.count_queries(user, pick, only_ok=True)
    fail_n = db.count_queries(user, pick, only_ok=False) - ok_n

    st.markdown(design.line([
        ("질의", f"{ok_n}건"),
        ("차단·실패", f"{fail_n}건"),
        ("누적 ε", f"{spent:.2f}"),
        ("데이터셋", pick),
    ]), unsafe_allow_html=True)
    st.write("")

    if not rows:
        st.markdown(design.empty("이 데이터셋에 대한 기록이 없습니다"), unsafe_allow_html=True)
        return

    blocks: list[str] = []
    for r in rows:
        ok = bool(r.get("ok"))
        bad = "" if ok else '<span class="tag r">차단</span>'
        eps = float(r.get("eps_spent") or 0.0)
        code = r.get("code") or ""
        ans = (r.get("answer") or "").strip()
        body = ""
        if ans:
            body += f'<div class="q" style="margin-top:4px;color:#5a6779">{_esc(ans[:400])}</div>'
        if code:
            body += f'<div class="anscode">{design._hl(code)}</div>'
        blocks.append(
            '<div class="card" style="margin-bottom:7px">'
            '<div class="row between">'
            f'<span class="mono dim" style="font-size:8px">{_t(r.get("asked_at"))}</span>'
            '<span style="display:flex;gap:5px;align-items:center">'
            f'{bad}<span class="tag">{eps:.2f} ε</span></span></div>'
            f'<div class="q" style="margin-top:5px;font-weight:600">{_esc(r.get("question") or "")}</div>'
            + body + "</div>"
        )
    st.markdown("".join(blocks), unsafe_allow_html=True)


def _t(v: str | None) -> str:
    if not v:
        return "-"
    return str(v).replace("T", " ")[5:16]


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# Streamlit 은 페이지 파일을 '스크립트'로 실행한다 — render() 를 직접 호출해야 한다.
render()