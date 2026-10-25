"""Streamlit 데모 진입점 (v14 시안 기준).

역할별 페이지 라우팅과 사이드바 하단 블록만 담당한다.
각 페이지는 ui/pages/*.py 에서 독립적으로 렌더링을 결정한다.

    분석가 : 질의 콘솔 / 채팅 히스토리 / 예산 신청
    관리자 : 질의 콘솔 / 채팅 히스토리 / 예산 관리 / 프라이버시 분석

역할은 로그인 계정이 결정한다(users.is_admin). 화면에 역할 토글은 두지 않는다.

페이지 파일이 없을 때
    st.Page() 는 파일이 없으면 StreamlitPageNotFoundError 를 던지고 앱 전체가 죽는다.
    그 화면만 빠지고 나머지는 쓰게 하려고, 이 파일은 경로를 먼저 확인하고
    없는 페이지만 건너뛴 뒤 사이드바에 무엇이 없는지 적는다.
    (진단: `python check_pages.py` — 실제 파일명을 repr 로 찍어 숨은 문자를 드러낸다.)
"""
from pathlib import Path

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


# ── 페이지 경로 확인 ─────────────────────────────────────
# st.Page 는 존재하지 않는 경로에서 예외를 던진다. 먼저 확인해 건너뛴다.
ROOT = Path(__file__).resolve().parent
PAGES_DIR = ROOT / "ui" / "pages"
_missing: list[str] = []


def _page(rel: str, title: str, icon: str, *, default: bool = False):
    if not (ROOT / rel).exists():
        _missing.append(rel)
        return None
    return st.Page(rel, title=title, icon=icon, **({"default": True} if default else {}))


def _report_missing() -> None:
    """누락된 페이지 경로와 ui/pages 실제 내용을 화면에 그대로 보여준다."""
    st.markdown(
        f"**저장소 루트** `{ROOT}`\n\n"
        f"**ui/pages** `{PAGES_DIR}` — exists={PAGES_DIR.is_dir()}\n\n"
        "**찾지 못한 경로**\n```\n"
        + "\n".join(_missing)
        + "\n```\n**ui/pages 실제 파일 (repr)**\n```\n"
        + (
            "\n".join(f"{p.name!r}" for p in sorted(PAGES_DIR.iterdir()))
            if PAGES_DIR.is_dir() else "(폴더 없음)"
        )
        + "\n```\n> 터미널에서 `python check_pages.py` 를 실행하면 같은 내용을 자세히 볼 수 있습니다."
    )


console = _page("ui/pages/console.py", "질의 콘솔", "💻", default=True)
history = _page("ui/pages/history.py", "채팅 히스토리", "🕘")

if IS_ADMIN:
    _groups = {
        "Workspace": [console, history],
        "Admin": [
            _page("ui/pages/budget_admin.py", "예산 관리", "📊"),
            _page("ui/pages/privacy_analysis.py", "프라이버시 분석", "🎚️"),
        ],
    }
else:
    _groups = {
        "Workspace": [
            console, history,
            _page("ui/pages/budget_request.py", "예산 신청", "📝"),
        ],
    }

pages = {k: [p for p in v if p is not None] for k, v in _groups.items()}
pages = {k: v for k, v in pages.items() if v}

# 남은 페이지가 하나도 없으면 st.navigation 이 실패한다 — 원인을 화면에 적고 멈춘다.
if not pages:
    st.error("표시할 페이지 파일을 찾지 못했습니다 — 아래 경로를 확인하세요.")
    _report_missing()
    st.stop()

pg = st.navigation(pages)


# ── 사이드바: 누락 안내 + 하단 고정 블록 ──────────────────
with st.sidebar:
    if _missing:
        st.markdown(
            '<div style="border:1px solid #f7c6cf;background:#fdeef0;color:#a32a3f;'
            'border-radius:7px;padding:8px 10px;font-size:9.5px;margin:8px 0">'
            f'페이지 파일 {len(_missing)}개를 찾지 못해 건너뛰었습니다.<br>'
            + "<br>".join(f'· <code>{m}</code>' for m in _missing) +
            '<br><span style="color:#8a4351">터미널에서 <code>python check_pages.py</code> 실행</span>'
            "</div>", unsafe_allow_html=True)

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