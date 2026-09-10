import streamlit as st
from ui import db, state


def render_login():
    st.markdown("<br>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.title("🔒 DP Agent Console")
        st.caption("차분 프라이버시로 보호되는 에이전트 기반 데이터 분석 플랫폼")

        tab_in, tab_up = st.tabs(["로그인", "회원가입"])

        with tab_in:
            with st.form("login"):
                u = st.text_input("아이디", value="analyst")
                p = st.text_input("비밀번호", type="password")
                if st.form_submit_button("로그인", use_container_width=True):
                    user = db.verify(u, p)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.username = user["username"]
                        st.session_state.is_admin = bool(user["is_admin"])
                        state.log("auth", f"{user['username']} 로그인")
                        st.rerun()
                    else:
                        st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

        with tab_up:
            with st.form("signup"):
                u = st.text_input("아이디 ")
                p1 = st.text_input("비밀번호 ", type="password",
                                   help="8자 이상")
                p2 = st.text_input("비밀번호 확인", type="password")
                if st.form_submit_button("가입", use_container_width=True):
                    if p1 != p2:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        ok, msg = db.create_user(u, p1)
                        (st.success if ok else st.error)(msg)