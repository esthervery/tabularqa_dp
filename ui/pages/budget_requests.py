### 0919 수정
"""Budget Requests — 분석가용 리스크 업그레이드 신청.

Renders (위→아래):
  [사이드바 슬롯]
    · My requests 요약 (총 건수 / 대기 건수)

  [메인]
    1) 헤더 : "Budget Requests" + 부제 + 사용자 이름
    2) Current status : 현재 이 DB 의 유효 리스크 요약 (Risk N + 총 ε + 출처)
    3) New Request 컨테이너 :
        · 대상 DB selectbox (Agent 콘솔에서 프리셋으로 넘어왔으면 그 값)
        · 요청 레벨 라디오 (current+1 ~ 5 만 노출)
        · 사유 textarea
        · [신청 제출]
    4) History : 내 신청 이력 카드 리스트

핵심 상태 키
    req_prefill_db    : Agent 콘솔이 넘긴 프리셋 DB (소비하면 지움)
    req_prefill_level : Agent 콘솔이 제안한 요청 레벨 (없으면 current+1)
"""
import streamlit as st
from ui import agent_bridge as ab, db, requests as reqs, state, theme

theme.inject_global_css()


ME = st.session_state.username


# ── 사이드바 : My requests 요약 ─────────────────
with st.session_state.nav_slot:
    st.caption("My requests")
    _my = reqs.list_by_user(ME)
    _n_pending = sum(1 for r in _my if r["status"] == "pending")
    st.write(f"총 **{len(_my)}**건 · 대기 **{_n_pending}**건")
    st.divider()


# ── 프리셋 소비 (Agent 콘솔에서 넘어왔을 때) ───
_prefill_db    = st.session_state.pop("req_prefill_db", None)
_prefill_level = st.session_state.pop("req_prefill_level", None)

if _prefill_db and _prefill_db in ab.catalog.names():
    # selectbox 가 아직 생성되기 전에 세션 값을 갈아끼움
    st.session_state["req_db_choice"] = _prefill_db


# ── 헤더 ────────────────────────────────────────
head_l, head_r = st.columns([3, 1.4], vertical_alignment="center")
with head_l:
    st.title("Budget Requests")
    st.caption(
        "이 DB 에 대해 지금보다 높은 리스크 레벨(더 큰 ε 예산)을 관리자에게 요청합니다."
    )
with head_r:
    st.write(f"👤 **{ME}**")


# ── 신청 폼 ─────────────────────────────────────
with st.container(border=True):
    st.subheader("추가 예산 신청")

    c1, c2 = st.columns([1, 1])
    with c1:
        _names = ab.catalog.names()
        _default_idx = (_names.index(st.session_state.get("req_db_choice",
                                                          st.session_state.db_name))
                        if st.session_state.get("req_db_choice",
                                                st.session_state.db_name) in _names
                        else 0)
        db_choice = st.selectbox(
            "대상 데이터베이스",
            _names, index=_default_idx,
            key="req_db_choice",
            format_func=lambda n: f"{n} · {ab.catalog.meta(n)['title'][:32]}",
        )

    # 이 사용자 × 이 DB 의 현재 유효 레벨 조회
    current_pol = db.get_effective_policy(ME, db_choice)
    current_level = int(current_pol["risk_level"])
    current_eps   = float(current_pol["total_epsilon"])
    source_label = {
        "override":       "개인 오버라이드",
        "db_default":     "DB 확정 정책",
        "system_default": "시스템 기본값",
    }[current_pol["source"]]

    with c2:
        st.caption(f"현재 유효 정책 · {source_label}")
        st.metric(
            "현재 리스크 레벨",
            f"Risk {current_level} · ε={current_eps:.1f}",
        )

    # ── 요청 레벨 선택 ─────────────────────
    upgradable = [lvl for lvl in (2, 3, 4, 5) if lvl > current_level]
    if not upgradable:
        st.info(
            "이미 최고 리스크 레벨(Risk 5) 이 적용되어 있어 "
            "추가 업그레이드가 불가능합니다.",
            icon="ℹ️",
        )
    else:
        # 프리셋으로 넘어온 값이 있고 upgradable 안에 있으면 그것을 기본
        if _prefill_level and _prefill_level in upgradable:
            _default_lvl = _prefill_level
        else:
            _default_lvl = upgradable[0]
        _default_idx = upgradable.index(_default_lvl)

        with st.form("new_req", clear_on_submit=True):
            requested_level = st.radio(
                "요청할 리스크 레벨",
                options=upgradable,
                index=_default_idx,
                horizontal=True,
                format_func=lambda l: f"Risk {l} (ε={db.RISK_TO_EPSILON[l]:.0f})",
            )
            reason = st.text_area(
                "사유 · 설명",
                placeholder=(
                    "예) 신용한도 분포를 더 정밀하게 추정해야 하는 분기 리포트 "
                    "작성을 위해 Risk 3 → Risk 4 로의 업그레이드가 필요합니다."
                ),
                height=110,
            )
            submitted = st.form_submit_button(
                "신청 제출", type="primary", width='stretch',
            )
            if submitted:
                if not reason.strip():
                    st.error("사유를 입력해주세요.")
                else:
                    rid = reqs.create(
                        username=ME, db_name=db_choice,
                        current_level=current_level,
                        requested_level=int(requested_level),
                        reason=reason,
                    )
                    state.log(
                        "request",
                        f"#{rid} {db_choice}: "
                        f"Risk {current_level} → Risk {requested_level}",
                    )
                    st.success(
                        f"신청 #{rid} 가 접수되었습니다. 관리자 결재를 기다립니다.",
                        icon="✅",
                    )
                    st.rerun()


# ── 내 신청 이력 ────────────────────────────────
st.subheader("History · 내 신청 이력")

_mine = reqs.list_by_user(ME)
if not _mine:
    st.info("아직 신청 이력이 없습니다.")
else:
    _STATUS = {
        "pending":  ("⏳ 대기",     st.warning),
        "approved": ("✅ 승인",     st.success),
        "partial":  ("🟡 부분승인",  st.info),
        "rejected": ("❌ 거절",     st.error),
    }
    for r in _mine:
        label, alert_fn = _STATUS[r["status"]]
        appr_lvl = r["approved_level"]
        appr_str = f"Risk {appr_lvl}" if appr_lvl is not None else "—"

        with st.container(border=True):
            head_l, head_r = st.columns([3, 1])
            with head_l:
                st.write(
                    f"**#{r['id']}** · `{r['db_name']}` · "
                    f"Risk {r['current_level']} → Risk {r['requested_level']}"
                )
            with head_r:
                alert_fn(label)

            st.caption(
                f"승인 결과 : **{appr_str}** · "
                f"신청 {r['created_at'][5:16].replace('T', ' ')}"
                + (f" · 결재 {r['reviewed_at'][5:16].replace('T', ' ')}"
                   if r["reviewed_at"] else "")
            )
            st.write(r["reason"])
            if r["admin_note"]:
                st.caption(f"관리자 노트 — \"{r['admin_note']}\"")