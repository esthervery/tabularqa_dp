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
    st.markdown(design.page_head("채팅 히스토리",
                                 "데이터셋별 질의·응답 기록 — 감사 추적용으로 삭제되지 않습니다"),
                unsafe_allow_html=True)

    cur = st.session_state.get("db_name")
    if cur not in ORD:
        cur = ORD[0]

    pick = cur   # 데이터셋은 상단 바에서 고른다
    limit = st.selectbox("표시 개수", [20, 50, 100, 200], index=1, key="hist_limit", width=160)


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

    # 기록마다 st.html 로 따로 그린다 (st.markdown + 빈 줄 → 태그 노출 버그 방지)
    label = fields.SPECS.get(pick, {}).get("measure", {}).get("label", "결과")
    for r in rows:
        st.html(design.history_card(
            _t(r.get("asked_at")),
            r.get("question") or "",
            r.get("code") or "",
            (r.get("answer") or "").strip(),
            ok=bool(r.get("ok")),
            eps=float(r.get("eps_spent") or 0.0),
            label=label,
        ))


def _t(v: str | None) -> str:
    if not v:
        return "-"
    return str(v).replace("T", " ")[5:16]


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# Streamlit 은 페이지 파일을 '스크립트'로 실행한다 — render() 를 직접 호출해야 한다.
render()