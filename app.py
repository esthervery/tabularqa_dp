"""Streamlit 데모 진입점.

역할별 페이지 라우팅과 사이드바 하단 고정 블록만 담당한다.
각 페이지는 ui/pages/*.py 에서 독립적으로 렌더링을 결정한다.

Renders (위→아래):
  - 로그인 안 된 상태: 사이드바 완전히 숨기고 auth.render_login() 만 보여줌
  - 로그인 후:
      · 사이드바 상단 : 각 페이지가 채우는 컨텍스트 슬롯 (nav_slot)
      · 사이드바 하단 : 역할 표시 + Log out 버튼 (고정)
      · 메인          : st.navigation 이 선택한 페이지의 body
"""
import streamlit as st
from ui import auth, db, state


# 스키마 준비 + 세션 상태 확인. set_page_config 는 첫 Streamlit 호출이므로
# 세션 값을 먼저 읽고 그다음에 호출한다.
# 기본값 init(True), 데모 계정 생성
db.init()
authed = st.session_state.get("authenticated", False)

st.set_page_config(
    page_title="DP Agent · Workspace",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded" if authed else "collapsed",
)

# 세션 상태 초기화(디폴트 설정)
state.init()


# ===로그인 전(authed 디폴트는 False): 사이드바를 아예 숨김===
if not authed:
    st.markdown(
        """
        <style>
        /* 로그인 화면에서만 사이드바와 토글 버튼을 완전히 숨김 */
        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] { display: none !important; }
        section.main { margin-left: 0 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    auth.render_login()
    st.stop()

# ===로그인 후(authed = True)===
# 개인 상한을 반영한 정책 정보 로딩
state.apply_effective_policy()

IS_ADMIN = bool(st.session_state.get("is_admin"))


# ── 페이지 구성 ───────────────────────────────────────────
# 분석가: Console + Budget Requests
# 관리자: Console + Privacy(정책 실험/확정) + Audit(예산 결재)
agent_qa = st.Page(
    "ui/pages/agent_qa.py",
    title="DP Agent Console",
    # icon=":material/chat:",
    icon="💬",
    default=True,
)

if IS_ADMIN:
    pages: dict[str, list] = {
        "Workspace": [agent_qa],
        "Admin": [
            st.Page("ui/pages/privacy.py",
                    title="Privacy Policy",
                    # icon=":material/shield:"),
                    icon="🛡️"),
            st.Page("ui/pages/audit.py",
                    title="Audit · 예산 결재",
                    # icon=":material/receipt_long:"),
                    icon="📜"),
        ],
    }
else:
    pages = {
        "Workspace": [
            agent_qa,
            st.Page("ui/pages/budget_requests.py",
                    title="Budget Requests",
                    # icon=":material/request_quote:"),
                    icon="📝"),
        ],
    }

pg = st.navigation(pages)


# ── 사이드바: 페이지 컨텍스트 슬롯 + 하단 고정 블록 ──────
with st.sidebar:
    # 각 페이지가 이 컨테이너에 DB/필터 등을 채운다.
    st.session_state.nav_slot = st.container()

    # 사이드바 최하단 (역할 표시 + 로그아웃)
    with st.container(key="sidebar_bottom"):
        st.divider()
        role_label = "관리자" if IS_ADMIN else "분석가"
        st.write(f"**{role_label}** · {st.session_state.username}")
            # Ex) 관리자 · admin
        if st.button("Log out", width='stretch'):
            state.logout()
            st.rerun()


pg.run()