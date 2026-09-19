"""Budget Requests — 분석가용 예산 증액 신청.

Renders (위→아래):
  [사이드바 슬롯]
    1) Query target : 도메인/DB selectbox (신청 폼 기본값)
    2) My requests  : 총 건수 / 대기 건수 요약

  [메인]
    3) 헤더  : "Budget Requests" + 분석가 이름 표시
    4) 잔여 예산 도넛 게이지 : 개인 상한 대비 세션 내 소모
    5) New Request 폼        : 대상 DB / 요청 ε 슬라이더 / 사유 textarea / [신청 제출]
    6) History               : 내가 낸 신청들의 카드 리스트 (상태 뱃지 + 관리자 노트)

핵심 상태 키
    없음. 신청 자체는 SQLite budget_requests 테이블에 즉시 커밋된다.
"""
import streamlit as st
from ui import agent_bridge as ab, requests as reqs, state, theme

theme.inject_global_css()
state.apply_active_policy()


# ── 사이드바 컨텍스트 ──────────────────────────────────
with st.session_state.nav_slot:
    st.caption("Query target")
    dom = st.selectbox("도메인", ab.catalog.domains(),
                       key="db_domain", label_visibility="collapsed")
    choices = ab.catalog.names(dom)
    if not choices:
        st.error("`competition/` 에서 `all.parquet` 을 찾지 못했습니다.")
        st.stop()
    if st.session_state.db_name not in choices:
        st.session_state.db_name = choices[0]
    st.selectbox(
        "Database", choices, key="db_name",
        format_func=lambda n: f"{n} · {ab.catalog.meta(n)['title'][:26]}",
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("My requests")
    _my = reqs.list_by_user(st.session_state.username)
    _n_pending = sum(1 for r in _my if r["status"] == "pending")
    st.write(f"총 **{len(_my)}**건 · 대기 **{_n_pending}**건")


# ── 헤더 ───────────────────────────────────────────
head_l, head_r = st.columns([3, 1.4], vertical_alignment="center")
with head_l:
    st.title("Budget Requests")
    st.caption("ε 상한을 다 쓴 경우 관리자에게 예산 증액을 요청합니다.")
with head_r:
    st.write(f"👤 **{st.session_state.username}**")


# ── 잔여 예산 도넛 게이지 ──────────────────────────
_eps_cap   = st.session_state.eps_cap
_spent     = st.session_state.spent
_remaining = max(0.0, _eps_cap - _spent)
_ratio     = _spent / max(_eps_cap, 1e-9)
_tone      = ("success" if _ratio < 0.6
              else ("warning" if _ratio < 0.9 else "danger"))

st.markdown(
    theme.donut_gauge(
        "현재 상한 대비 소모", _spent, _eps_cap,
        unit="ε", tone=_tone,
        sub=f"잔여 {_remaining:.2f} ε · 상한 {_eps_cap:.2f} ε",
    ),
    unsafe_allow_html=True,
)


# ── 신청 폼 ─────────────────────────────────────────
with st.container(border=True):
    st.subheader("New Request · 추가 예산 신청서")
    st.caption("관리자가 검토 후 승인·부분승인·거절 처리합니다.")

    with st.form("new_req", clear_on_submit=True):
        c1, c2 = st.columns([1, 1])
        with c1:
            _names = ab.catalog.names()
            _default_idx = (_names.index(st.session_state.db_name)
                            if st.session_state.db_name in _names else 0)
            db_choice = st.selectbox(
                "대상 데이터베이스",
                _names, index=_default_idx,
                format_func=lambda n: f"{n} · {ab.catalog.meta(n)['title'][:32]}",
                help="현재 콘솔에서 선택한 DB가 기본값입니다.",
            )
        with c2:
            requested = st.slider(
                "요청 ε 증액",
                0.5, 20.0, value=2.0, step=0.5,
                help="현재 상한에 얼마만큼 더 얹어달라고 요청할지 지정합니다.",
            )
        reason = st.text_area(
            "사유 · 설명",
            placeholder=(
                "예) 신용한도 분포의 라운드별 상대폭이 5%에 도달하지 못해 "
                "정지 규칙을 만족하지 못했습니다. 세 번의 라운드를 추가로 "
                "돌리기 위해 약 2.0 ε의 증액이 필요합니다."
            ),
            height=110,
        )
        submitted = st.form_submit_button(
            "신청 제출", type="primary", use_container_width=True,
        )
        if submitted:
            if not reason.strip():
                st.error("사유를 입력해주세요.")
            else:
                _rid = reqs.create(
                    st.session_state.username, db_choice,
                    float(requested), reason,
                )
                state.log("request",
                          f"#{_rid} +{requested:.2f}ε for {db_choice}")
                st.success(f"신청 #{_rid} 가 접수되었습니다. 관리자 결재를 기다립니다.")
                st.rerun()


# ── 내 신청 이력 ────────────────────────────────────
st.subheader("History · 내 신청 이력")

_mine = reqs.list_by_user(st.session_state.username)
if not _mine:
    st.info("아직 신청 이력이 없습니다.")
else:
    _STATUS_LABEL = {
        "pending":  ("⏳ 대기",     st.warning),
        "approved": ("✅ 승인",     st.success),
        "partial":  ("🟡 부분승인",  st.info),
        "rejected": ("❌ 거절",     st.error),
    }
    for r in _mine:
        label, alert_fn = _STATUS_LABEL[r["status"]]
        appr = f"{r['approved']:.2f}" if r["approved"] is not None else "—"

        with st.container(border=True):
            head_l, head_r = st.columns([3, 1])
            with head_l:
                st.write(f"**#{r['id']}** · `{r['db_name']}`")
            with head_r:
                # 상태별로 다른 alert 함수를 호출
                alert_fn(label)

            st.caption(
                f"요청 **{r['requested']:.2f} ε** · 승인 **{appr} ε** · "
                f"신청 {r['created_at'][5:16].replace('T', ' ')}"
                + (f" · 결재 {r['reviewed_at'][5:16].replace('T', ' ')}"
                   if r["reviewed_at"] else "")
            )
            st.write(r["reason"])
            if r["admin_note"]:
                st.caption(f"관리자 노트 — \"{r['admin_note']}\"")
