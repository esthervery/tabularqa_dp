"""Streamlit 데모 진입점 (v14 시안 기준).

역할별 페이지 라우팅과 사이드바 하단 블록만 담당한다.
각 페이지는 ui/pages/*.py 에서 독립적으로 렌더링을 결정한다.

    분석가 : 질의 콘솔 / 채팅 히스토리 / 예산 신청
    관리자 : 질의 콘솔 / 채팅 히스토리 / 예산 관리 / 프라이버시 분석

역할은 로그인 계정이 결정한다(users.is_admin). 화면에 역할 토글은 두지 않는다.
"""
import streamlit as st
from ui import auth, boot, db, fields, state

# 스키마 준비 + 세션 상태 확인. set_page_config 는 첫 Streamlit 호출이므로
# 세션 값을 먼저 읽고 그다음에 호출한다.
db.init()
authed = st.session_state.get("authenticated", False)

st.set_page_config(
    page_title="DPilot · Workspace",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded" if authed else "collapsed",
)

state.init()

# 파이프라인 워밍업 — 로그인 화면을 띄우는 동안 백그라운드로 로딩한다.
boot.start()

# 데모 데이터셋 카탈로그 (state.DEFAULTS 의 db_name 은 구버전 값이다)
ENABLED = [k for k, v in fields.SPECS.items() if v.get("enabled")]
if st.session_state.get("db_name") not in ENABLED:
    st.session_state.db_name = ENABLED[0]


# ===로그인 전: 사이드바를 아예 숨김===
if not authed:
    st.markdown(
        """
        <style>
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

# ===로그인 후===
state.apply_effective_policy()

IS_ADMIN = bool(st.session_state.get("is_admin"))

# ── 페이지 구성 ───────────────────────────────────────────
console = st.Page("ui/pages/console.py", title="질의 콘솔", icon="💻", default=True)
history = st.Page("ui/pages/history.py", title="채팅 히스토리", icon="🕘")

if IS_ADMIN:
    pages: dict[str, list] = {
        "Workspace": [console, history],
        "Admin": [
            st.Page("ui/pages/budget_admin.py", title="예산 관리", icon="📊"),
            st.Page("ui/pages/privacy.py", title="프라이버시 분석", icon="🎚️"),
        ],
    }
else:
    pages = {
        "Workspace": [
            console, history,
            st.Page("ui/pages/budget_request.py", title="예산 신청", icon="📝"),
        ],
    }

pg = st.navigation(pages)


# ── 사이드바: 하단 고정 블록 ──────────────────────────────
with st.sidebar:
    with st.container(key="sidebar_bottom"):
        role_label = "Admin" if IS_ADMIN else "Analyst"
        st.markdown(
            '<div style="display:flex;align-items:center;gap:7px;padding:10px 0 8px;'
            'border-top:1px solid #e4e8ee;margin-top:10px">'
            '<div style="width:20px;height:20px;border-radius:5px;background:#eef0fe;'
            'border:1px solid #cdd2fb;color:#3f42b8;display:flex;align-items:center;'
            'justify-content:center;font-family:IBM Plex Mono,monospace;font-size:8px;'
            'font-weight:600">'
            f'{role_label[:2].upper()}</div>'
            '<div style="display:flex;flex-direction:column;line-height:1.25">'
            f'<b style="font-size:10.5px;color:#101828">{st.session_state.username}</b>'
            f'<span style="font-family:IBM Plex Mono,monospace;font-size:7.5px;'
            f'color:#8896a8">{role_label}</span></div></div>',
            unsafe_allow_html=True,
        )
        if st.button("→ 로그아웃", use_container_width=True):
            state.logout()
            # 로그인마다 새 파이프라인이 되도록 폐기한다 (rerun 보다 먼저).
            boot.discard()
            st.rerun()


pg.run()