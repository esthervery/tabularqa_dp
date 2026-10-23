"""Workspace entry point with a top header and role-based navigation."""
import streamlit as st
from ui import auth, boot, db, state, theme


# 스키마 준비 + 세션 상태 확인. set_page_config 는 첫 Streamlit 호출이므로
# 세션 값을 먼저 읽고 그다음에 호출한다.
# 기본값 init(True), 데모 계정 생성
db.init()
authed = st.session_state.get("authenticated", False)

st.set_page_config(
    page_title="DP Agent · Workspace",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 세션 상태 초기화(디폴트 설정)
state.init()
theme.inject_global_css()

# [0928] 파이프라인 워밍업: 로그인 화면을 띄우는 동안 백그라운드로 로딩한다.
# 로그인 전 st.stop() 보다 먼저 호출해야 로그인 화면 시점부터 로딩이 시작된다.
# (페이지 파일은 pg.run() 시점에 실행되므로, 여기서 안 걸면 첫 질의에서야 로딩이 시작된다.)
# boot 모듈 안의 _started 가드 덕분에 리런마다 호출해도 기동은 1회뿐이다.
boot.start()


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
# state.apply_active_policy()
state.select_database()
state.apply_effective_policy()

IS_ADMIN = bool(st.session_state.get("is_admin"))


# ── 페이지 구성 ───────────────────────────────────────────
# 분석가: Console + Budget Requests
# 관리자: Console + Privacy(정책 실험/확정) + Audit(예산 결재)
agent_qa = st.Page(
    "ui/pages/agent_qa.py",
    title="DP Agent Console",
    # icon=":material/chat:",
    icon="💻",
    default=True,
)

if IS_ADMIN:
    pages: dict[str, list] = {
        "Workspace": [agent_qa],
        "Admin": [
            st.Page("ui/pages/privacy.py",
                    title="Privacy Policy",
                    # icon=":material/shield:"),
                    icon="🎚️"),
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

# Register routes without the built-in sidebar; retain normal page URLs.
pg = st.navigation(pages, position="hidden")

with st.container(key="workspace_header"):
    brand_col, account_col, logout_col = st.columns([5, 2, 1.3], vertical_alignment="center")
    with brand_col:
        theme.brand_block()
    with account_col:
        theme.role_block(st.session_state.username, IS_ADMIN)
    with logout_col:
        if st.button("로그아웃", key="header_logout", width="stretch"):
            state.logout()
            boot.discard()
            st.rerun()

with st.container(key="workspace_navigation"):
    for group, routes in pages.items():
        label_col, links_col = st.columns([1, 7], vertical_alignment="center")
        with label_col:
            st.caption(group.upper())
        with links_col:
            columns = st.columns(len(routes))
            for column, route in zip(columns, routes):
                with column:
                    st.page_link(route, label=route.title, width="stretch")

# Existing page summaries (requests and audit) now render above page content.
with st.container(key="workspace_context"):
    st.session_state.nav_slot = st.container()

pg.run()
