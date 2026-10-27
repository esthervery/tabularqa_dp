"""프라이버시 분석 (관리자) — Utility 레벨별 신뢰구간 수렴 시뮬레이션 · 기본 정책 확정.

Renders (위→아래):
    1) 프라이버시 리스크 분석 카드
       · 열 제목 = Utility 1~5 버튼 (누르면 시뮬레이션 재생 + 아래 정책 선택칸 연동)
       · 셀 = 통계 대상 평균을 허용 횟수 k 만큼 반복 질의했을 때의 최종 95% CI 폭
       · 표 아래 = 시뮬레이션 영역 (안내 문구 → 버튼 클릭 시 수렴 애니메이션)
    2) 데이터셋 기본 정책 설정 카드
       · Utility · 메모 · [확정]
       · 데이터셋별 적용 정책 표 (수동 = 관리자 확정 / 자동 = 확정 없음 → 시스템 기본값)

계산: ui/dputils/dp_sim.trace() — 데이터셋당 노이즈 응답 100개를 한 번 만들고 Utility 별로 앞 k 개를 쓴다.
관리자 전용 화면이므로 참 평균 · 실제 값 축을 그대로 보여준다.
"""
from __future__ import annotations

import streamlit as st

from ui import db, design, fields
from ui.security import authz

try:
    from ui.dputils import dp_sim, dp_viz
    _SIM_ERR = None
except Exception as _e:   # scipy · matplotlib 미설치 등 — 화면은 뜨고 안내만 남긴다
    dp_sim = dp_viz = None
    _SIM_ERR = f"{type(_e).__name__}: {_e}"
try:
    from ui.dputils import sim_explain
except Exception:           # 해설이 없어도 시뮬레이션은 동작
    sim_explain = None

RISKS = [1, 2, 3, 4, 5]
COLS = [1.6, 1, 1, 1, 1, 1]               # 데이터셋 | U1..U5 — 머리줄·값줄 공통
EPS_Q = 0.1

SEL, PLAY, DS, FLASH = "pa_sel", "pa_play", "pa_ds", "pa_flash"
OPEN = "pa_open"                          # 시뮬레이션 영역 펼침 여부


# ── 상태 ───────────────────────────────────────────────

def _sync(name: str) -> None:
    """데이터셋이 바뀌면 선택 · 재생 · 정책칸을 초기화한다."""
    if st.session_state.get(DS) != name:
        st.session_state[DS] = name
        st.session_state[SEL] = None
        st.session_state[PLAY] = False
        st.session_state.pop("pol_lv", None)
        st.session_state.pop("pol_note", None)
    if "pol_lv" not in st.session_state:          # 다른 페이지 다녀오면 위젯 상태가 지워진다
        st.session_state["pol_lv"] = int(db.get_active_policy(name)["risk_level"])


def _pick(r: int) -> None:
    st.session_state[SEL] = r
    st.session_state[PLAY] = True
    st.session_state["pol_lv"] = r                # 정책 선택칸 연동
    st.session_state[OPEN] = True                 # 접혀 있어도 Utility 를 누르면 다시 펼친다


def _toggle() -> None:
    """시뮬레이션 영역 접기 / 펼치기 — Utility 선택은 유지한다."""
    st.session_state[OPEN] = not st.session_state.get(OPEN, True)
    st.session_state[PLAY] = False        # 펼칠 때는 마지막 장면만 보여준다 (재생은 ↻ 버튼)


def _replay() -> None:
    st.session_state[PLAY] = True


def _do_confirm(admin: str, ds: str) -> None:
    if not authz.is_admin_now(): return
    lv = int(st.session_state.get("pol_lv") or 1)
    note = (st.session_state.get("pol_note") or "").strip()
    try:
        db.confirm_policy(admin, ds, lv, note or None)
        st.session_state[FLASH] = f"{ds} 기본 정책을 Utility {lv} 로 확정했습니다."
        st.session_state["pol_note"] = ""
    except Exception as e:
        st.session_state[FLASH] = f"확정하지 못했습니다 ({type(e).__name__}: {e})"


# ── 화면 ───────────────────────────────────────────────
def render() -> None:
    design.inject()
    authz.require_admin()

    msg = st.session_state.pop(FLASH, None)
    if msg:
        st.toast(msg, duration="short")

    name = st.session_state.get("db_name")
    spec = fields.SPECS.get(name) or {}
    if not spec.get("enabled"):
        st.markdown(design.empty("분석할 데이터셋을 상단에서 선택하세요"), unsafe_allow_html=True)
        return
    _sync(name)

    # 1) 정책 설정 (맨 위)
    _confirm(name, spec)

    # 2) 프라이버시 리스크 분석
    if dp_sim is None:
        st.markdown(design.warn("시뮬레이터를 불러오지 못했습니다 — scipy · matplotlib 설치가 필요합니다 "
                                f"({_SIM_ERR})"), unsafe_allow_html=True)
    else:
        try:
            tr = dp_sim.trace(name)
        except Exception as e:
            tr = None
            st.markdown(design.warn(f"시뮬레이션을 계산하지 못했습니다 — {type(e).__name__}: {e}"),
                        unsafe_allow_html=True)
        if tr is not None:
            _matrix(name, spec, tr)

    # 3) 데이터셋 별 정책 현황 (맨 아래, 별도 섹션)
    _status(name)


