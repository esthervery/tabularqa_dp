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
from ui import db, design, fields
from ui.dputils import state
from ui.pages import auth, privacy_policy
from ui.utils import boot

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
        if st.session_state.get(auth.VIEW) == "privacy":
            privacy_policy.render()
        else:
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


# ── 상단 데이터셋 선택 ─────────────────────────────────
# 공용 값은 db_name(항상 실제 데이터셋). '전체' 필터는 화면별 전용 키에 따로 둔다.
#   예산 관리     → adm_ds   (기본: 전체)
#   채팅 히스토리 → hist_ds  (기본: 전체)
# 예산 관리의 '전체' 필터는 adm_ds 에 따로 둔다.
# key 를 쓰지 않고 index 로만 현재 값을 표현한다 (v17 버그 회피 — console.py 주석 참고).
ALL_DS = "전체"
CUR_TITLE = getattr(pg, "title", st.session_state.nav_active)
DS_MODE = {"예산 관리": "admin", "채팅 히스토리": "hist"}.get(CUR_TITLE, "ds")


def _ds_label(k: str) -> str:
    return "전체 데이터셋" if k == ALL_DS else f"{fields.SPECS[k]['title']}  ·  {k}"


PW_FLASH = "pw_flash"


@st.dialog("비밀번호 변경", width="small")
def _pw_dialog() -> None:
    st.caption(f"{USER} · {ROLE_LABEL}")
    with st.form("pw_form", border=False):
        cur = st.text_input("현재 비밀번호", type="password", key="pw_cur")
        new = st.text_input("새 비밀번호", type="password", key="pw_new",
                            help="8자 이상")
        new2 = st.text_input("새 비밀번호 확인", type="password", key="pw_new2")
        ok = st.form_submit_button("변경", type="primary", width="stretch")
    if not ok:
        return
    if new != new2:
        st.error("새 비밀번호가 서로 일치하지 않습니다.")
        return
    success, msg = db.change_password(USER, cur, new)
    if not success:
        st.error(msg)
        return
    st.session_state[PW_FLASH] = msg
    st.rerun()                                # 대화상자 닫힘


def _ds_picker() -> None:
    """데이터셋 선택기 — mode="none"(프라이버시 분석)일 때만 자리를 비운다."""
    if DS_MODE == "none":
        return

    if DS_MODE in ("admin", "hist"):        # '전체' 허용 (기본값 = 전체)
        opts = [ALL_DS] + ENABLED
        skey = "adm_ds" if DS_MODE == "admin" else "hist_ds"
        now = st.session_state.setdefault(skey, ALL_DS)
        if now not in opts:                 # 정렬·구성 변화 방어
            now = ALL_DS
            st.session_state[skey] = now
    else:                                    # "ds" — 질의 콘솔 (전체 없음)
        opts, skey = ENABLED, None
        now = st.session_state.db_name

    pick = st.selectbox(
        f"dataset_{DS_MODE}",                # 라벨을 모드별로 달리해 위젯 상태를 분리
        opts, index=opts.index(now), format_func=_ds_label,
        label_visibility="collapsed", width="stretch",   # 폭은 CSS 에서 150~340px 로 제한
    )
    if pick == now:
        return

    if skey is None:                         # 질의 콘솔 — 공용 값(db_name)을 바꾼다
        st.session_state.db_name = pick
        state.reset_console()
    else:
        st.session_state[skey] = pick
        if DS_MODE == "admin" and pick != ALL_DS and pick != st.session_state.db_name:
            st.session_state.db_name = pick   # 예산 관리에서 특정 셋을 고르면 공용 값도 동기화
            state.reset_console()
        if DS_MODE == "hist":
            st.session_state["hist_sel"] = None   # 데이터셋을 바꾸면 열린 상세는 닫는다
    st.rerun()



# ══ 상단 바 ════════════════════════════════════════════
# 한 줄 고정(wrap=False) — 창이 좁아지면 줄바꿈 대신 선택칸부터 줄어든다.
# 왼쪽 navleft: 브랜드 | 탭  /  오른쪽 navbar: 데이터셋 선택 | 계정 · 로그아웃
with st.container(horizontal=True, wrap=False, vertical_alignment="center",
                  gap="small", key="navtop"):

    # 왼쪽 — 내용 폭만큼만 차지한다
    with st.container(horizontal=True, wrap=False, vertical_alignment="center",
                      gap="small", width="content", key="navleft"):
        st.html(
            '<div class="navbrand"><div class="mark">D</div>'
            '<div class="who"><b>DPilot</b><span>PRIVACY WORKSPACE</span></div></div>',
            width="content",
        )
        st.html('<div class="navsep"></div>', width="content")
        # 현재 페이지는 st.navigation 이 돌려준 pg 기준
        cur_title = getattr(pg, "title", st.session_state.nav_active)
        for i, pg_item in enumerate(FLAT):
            t = getattr(pg_item, "title", "")
            on = (t == cur_title)
            if st.button(t, key=(f"nav_on_{i}" if on else f"nav_{i}"), type="tertiary"):
                st.session_state.nav_active = t
                st.switch_page(pg_item)

    st.space(98)
    # 오른쪽 — 남은 폭 전부, 내용은 오른쪽 끝에 붙는다
    with st.container(horizontal=True, wrap=False, horizontal_alignment="right",
                      vertical_alignment="center", gap="small", key="navbar"):
        _ds_picker()
        st.html('<div class="navsep"></div>', width="content")
        if st.button(USER, key=("nav_user_ad" if IS_ADMIN else "nav_user_an"),
                     type="tertiary", help="비밀번호 변경"):
            _pw_dialog()
        if st.button("로그아웃", key="nav_logout", type="tertiary"):
            boot.discard()
            state.logout()
            st.rerun()


if _missing:
    st.markdown('<div class="navwarn">페이지 파일 누락 — '
                + ", ".join(f"<code>{m}</code>" for m in _missing) + "</div>",
                unsafe_allow_html=True)

st.markdown('<div class="navrule"></div>', unsafe_allow_html=True)
if (_m := st.session_state.pop(PW_FLASH, None)):
    st.toast(_m, icon=":material/check_circle:", duration="short")


# ══ 본문 ══════════════════════════════════════════════
pg.run()