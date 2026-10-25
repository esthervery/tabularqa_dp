"""Streamlit 데모 진입점 (v18 — 상단 네비게이션).

사이드바를 없애고 네비게이션을 메인 화면 맨 위 한 줄로 옮겼다.

    ┌──────────────────────────────────────────────────────────────┐
    │ D DPilot  PRIVACY WORKSPACE   [질의 콘솔][채팅 히스토리][예산신청]   analyst ▾ │
    ├──────────────────────────────────────────────────────────────┤
    │ 페이지 본문 (전체 폭)                                          │
    └──────────────────────────────────────────────────────────────┘

왜 이 구조인가
    · 페이지가 3~4개뿐이라 사이드바는 과한 장치였다. 접기/펼치기 상태를
      관리할 이유도 없다(접히면 다시 안 보이는 문제가 반복됐다).
    · 상단 탭은 접힐 수 없고, 본문이 전체 폭을 쓴다.
    · 라우팅은 st.navigation(position="hidden") 이 담당한다. 네비 UI 는
      st.button + st.switch_page 로 직접 그리므로 스타일이 어긋날 여지가 없다.

레이아웃 원칙
    · position:fixed/absolute 오버레이 금지 — 겹침의 근본 원인.
    · 간격은 Streamlit 기본 gap 유지, 카드 안쪽 여백을 넉넉히.
    · 타입 4단계: 22(수치) / 16(제목) / 13(본문) / 10(메타).
"""
from pathlib import Path

import streamlit as st
from ui import auth, boot, db, design, fields, state

db.init()
authed = st.session_state.get("authenticated", False)

st.set_page_config(
    page_title="DPilot · Workspace",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

state.init()
boot.start()

ENABLED = [k for k, v in fields.SPECS.items() if v.get("enabled")]
if st.session_state.get("db_name") not in ENABLED:
    st.session_state.db_name = ENABLED[0]


# ══ 로그인 전 ═══════════════════════════════════════════
if not authed:
    design.inject()
    _c = st.columns([0.16, 0.68, 0.16])
    with _c[1]:
        auth.render_login()
    st.stop()


# ══ 로그인 후 ═══════════════════════════════════════════
state.apply_effective_policy()
IS_ADMIN = bool(st.session_state.get("is_admin"))
USER = str(st.session_state.username)
ROLE_LABEL = "Admin" if IS_ADMIN else "Analyst"

ROOT = Path(__file__).resolve().parent
_missing: list[str] = []


def _page(rel: str, title: str, icon: str, *, default: bool = False):
    if not (ROOT / rel).exists():
        _missing.append(rel)
        return None
    return st.Page(rel, title=title, icon=icon, **({"default": True} if default else {}))


console = _page("ui/pages/console.py", "질의 콘솔", "💻", default=True)
history = _page("ui/pages/history.py", "채팅 히스토리", "🕘")

if IS_ADMIN:
    NAV = {
        "Workspace": [console, history],
        "Admin": [
            _page("ui/pages/budget_admin.py", "예산 관리", "📊"),
            _page("ui/pages/privacy_analysis.py", "프라이버시 분석", "🎚️"),
        ],
    }
else:
    NAV = {
        "Workspace": [
            console, history,
            _page("ui/pages/budget_request.py", "예산 신청", "📝"),
        ],
    }

PAGES = {k: [p for p in v if p is not None] for k, v in NAV.items()}
PAGES = {k: v for k, v in PAGES.items() if v}

if not PAGES:
    design.inject()
    st.error("표시할 페이지 파일을 찾지 못했습니다.")
    st.code("\n".join(_missing) or "(없음)")
    st.stop()

FLAT = [p for group in PAGES.values() for p in group]
TITLES = [getattr(p, "title", "") for p in FLAT]

if st.session_state.get("nav_active") not in TITLES:
    st.session_state.nav_active = TITLES[0]

pg = st.navigation(PAGES, position="hidden")


# 다른 페이지에서 switch_page 할 때 쓰도록, 이번 실행에 등록된 페이지 객체를
# '파일 경로 → Page' 로 저장한다. (역할에 따라 등록된 페이지가 다르므로
# 페이지 쪽에서는 이 맵에 있는지 먼저 확인하고 이동한다)
st.session_state.page_map = {
    rel: p for rel, p in (
        ("ui/pages/console.py", console),
        ("ui/pages/history.py", history),
        ("ui/pages/budget_request.py",   next((x for x in FLAT if getattr(x, "title", "") == "예산 신청"), None)),
        ("ui/pages/budget_admin.py",     next((x for x in FLAT if getattr(x, "title", "") == "예산 관리"), None)),
        ("ui/pages/privacy_analysis.py", next((x for x in FLAT if getattr(x, "title", "") == "프라이버시 분석"), None)),
    ) if p is not None
}


design.inject()


# ══ 상단 바 ════════════════════════════════════════════
# 왼쪽: 브랜드 / 오른쪽: 탭 + 계정 + 로그아웃 (한 줄, 오른쪽 정렬)
top = st.columns([0.34, 0.66], vertical_alignment="center")
with top[0]:
    st.markdown(
        '<div class="navbrand"><div class="mark">D</div>'
        '<div class="who"><b>DPilot</b><span>PRIVACY WORKSPACE</span></div></div>',
        unsafe_allow_html=True,
    )

with top[1]:
    bar = st.container(horizontal=True, horizontal_alignment="right",
                       vertical_alignment="center", gap="small")
    with bar:
        for pg_item in FLAT:
            t = getattr(pg_item, "title", "")
            ic = getattr(pg_item, "icon", "") or ""
            on = st.session_state.nav_active == t
            if st.button(f"{ic}  {t}", key=f"nav_{t}",
                         type=("primary" if on else "secondary")):
                st.session_state.nav_active = t
                st.switch_page(pg_item)

        st.markdown('<div class="navsep"></div>', unsafe_allow_html=True)

        st.markdown(
            '<div class="navuser"><div class="av">'
            + ("AD" if IS_ADMIN else "AN") + "</div>"
            '<div class="u"><b>' + USER + "</b><span>" + ROLE_LABEL + "</span></div></div>",
            unsafe_allow_html=True,
        )
        if st.button("로그아웃", key="nav_logout"):
            state.logout()
            boot.discard()
            st.rerun()

if _missing:
    st.markdown('<div class="navwarn">페이지 파일 누락 — '
                + ", ".join(f"<code>{m}</code>" for m in _missing) + "</div>",
                unsafe_allow_html=True)

st.markdown('<div class="navrule"></div>', unsafe_allow_html=True)


# ══ 본문 ══════════════════════════════════════════════
pg.run()