# ── 1) 프라이버시 리스크 분석 ─────────────────────────────
def _matrix(name: str, spec: dict, tr) -> None:
    widths = {r: tr.final(r)[3] for r in RISKS}
    wmax = max(widths.values()) or 1.0
    sel = st.session_state.get(SEL)
    m = spec["measure"]

    with st.container(border=True, key="card_matrix"):
        st.markdown(design.card_head(
            "프라이버시 리스크 분석",
            f"통계 대상({m['label']}) 평균값을 Utility별 허용 횟수만큼 반복 질의했을 때의 "
            "최종 95% 신뢰구간 폭"), unsafe_allow_html=True)

        with st.container(key="pa_head"):
            head = st.columns(COLS, gap="small", vertical_alignment="center")
            for i, r in enumerate(RISKS, 1):
                with head[i]:
                    st.button(f"Utility {r}",
                              key=f"pa_uton_{r}" if sel == r else f"pa_ut_{r}",
                              on_click=_pick, args=(r,), width="stretch")

        row = st.columns(COLS, gap="small", vertical_alignment="center")
        row[0].markdown(
            f'<div class="pa-ds"><span class="tt">{_esc(spec["title"])}</span>'
            f'<span class="ts">{name} · {_esc(m["label"])}</span></div>', unsafe_allow_html=True)
        for i, r in enumerate(RISKS, 1):
            row[i].markdown(_cell(widths[r], wmax, tr.k_of(r), sel == r), unsafe_allow_html=True)

        st.markdown('<div class="pa-div"></div>', unsafe_allow_html=True)
        _sim(spec, tr, sel)


def _cell(v: float, wmax: float, k: int, on: bool) -> str:
    pct = max(6.0, min(100.0, v / wmax * 100))
    return (f'<div class="pa-cell{" on" if on else ""}">'
            f'<span class="v">{dp_sim.fmt_sig(v)}</span>'
            f'<div class="bar"><span style="width:{pct:.0f}%"></span></div>'
            '</div>')


def _loading_html(msg: str = "결과를 해석하고 있습니다…") -> str:
    """LLM 해설 대기 중 말풍선 — 도는 링 + 문구 (CSS 애니메이션이라 재생 중에도 돈다)"""
    return (
        '<div class="pa-load">'
        '<span class="pa-spin"></span>'
        f'<span class="pa-load-t">{msg}</span>'
        '</div>'
    )


def _sim(spec: dict, tr, sel: int | None) -> None:
    if sel is None:
        st.markdown('<div class="pa-empty">유틸리티 버튼을 눌러 프라이버시 리스크를 시뮬레이션하세요</div>',
                    unsafe_allow_html=True)
        return

    k = tr.k_of(sel)
    eps = dp_sim.RISK_LEVELS[sel]
    m = spec["measure"]
    ylabel = m["label"] + (f" ({m['unit']})" if m.get("unit") else "")

    top = st.columns([1, 0.1], vertical_alignment="center")
    top[0].markdown(
        f'<div class="pa-simhead"><b>Utility {sel}</b>'
        f'<span>총 ε {eps:g} · 질의당 ε {dp_sim.EPS_PER_QUERY:g} · 평균 질의 {k}회 반복</span></div>',
        unsafe_allow_html=True)
    opened = st.session_state.get(OPEN, True)
    with top[1]:
        with st.container(key="pa_closewrap", horizontal=True,
                          horizontal_alignment="right"):        # 칸 오른쪽 끝으로
            st.button(":material/expand_less:" if opened else ":material/expand_more:",
                      key="pa_close", on_click=_toggle,
                      help="접기" if opened else "펼치기", width="content")
    if not opened:                        # 접힘 — 제목 줄과 버튼만 남긴다
        return


    if dp_viz.KO_FONT is None:
        st.caption("한글 글꼴을 찾지 못해 그래프 글자가 깨질 수 있습니다 (맑은 고딕 · 나눔고딕 설치 필요).")

    g_col, s_col = st.columns(dp_viz.SIM_COLS, gap="medium", vertical_alignment="center")
    with g_col:
        slot = st.empty()          # 그래프
        st.button("↻ 다시 재생", key="pa_replay", on_click=_replay)   # 그래프 바로 아래
    with s_col:
        info = st.empty()          # 수치 패널
        note = st.empty()          # LLM 해설

    # 해설: 캐시가 있으면 바로, 없으면 애니메이션과 동시에 생성 시작
    fut = None
    if sim_explain is not None:
        payload = sim_explain.build_payload(spec, tr, sel)
        text = sim_explain.cached(payload)
        if text is None:
            fut = sim_explain.submit(payload)
            note.html(_llm_html(None))
        else:
            note.html(_llm_html(text))

    if st.session_state.get(PLAY):
        st.session_state[PLAY] = False            # 한 번만 재생 — 이후 rerun 은 마지막 장면
        dp_viz.play(tr, sel, ylabel, slot, info)
    else:
        dp_viz.still(tr, sel, ylabel, slot, info)

    if fut is not None:
        try:
            note.html(_llm_html(fut.result(timeout=sim_explain.DEFAULT_TIMEOUT + 5)))
        except Exception as e:
            note.html(_llm_html(None, err=f"해설을 불러오지 못했습니다 ({type(e).__name__})"))


