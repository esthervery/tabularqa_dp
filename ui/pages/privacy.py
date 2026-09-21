### 0919 수정
"""Privacy Policy — 관리자용 DB별 리스크 정책 콘솔.

Renders (위→아래):
  [사이드바 슬롯 : 비워둠]

  [메인]
    1) 헤더 : "Privacy Policy" + 부제
    2) Policy scope : 편집 대상 DB selectbox
    3) Currently applied : 이 DB 의 현재 확정 정책 요약 (Risk N + 총 ε + k)
    4) Risk 버튼 5개 (Risk 1..5) → 클릭 시 미리보기 모달 open
    5) Matrix (expander) : 모든 DB 의 현재 정책 요약
    6) History : 확정 이력 dataframe

  [모달] (관리자가 Risk N 버튼을 눌렀을 때)
    · 시각화 A/B 자리 (지금은 스텁)
    · 해설 자리 (지금은 스텁)
    · [✓ 확정] · [✕ 취소]
    · 확정 시 db.confirm_policy() 호출 후 모달 닫고 rerun.
"""
import pandas as pd
import streamlit as st

from ui import agent_bridge as ab, db, state, theme
from ui import dp_sim


theme.inject_global_css()

if not st.session_state.get("is_admin"):
    st.error("이 페이지는 관리자 권한이 필요합니다.")
    st.stop()


ME = st.session_state.username


# ── 사이드바 : 이 페이지는 사이드바에 아무것도 두지 않는다 ──


# ── 헤더 ────────────────────────────────────────────
st.title("Privacy Policy")
# st.caption(
#     "DB별로 리스크 레벨을 선택하면 총 ε 예산과 라운드 수(k)가 자동으로 결정됩니다. "
#     "리스크 버튼을 눌러 미리보기 그래프에서 신뢰구간 수렴과 인접 DB CI 겹침을 확인한 뒤 확정하세요."
# )


# ── Policy scope · 편집 대상 DB ─────────────────────
with st.container(border=True):
    st.subheader("데이터베이스 선택")
    sel_l, sel_r = st.columns([1, 2])
    with sel_l:
        dom = st.selectbox(
            "도메인", ab.catalog.domains(), key="db_domain",
        )
    with sel_r:
        choices = ab.catalog.names(dom)
        if not choices:
            st.error("`competition/` 에서 `all.parquet` 을 찾지 못했습니다.")
            st.stop()
        if st.session_state.db_name not in choices:
            st.session_state.db_name = choices[0]
        st.selectbox(
            "Database", choices, key="db_name",
            format_func=lambda n: f"{n} · {ab.catalog.meta(n)['title'][:40]}",
        )

    if dp_sim.is_supported(st.session_state.db_name):
        st.caption(
            f"시뮬레이션 대상 컬럼 : "
            f"`{dp_sim.target_of(st.session_state.db_name)}`"
        )
    else:
        st.warning(
            f"`{st.session_state.db_name}` 는 아직 시뮬레이션 대상 컬럼이 "
            f"등록되어 있지 않습니다. `ui/dp_sim.py` 의 `SIM_TARGET` 에 추가하세요.",
            icon="⚠️",
        )


DBNAME = st.session_state.db_name
ACTIVE = db.get_active_policy(DBNAME)


# ── Risk 버튼 5개 ──────────────────────────────
with st.container(border=True):
    st.subheader("리스크 레벨 선택")

    btn_cols = st.columns(5)
    for lvl in (1, 2, 3, 4, 5):
        eps = db.RISK_TO_EPSILON[lvl]
        is_current = (lvl == int(ACTIVE["risk_level"]))
        label = f"Risk {lvl}\n(ε={eps:.0f})"
        if btn_cols[lvl - 1].button(
            label,
            key=f"risk_btn_{lvl}",
            type=("primary" if is_current else "secondary"),
            width='stretch',
        ):
            st.session_state.policy_modal_open  = True
            st.session_state.policy_modal_level = lvl
            st.rerun()


# ── Currently applied ────────────────────────────
with st.container(border=True):
    is_default = ACTIVE.get("confirmed_at") is None
    if is_default:
        st.subheader("활성 프라이버시 정책")
        st.caption(
            f"`{DBNAME}` 에 확정된 정책이 없어 시스템 기본값 (Risk 1) 이 적용됩니다."
        )
    else:
        st.subheader(f"현재 정책 · `{DBNAME}`")
        st.caption(
            f"확정 · {ACTIVE['confirmed_at'].replace('T', ' ')}"
            f" · by {ACTIVE.get('admin') or 'system'}"
        )

    a1, a2, a3 = st.columns(3)
    a1.metric("리스크 레벨", f"Risk {ACTIVE['risk_level']}")
    a2.metric("총 ε 예산",   f"{ACTIVE['total_epsilon']:.1f}")
    a3.metric("라운드 수 k", f"{int(ACTIVE['total_epsilon'] / dp_sim.EPS_PER_QUERY)}")


