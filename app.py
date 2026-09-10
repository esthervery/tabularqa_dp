# app.py
import streamlit as st
from ui import auth, db, state

st.set_page_config(page_title="DP Agent Workspace", layout="wide")

db.init()
state.init()

if not st.session_state.authenticated:
    auth.render_login()
    st.stop()

IS_ADMIN = bool(st.session_state.get("is_admin"))

# --- 사이드바 하단 고정용 CSS ---
st.markdown("""
<style>
[data-testid="stSidebarUserContent"] {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding-bottom: 1rem;
}
[data-testid="stSidebarUserContent"] > div[data-testid="stVerticalBlock"] {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    height: 100%;
}
.st-key-sidebar_bottom { margin-top: auto; }
</style>
""", unsafe_allow_html=True)

# --- 역할별 페이지 구성 ---
agent_qa = st.Page("ui/pages/agent_qa.py", title="Agent Q&A",
                   icon=":material/chat:", default=True)

pages = {"Workspace": [agent_qa]}
if IS_ADMIN:
    pages["Admin"] = [
        st.Page("ui/pages/privacy.py", title="Privacy Budget",
                icon=":material/shield:"),
        st.Page("ui/pages/audit.py", title="Audit Log",
                icon=":material/receipt_long:"),
    ]

pg = st.navigation(pages)

# --- 사이드바: 위쪽 슬롯(페이지가 채움) / 아래쪽 고정 블록 ---
with st.sidebar:
    st.session_state.nav_slot = st.container()

    with st.container(key="sidebar_bottom"):
        st.divider()
        badge = "🛡️ 관리자" if IS_ADMIN else "👤 분석가"
        st.caption(f"{badge} · {st.session_state.username}")
        if st.button("Log out", width="stretch"):
            state.logout()
            st.rerun()

pg.run()