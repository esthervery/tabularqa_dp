"""로그인 · 회원가입 화면.

app.py 에서 st.session_state.authenticated 가 False 일 때만 호출된다.
성공 시 세션 상태를 채우고 st.rerun() 을 발생시켜 메인 앱으로 이동.
"""
import streamlit as st
from ui import db, state


def render_login() -> None:
    """
    Renders (위→아래):
      - 좌측 컬럼 : 서비스 소개 텍스트 (제목/설명/불릿 3개)
      - 우측 컬럼 : 로그인/회원가입 탭 폼 (bordered container)
      - 하단      : 저작권/빌드 표시 caption
    """
    left, right = st.columns([1.05, 1], gap="large")

    with left:
        _render_intro()

    with right:
        with st.container(border=True):
            st.subheader("Console 접속")

            tab_in, tab_up = st.tabs(["로그인", "회원가입"])
            with tab_in:
                _render_login_form()
            with tab_up:
                _render_signup_form()

    st.caption(
        "© 2026 DP Agent · AILS-NTUA / DataBench pipeline · demonstration build"
    )


def _render_intro() -> None:
    """좌측 소개 컬럼. 서비스 컨셉 3문장 + 특징 3개."""
    st.title("안전한 경계 안에서\n데이터에게 질문하기")
    st.write(
        "분석가는 원본 데이터에 직접 접근하지 않고, "
        "LLM 에이전트가 작성·실행한 코드의 결과만 "
        "차분 프라이버시 보호 아래 받아봅니다."
    )
    st.markdown(
        "1. **자연어 질의** — 스키마만 참고해 pandas 코드를 스트리밍 생성  \n"
        "2. **ε 예산 원장** — 질의마다 소비된 ε 을 개인별 상한과 함께 추적  \n"
        "3. **관리자 결재** — 예산 부족 시 사유와 함께 증액을 요청·승인"
    )


def _render_login_form() -> None:
    """로그인 탭 폼. 성공 시 세션 채우고 rerun."""
    with st.form("login", clear_on_submit=False, border=False):
        u = st.text_input("아이디", value="analyst")
        p = st.text_input("비밀번호", type="password", placeholder="8자 이상")
        submitted = st.form_submit_button(
            "로그인", type="primary", use_container_width=True,
        )
        if not submitted:
            return

        user = db.verify(u, p)
        if not user:
            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
            return

        st.session_state.authenticated = True
        st.session_state.username      = user["username"]
        st.session_state.is_admin      = bool(user["is_admin"])
        st.session_state.eps_cap       = float(user["eps_cap"])
        st.session_state.spent         = 0.0
        state.log("auth", f"{user['username']} 로그인")
        st.rerun()


def _render_signup_form() -> None:
    """회원가입 탭 폼."""
    with st.form("signup", clear_on_submit=False, border=False):
        u  = st.text_input("아이디 ", placeholder="영문/숫자 조합")
        p1 = st.text_input("비밀번호 ", type="password", help="8자 이상")
        p2 = st.text_input("비밀번호 확인", type="password")

        if not st.form_submit_button("가입", use_container_width=True):
            return

        if p1 != p2:
            st.error("비밀번호가 일치하지 않습니다.")
            return

        ok, msg = db.create_user(u, p1)
        (st.success if ok else st.error)(msg)