# ── 모달 (dialog) ──────────────────────────────

@st.dialog("Risk 정책 테스트", width="large")
def _risk_preview_dialog():
    lvl = st.session_state.policy_modal_level
    if lvl is None:
        st.warning("레벨이 지정되지 않았습니다.")
        return

    eps = db.RISK_TO_EPSILON[lvl]
    k   = int(eps / dp_sim.EPS_PER_QUERY)

    st.subheader(f"Risk {lvl}  ·  총 ε = {eps:.0f}  ·  k = {k} rounds")
    st.caption(
        f"대상 DB : `{DBNAME}` · "
        f"현재 확정 : Risk {ACTIVE['risk_level']} (ε = {ACTIVE['total_epsilon']:.0f})"
    )

    # ── 시각화 스텁 A ────────────────────────
    with st.container(border=True):
        st.info("📈 [시각화 A 자리]  라운드별 신뢰구간 수렴 그래프")
        st.caption("(dp_sim 시각화 구현 이후 이 자리에 그래프가 렌더링됩니다)")

    # ── 시각화 스텁 B ────────────────────────
    with st.container(border=True):
        st.info("🔀 [시각화 B 자리]  인접 DB 신뢰구간 겹침 비교")
        st.caption(
            "Overlap ratio · Δ (민감도) 지표가 이 자리에 표시됩니다."
        )

    # ── 해설 스텁 ────────────────────────────
    with st.container(border=True):
        st.markdown("##### 해설")
        st.write(
            f"[해설 자리]  Risk {lvl} 은 총 ε = {eps:.0f} 을 사용하며 "
            f"{k} 회 라운드를 실행합니다. 실제 신뢰구간 수렴 정도와 인접 DB "
            f"CI 겹침 비율에 대한 해설이 이 자리에 표시됩니다."
        )

    # ── 확정 / 취소 ─────────────────────────
    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        note = st.text_input(
            "확정 노트 (선택)",
            key="policy_confirm_note",
            placeholder="예) 데모 시연용 Risk 3 채택",
            label_visibility="collapsed",
        )
    with c2:
        if st.button("✓ 확정", type="primary", width='stretch'):
            new_active = db.confirm_policy(
                admin=ME, db_name=DBNAME, risk_level=int(lvl),
                note=note or None,
            )
            state.log(
                "policy_confirm",
                f"{DBNAME}: Risk {new_active['risk_level']} "
                f"(ε={new_active['total_epsilon']:.1f})",
            )
            st.session_state.policy_modal_open = False
            st.session_state.policy_modal_level = None
            st.success(
                f"`{DBNAME}` 이(가) Risk {new_active['risk_level']} 로 확정되었습니다.",
                icon="✅",
            )
            st.rerun()
    with c3:
        if st.button("✕ 취소", width='stretch'):
            st.session_state.policy_modal_open = False
            st.session_state.policy_modal_level = None
            st.rerun()


if st.session_state.policy_modal_open:
    _risk_preview_dialog()


# ── Matrix (expander) ───────────────────────────
with st.expander("Matrix · 모든 DB 의 현재 정책", expanded=False):
    _active_map = db.list_active_policies()

    _rows = []
    for _dn in ab.catalog.names():
        _pol = _active_map.get(_dn)
        _lvl = _pol["risk_level"]    if _pol else db.DEFAULT_POLICY["risk_level"]
        _eps = _pol["total_epsilon"] if _pol else db.DEFAULT_POLICY["total_epsilon"]
        _rows.append({
            "DB":         _dn,
            "상태":       ("확정" if _pol else "기본값"),
            "리스크":     f"Risk {_lvl}",
            "총 ε":      _eps,
            "라운드 k":  int(_eps / dp_sim.EPS_PER_QUERY),
            "지원 여부":  "✓" if dp_sim.is_supported(_dn) else "—",
            "확정 시각":  _pol["confirmed_at"] if _pol else "—",
        })
    st.dataframe(pd.DataFrame(_rows), width='stretch', hide_index=True)


# ── History ────────────────────────────────────
with st.expander("History · 확정 이력", expanded=False):
    _hist = db.policy_history(limit=15)
    if not _hist:
        st.info("확정된 정책 이력이 없습니다.")
    else:
        st.dataframe(
            pd.DataFrame(_hist)[
                ["confirmed_at", "db_name", "admin",
                 "risk_level", "total_epsilon", "note"]
            ].rename(columns={
                "confirmed_at":  "확정 시각",
                "db_name":       "DB",
                "admin":         "확정자",
                "risk_level":    "리스크 레벨",
                "total_epsilon": "총 ε",
                "note":          "노트",
            }),
            width='stretch', hide_index=True,
        )