def _llm_html(text: str | None, err: str | None = None) -> str:
    if err:
        body = f'<span class="er">{_esc(err)}</span>'
    elif text is None:
        body = '<span class="ld"><i class="spin"></i>결과를 해석하고 있습니다…</span>'
    else:
        body = _esc(text).replace("\n", "<br>")
    return f'<div class="pa-llm"><span class="av">ε</span><div class="tx">{body}</div></div>'


# ── 2) 데이터셋 기본 정책 설정 ────────────────────────────
def _confirm(name: str, spec: dict) -> None:
    admin = st.session_state.get("username") or "admin"

    with st.container(key="sec_confirm"):
        st.markdown(design.card_head("데이터셋 기본 정책 설정", f"대상: {spec['title']}"),
                    unsafe_allow_html=True)

        c1, c2, c3 = st.columns([1.1, 2.2, 0.8], vertical_alignment="bottom")
        with c1:
            st.selectbox("Utility", RISKS, key="pol_lv",
                         format_func=lambda x: f"Utility {x} ({db.RISK_TO_EPSILON[x]:.0f} ε)")
        with c2:
            st.text_input("메모", key="pol_note", placeholder="확정 근거 (선택)")
        with c3:
            st.button("확정", type="primary", key="pol_ok", width="stretch",
                      on_click=_do_confirm, args=(admin, name))


def _status(name: str) -> None:
    """3) 데이터셋 별 정책 현황 — 별도 카드."""
    with st.container(border=True, key="card_policies"):
        st.markdown(design.card_head(
            "데이터셋 별 정책 현황"),
            # "수동 = 관리자 확정 · 자동 = 확정 기록 없음(시스템 기본값)"), 
            unsafe_allow_html=True)
        _policies(name)


def _policies(cur: str) -> None:
    """데이터셋별 현재 적용 정책 — 수동(관리자 확정) / 자동(확정 없음 → 시스템 기본값)."""
    active = db.list_active_policies()
    names = [n for n, s in fields.SPECS.items() if s.get("enabled")]
    eps_q = dp_sim.EPS_PER_QUERY if dp_sim else EPS_Q
    grid = "grid-template-columns:1.7fr 0.8fr 0.6fr 0.7fr 0.7fr 1fr 0.8fr"

    out = [f'<div class="trow head" style="{grid}"><span>데이터셋</span><span>Utility</span>'
           '<span class="r">총 ε</span><span class="r">질의 횟수</span><span>적용 방식</span>'
           '<span>확정 시각</span><span>확정자</span></div>']
    for n in names:
        p = active.get(n)
        manual = p is not None
        lv = int(p["risk_level"]) if manual else int(db.DEFAULT_POLICY["risk_level"])
        eps = db.RISK_TO_EPSILON[lv]
        mode = ('<span class="pmode m">수동</span>' if manual
                else '<span class="pmode a">자동</span>')
        out.append(
            f'<div class="trow{" on" if n == cur else ""}" style="{grid}">'
            f'<span><span class="tt">{_esc(fields.SPECS[n].get("title", n))}</span>'
            f'<span class="ts">{n}</span></span>'
            f'<span>{design.pill(f"Utility {lv}", "primary")}</span>'
            f'<span class="r m">{eps:g}</span>'
            f'<span class="r m">{int(round(eps / eps_q))}회</span>'
            f'<span>{mode}</span>'
            f'<span class="t">{_t(p.get("confirmed_at")) if manual else "-"}</span>'
            f'<span class="t">{_esc(p.get("admin") or "-") if manual else "-"}</span></div>')
    st.markdown("".join(out), unsafe_allow_html=True)


def _t(v) -> str:
    if not v:
        return "-"
    return str(v).replace("T", " ")[5:16]


def _esc(s) -> str:
    return str(s).replace("<", "&lt;").replace(">", "&gt;")


# Streamlit 은 페이지 파일을 '스크립트'로 실행한다 — render() 를 직접 호출해야 한다.
render()