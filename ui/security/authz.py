"""관리자 권한 가드 — 페이지와 결재 동작 양쪽에서 호출한다."""
from __future__ import annotations

import streamlit as st

from ui import db


def is_admin_now() -> bool:
    if not st.session_state.get("authenticated"):
        return False
    user = st.session_state.get("username")
    return bool(user) and db.is_admin(user)


def require_admin() -> str:
    """관리자가 아니면 화면을 멈춘다. 통과하면 관리자 아이디 반환."""
    if not is_admin_now():
        print(f"[authz] denied: user={st.session_state.get('username')!r}")
        st.error("관리자만 접근할 수 있는 페이지입니다.")
        st.stop()
    return st.session_state["username"]