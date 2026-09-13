import streamlit as st
from ui import db, state, theme


HERO_HTML = """
<div class="dp-login-hero">
  <div style="display:flex;align-items:center;gap:10px;">
    <div class="dp-brand-mark" style="width:38px;height:38px;font-size:18px;">ε</div>
    <div>
      <div style="font-weight:700;font-size:16px;color:#0f172a;">DP Agent</div>
      <div style="font-size:11px;color:#64748b;letter-spacing:0.02em;">
        Differential Privacy Workspace
      </div>
    </div>
  </div>
  <h2>안전한 경계 안에서<br/>데이터에게 질문하기.</h2>
  <p>
    분석가는 원본 데이터에 직접 접근하지 않고, LLM 에이전트가 작성·실행한
    코드의 결과만 차분 프라이버시 보호 아래 받아봅니다.
  </p>

  <div class="bullet">
    <div class="bullet-dot">1</div>
    <div class="bullet-text">
      <b>자연어 질의</b><br/>
      <span>스키마만을 참고해 에이전트가 pandas 코드를 스트리밍 생성합니다.</span>
    </div>
  </div>
  <div class="bullet">
    <div class="bullet-dot">2</div>
    <div class="bullet-text">
      <b>ε 예산 원장</b><br/>
      <span>질의마다 소비된 ε을 개인별 상한과 함께 실시간 추적합니다.</span>
    </div>
  </div>
  <div class="bullet">
    <div class="bullet-dot">3</div>
    <div class="bullet-text">
      <b>관리자 결재</b><br/>
      <span>예산이 부족할 때는 사유와 함께 증액을 요청하고 승인받습니다.</span>
    </div>
  </div>
</div>
"""


def render_login():
    theme.inject_global_css()

    st.markdown("<div style='height: 3vh;'></div>", unsafe_allow_html=True)

    left, right = st.columns([1.05, 1], gap="large")

    # 왼쪽: 순수 HTML hero (Streamlit 위젯 없음)
    with left:
        st.markdown(HERO_HTML, unsafe_allow_html=True)

    # 오른쪽: HTML <div> 로 감싸지 말고, st.container(border=True) 를 카드로 쓴다.
    with right:
        with st.container(border=True, key="login_card"):
            st.markdown(
                # '<div class="dp-eyebrow">Sign in</div>'
                '<h3 style="margin:2px 0 0 0;">Console 접속</h3>'
                '<p style="color:#64748b;font-size:13px;margin:4px 0 0 0;">',
                # '데모 계정 · <code>analyst / demo1234</code> · '
                # '<code>admin / admin1234</code></p>',
                unsafe_allow_html=True,
            )

            tab_in, tab_up = st.tabs(["로그인", "회원가입"])

            with tab_in:
                with st.form("login", clear_on_submit=False, border=False):
                    u = st.text_input("아이디", value="analyst")
                    p = st.text_input("비밀번호", type="password",
                                      placeholder="8자 이상")
                    submitted = st.form_submit_button(
                        "로그인",
                        use_container_width=True,
                        type="primary",
                    )
                    if submitted:
                        user = db.verify(u, p)
                        if user:
                            st.session_state.authenticated = True
                            st.session_state.username = user["username"]
                            st.session_state.is_admin = bool(user["is_admin"])
                            st.session_state.eps_cap = float(user["eps_cap"])
                            st.session_state.spent = 0.0
                            state.log("auth", f"{user['username']} 로그인")
                            st.rerun()
                        else:
                            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

            with tab_up:
                with st.form("signup", clear_on_submit=False, border=False):
                    u = st.text_input("아이디 ", placeholder="영문/숫자 조합")
                    p1 = st.text_input("비밀번호 ", type="password",
                                       help="8자 이상")
                    p2 = st.text_input("비밀번호 확인", type="password")
                    # is_adm = st.checkbox(
                    #     "관리자로 가입 (데모용)",
                    #     help="발표회 데모에서 관리자/분석가 시나리오를 시연하기 위한 옵션입니다.",
                    # )
                    if st.form_submit_button("가입",
                                             use_container_width=True):
                        if p1 != p2:
                            st.error("비밀번호가 일치하지 않습니다.")
                        else:
                            ok, msg = db.create_user(u, p1)
                            (st.success if ok else st.error)(msg)

    st.markdown(
        '<div style="text-align:center;color:#94a3b8;font-size:12px;'
        'margin-top:32px;">'
        '© 2026 DP Agent · AILS-NTUA / DataBench pipeline · '
        'demonstration build'
        '</div>',
        unsafe_allow_html=True,
    )