# streamlit 데모 진입점
import streamlit as st
from ui_design import auth, db, state, theme

# ── 로그인 여부에 따라 페이지 옵션이 달라져야 하므로
#    st.set_page_config 를 조건부로 호출한다.
# 세션 상태를 참조하려면 init 이 먼저 필요.
db.init()
# authenticated 플래그만 미리 확보 (state.init() 이 아직 안 돌았을 수도 있음)
authed = st.session_state.get("authenticated", False)

st.set_page_config(
    page_title="DP Agent · Workspace",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded" if authed else "collapsed",
)

state.init()
theme.inject_global_css()

# ── 로그인 전: 사이드바를 아예 감춘다 ──────────────────────
if not authed:
    st.markdown(
        """
        <style>
        /* 로그인 화면에서는 사이드바와 사이드바 토글 버튼을 완전히 숨김 */
        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {
            display: none !important;
        }
        /* 사이드바가 사라진 만큼 메인 컨텐츠가 가운데로 오도록 */
        [data-testid="stAppViewContainer"] > .main,
        section.main {
            margin-left: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    auth.render_login()
    st.stop()


# 관리자가 예산을 승인해 개인 ε 상한이 늘어난 경우를 반영
state.apply_active_policy()

IS_ADMIN = bool(st.session_state.get("is_admin"))

# ── 페이지 구성 ──────────────────────────────────────────────
# 분석가: Console + Budget Requests
# 관리자: Console + Privacy(정책 확정) + Audit(예산 결재)
agent_qa = st.Page(
    "ui/pages/agent_qa.py",
    title="DP Agent Console",
    icon=":material/chat:",
    default=True,
)

if IS_ADMIN:
    pages: dict[str, list] = {
        "Workspace": [agent_qa],
        "Admin": [
            st.Page("ui/pages/privacy.py",
                    title="Privacy Policy",
                    icon=":material/shield:"),
            st.Page("ui/pages/audit.py",
                    title="Audit · 예산 결재",
                    icon=":material/receipt_long:"),
        ],
    }
else:
    pages = {
        "Workspace": [
            agent_qa,
            st.Page("ui/pages/budget_requests.py",
                    title="Budget Requests",
                    icon=":material/request_quote:"),
        ],
    }

pg = st.navigation(pages)

# ── 사이드바: 브랜드 / 페이지 슬롯 / 하단 고정 블록 ──────────
with st.sidebar:
    # theme.brand_block()
    # 각 페이지가 이 컨테이너를 채운다 (모드별 컨텍스트)
    st.session_state.nav_slot = st.container()

    with st.container(key="sidebar_bottom"):
        st.divider()
        role_tone = "primary" if IS_ADMIN else "success"
        role_label = "🛡️ 관리자" if IS_ADMIN else "👤 분석가"
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;'
            f'margin-bottom:8px;">'
            f'{theme.pill(role_label, role_tone)}'
            f'<span style="font-size:13px;font-weight:600;color:#0f172a;">'
            f'{st.session_state.username}</span></div>',
            unsafe_allow_html=True,
        )
        if st.button("Log out", width="stretch"):
            state.logout()
            st.rerun()

pg.run()