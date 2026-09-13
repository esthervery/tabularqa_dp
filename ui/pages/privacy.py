"""Privacy Policy — 관리자용 (DB x query_type) 정책 실험실.

Renders (위→아래):
  [사이드바 슬롯]
    1) Policy scope    : 도메인/DB/질의유형 selectbox (편집 대상 조합 선택)
    2) My drafts       : 이 관리자가 저장 중인 draft 개수

  [메인]
    3) 헤더       : "Privacy Policy · 실험실" + 부제 + 상태 배지
    4) Currently applied : 이 조합에 지금 적용 중인 정책 (있으면 확정, 없으면 기본값)
    5) Draft parameters  : 4개 슬라이더 (질의당 ε / 기본 상한 / 목표 폭 / step)
                           변경 시 자동으로 db.save_draft() 호출
    6) Lab (실험실)
        · 도넛 게이지 : 누적 소모 / 기본 상한 (draft 값 기준)
        · 막대 게이지 : 다음 라운드 배정 예산
        · 4개 metric  : 질의당 ε / 기본 상한 / 목표 폭 / 라운드 수(수렴 표시)
        · 컨트롤 컨테이너 : [▶ 라운드 실험] [↺ 로그 초기화] + 진행 상황 문구
        · 결과      : ROUNDS 테이블 + Relative Width 그래프 (target 라인 포함)
    7) Confirm 컨테이너   : [✓ 이 조합만 확정] [⇈ 배치 확정 N] [↺ 이 조합 초기화]
                           + 확정 노트 입력
    8) Matrix     : 모든 (DB x query_type) 조합의 현재 정책 요약 dataframe
    9) Draft queue: 아직 확정하지 않은 draft 목록 (개별 확정/삭제 버튼)
   10) History    : 확정 이력 dataframe

핵심 상태 키
    draft_eps, draft_eps_cap, draft_target_rel_width, draft_step
        : 슬라이더가 바인딩되는 로컬 값. 스코프가 바뀌면 다시 seed 된다.
    _policy_loaded_scope : "db/qt" 문자열. 스코프 변경 감지용.
    rounds_by_scope[scope] : 실험실 라운드 로그 (조합별 격리)
"""

import random
import pandas as pd
import streamlit as st
from ui import agent_bridge as ab, db, state, theme
from ui.state import apply_active_policy

theme.inject_global_css()

if not st.session_state.get("is_admin"):
    st.error("이 페이지는 관리자 권한이 필요합니다.")
    st.stop()


ME = st.session_state.username


# ── 사이드바: 편집 대상 스코프 선택 ─────────────────────
with st.session_state.nav_slot:
    st.caption("Policy scope")

    dom = st.selectbox(
        "도메인", ab.catalog.domains(),
        key="db_domain", label_visibility="collapsed",
    )
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
    st.selectbox(
        "Query type", db.QUERY_TYPES, key="query_type",
        format_func=lambda q: {
            "mean":     "평균 (mean)",
            "count":    "카운트 (count)",
            "sum":      "합계 (sum)",
            "variance": "분산 (variance)",
            "max":      "최댓값 (max)",
        }.get(q, q),
    )

    # === 굳이 사이드 바에서 표시할 필요 없을 것 같아서 주석처리===
    # st.divider()
    # st.caption("My drafts")

    # # ===db의 dp_policy 테이블에서 컬럼명 admin이 ME(세션에 저장된 정보)로 되어 있는 정책을 파이썬 dict 형태로 반환===
    # _n_draft = len(db.list_draft_policies(ME))
    # st.write(f"저장된 draft **{_n_draft}**건 (배치 확정 대상)")


# ── 편집 대상 스코프 로컬 변수 ────────────────────────────
DBNAME = st.session_state.db_name
QTYPE  = st.session_state.query_type 
    # 사이드 바에서 설정한 값이 세션 상태로 저장됨.
SCOPE  = f"{DBNAME}/{QTYPE}"

# (db, qt) 의 활성(확정) 정책. 없으면 DEFAULT_POLICY 를 반환. 파이썬 dict 형태
ACTIVE = db.get_active_policy(DBNAME, QTYPE)

# ====이 코드에서 수정된 사항===
# 정책 정보를 db에서 조회해서 ACTIVE로 로드하면, 세션 상태도 ACTIVE에 맞도록 설정해야 함.
apply_active_policy(DBNAME, QTYPE)

# 스코프가 바뀔 때만 draft 슬라이더 값을 DB 에서 다시 로드
if st.session_state.get("_policy_loaded_scope") != SCOPE:
    _d = db.get_draft_policy(ME, DBNAME, QTYPE)
    st.session_state.draft_eps              = float(_d["eps_per_query"])
    st.session_state.draft_eps_cap          = float(_d["eps_cap_default"])
    st.session_state.draft_target_rel_width = float(_d["target_rel_width"])
    st.session_state.draft_step             = float(_d["step"])
    st.session_state._policy_loaded_scope   = SCOPE


def has_diff() -> bool:
    """draft 값이 현재 활성 정책과 다른지."""
    # 페이지를 로드했을 당시 get_active_policy()로 데이터베이스를 조회해서 가져온 결과와 세션 상태값을 비교
    # abs(... - ...) > 1e-9 → 두 값의 차이가 아주 작은 오차(1e-9) 이상이면 다르다고 판단. 
    # 비교하는 네 값 중 하나라도 다르면 전체가 True 처리됨.
    return (
        abs(st.session_state.draft_eps              - ACTIVE["eps_per_query"])    > 1e-9
        or abs(st.session_state.draft_eps_cap      - ACTIVE["eps_cap_default"])  > 1e-9
        or abs(st.session_state.draft_target_rel_width - ACTIVE["target_rel_width"]) > 1e-9
        or abs(st.session_state.draft_step         - ACTIVE["step"])             > 1e-9
    )


# 조합별 라운드 로그 (실험실이 append)
rounds = st.session_state.rounds_by_scope.setdefault(SCOPE, [])


# ── 헤더 ────────────────────────────────────────────────
head_l, head_r = st.columns([3, 1.6], vertical_alignment="center")
with head_l:
    st.title("Privacy Policy · 실험실")
    st.caption(
        "(DB x 질의 유형) 조합별로 상대폭 기반 라운드를 시뮬레이션한 뒤 "
        "만족스러운 값을 **확정** 하면 그 시점부터 분석가에게 적용됩니다."
    )
with head_r:
    st.write(f"🗄️ **DB** · `{DBNAME}`")
    st.write(f"⚙️ **Query type** · `{QTYPE}`")
    if has_diff():
        # 현재 세션에서 정책이 변경된 경우
        st.warning("Draft 변경 있음", icon="✏️")
        # ===디버깅용===
        st.write(f"st.session_state.draft_eps = {st.session_state.draft_eps} / ACTIVE[\"eps_per_query\"] = {ACTIVE["eps_per_query"]}")
        st.write(f"st.session_state.draft_eps_cap = {st.session_state.draft_eps_cap} / ACTIVE[\"eps_cap_default\"] = {ACTIVE["eps_cap_default"]}")
        st.write(f"st.session_state.draft_target_rel_width = {st.session_state.draft_target_rel_width} / ACTIVE[\"target_rel_width\"] = {ACTIVE["target_rel_width"]}")
        st.write(f"st.session_state.draft_step = {st.session_state.draft_step} / ACTIVE[\"step\"] = {ACTIVE["step"]}")
    elif ACTIVE.get("confirmed_at"):
        st.success("확정 정책 적용 중", icon="✅")
    else:
        st.info("시스템 기본값 적용", icon="ℹ️")


# ── 현재 적용 정책 요약 ─────────────────────────────────
with st.container(border=True):
    is_default = ACTIVE.get("confirmed_at") is None
    if is_default:
        st.subheader("Currently applied · 시스템 기본값")
        st.caption(
            f"`{DBNAME} x {QTYPE}` 조합의 확정된 정책이 없어 "
            "DEFAULT_POLICY 가 fallback 으로 적용됩니다."
        )
    else:
        st.subheader(f"Currently applied · 현재 `{DBNAME} x {QTYPE}` 조합의 확정된 운영 정책")
        st.caption(
            f"확정 · {ACTIVE['confirmed_at'].replace('T', ' ')}"
            f" · by {ACTIVE.get('admin') or 'system'}"
        )

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("질의당 ε",   f"{ACTIVE['eps_per_query']:.2f}")
    a2.metric("기본 상한",  f"{ACTIVE['eps_cap_default']:.2f}")
    a3.metric("목표 폭",   f"{ACTIVE['target_rel_width']:.1%}")
    a4.metric("step",     f"x{ACTIVE['step']:.2f}")


# ── Draft 슬라이더 ──────────────────────────────────────
st.subheader(f"Draft parameters · {DBNAME} / {QTYPE}")

s1, s2 = st.columns(2)
with s1:
    st.slider("질의당 ε", 0.25, 2.0,
              key="draft_eps", step=0.25)
    st.slider("기본 상한 ε", 1.0, 50.0,
              key="draft_eps_cap", step=1.0,
              help="신규 분석가 계정의 초기 개인 상한 시드값.")
with s2:
    st.slider("목표 상대폭", 0.005, 0.1,
              key="draft_target_rel_width", step=0.005, format="%.3f")
    st.slider("step 배율", 1.05, 1.5,
              key="draft_step", step=0.01)

# 슬라이더 변화가 있을 때마다 draft 를 DB 에 자동 저장
db.save_draft(
    ME,
    db_name=DBNAME, query_type=QTYPE,
    eps_per_query=st.session_state.draft_eps,
    eps_cap_default=st.session_state.draft_eps_cap,
    target_rel_width=st.session_state.draft_target_rel_width,
    step=st.session_state.draft_step,
)


# ── 실험실: 게이지 ─────────────────────────────────────
st.subheader("Lab · draft 값으로 시뮬레이션")

d_eps  = st.session_state.draft_eps
d_cap  = st.session_state.draft_eps_cap
d_tgt  = st.session_state.draft_target_rel_width
d_step = st.session_state.draft_step

lab_spent = sum(r["alloc"] for r in rounds)
lab_ratio = lab_spent / max(d_cap, 1e-9)
lab_tone  = ("success" if lab_ratio < 0.6
             else ("warning" if lab_ratio < 0.9 else "danger"))
converged = bool(rounds and rounds[-1]["rel_width"] <= d_tgt + 1e-9)
next_alloc = d_eps * (d_step ** len(rounds))

g1, g2 = st.columns(2)
with g1:
    # 시각적 이해가 중요한 곳: SVG 도넛 유지
    st.markdown(
        theme.donut_gauge(
            "누적 소모 / 기본 상한 (draft)", lab_spent, d_cap,
            unit="ε", tone=lab_tone,
            sub=f"잔여 {max(0.0, d_cap-lab_spent):.2f} ε · 질의당 {d_eps:.2f}",
        ),
        unsafe_allow_html=True,
    )
with g2:
    st.markdown(
        theme.bar_gauge(
            f"다음 라운드 배정 (round {len(rounds)+1})",
            next_alloc, d_cap,
            unit="ε", tone="primary",
            sub=f"step ×{d_step:.2f} · target {d_tgt:.1%}",
        ),
        unsafe_allow_html=True,
    )

# 요약 metric 4개 (게이지가 덮지 못하는 값)
k1, k2, k3, k4 = st.columns(4)
k1.metric("질의당 ε",   f"{d_eps:.2f}")
k2.metric("기본 상한 ε", f"{d_cap:.2f}")
k3.metric("목표 상대폭", f"{d_tgt:.1%}")
k4.metric("라운드 수",   len(rounds),
          delta=("수렴 ✓" if converged else None),
          delta_color=("normal" if converged else "off"))


# ── 실험실: 라운드 실행 컨트롤 ─────────────────────────
with st.container(border=True):
    c1, c2, c3 = st.columns([1, 1, 3], vertical_alignment="center")
    with c1:
        if st.button("▶ 라운드 실험", type="primary",
                     width="stretch",
                     disabled=(lab_spent + next_alloc > d_cap + 1e-9)):
            # TODO: run_fixed_k / explore 실제 연결 지점.
            # 지금은 목업으로 step 배율만큼 상대폭이 줄어드는 시뮬레이션.
            prev_rw = rounds[-1]["rel_width"] if rounds else 0.08
            new_rw  = max(d_tgt * 0.9, prev_rw / d_step)
            rounds.append({
                "round":     len(rounds) + 1,
                "alloc":     round(next_alloc, 3),
                "estimate":  round(1000 + random.uniform(-2, 2), 3),
                "rel_width": round(new_rw, 4),
            })
            st.rerun()
    with c2:
        if st.button("↺ 로그 초기화", width="stretch"):
            st.session_state.rounds_by_scope[SCOPE] = []
            st.rerun()
    with c3:
        if converged:
            st.success(f"✓ 목표 상대폭 **{d_tgt:.1%}** 이하 도달. 확정을 고려하세요.")
        elif rounds:
            st.caption(f"현재 상대폭 **{rounds[-1]['rel_width']:.3f}** · "
                       f"목표 **{d_tgt:.3f}**. 라운드를 더 돌려보세요.")
        else:
            st.caption("draft 값으로 상대폭 기반 라운드를 시뮬레이션합니다.")


# ── 실험실: 라운드 로그 & 그래프 ───────────────────────
if rounds:
    df = pd.DataFrame(rounds)
    left, right = st.columns([1.1, 1], gap="medium")
    with left:
        st.caption("Rounds")
        st.dataframe(
            df, width="stretch", hide_index=True,
            column_config={
                "round":     st.column_config.NumberColumn("ROUND",     width="small"),
                "alloc":     st.column_config.NumberColumn("ALLOC ε",   format="%.3f"),
                "estimate":  st.column_config.NumberColumn("ESTIMATE",  format="%.3f"),
                "rel_width": st.column_config.NumberColumn("REL_WIDTH", format="%.4f"),
            },
        )
    with right:
        st.caption("Relative width vs target")
        chart_df = df.set_index("round")[["rel_width"]].copy()
        chart_df["target"] = d_tgt
        st.line_chart(chart_df, width="stretch")
else:
    st.info("아직 실험된 라운드가 없습니다. **▶ 라운드 실험**으로 시작하세요.")


# ── Confirm 블록 ────────────────────────────────────────
with st.container(border=True):
    st.subheader("Confirm · 운영 정책으로 확정")
    st.caption(
        "**이 조합만 확정** — 현재 편집 중인 (DB, 질의유형) 조합만 활성화. "
        "**배치 확정** — 저장된 모든 draft 를 한 번에 활성화."
    )
    note = st.text_input(
        "확정 노트 (선택)",
        placeholder="예) v2 – 평균 질의 상대폭 1% 도달 확인.",
        key="policy_confirm_note",
    )

    c1, c2, c3 = st.columns([1.2, 1.2, 1.2])
    with c1:
        if st.button("✓ 이 조합만 확정", type="primary",
                     width="stretch",
                     disabled=(not has_diff())):
            new_active = db.confirm_draft(
                ME, DBNAME, QTYPE, note=note or None,
            )
            state.log("policy_confirm",
                      f"{DBNAME}/{QTYPE}: eps={new_active['eps_per_query']:.2f}, "
                      f"cap={new_active['eps_cap_default']:.2f}")
            st.session_state.pop("_policy_loaded_scope", None)
            st.success(
                f"`{DBNAME} / {QTYPE}` 이(가) 활성 정책으로 확정되었습니다.",
                icon="✅",
            )
            st.rerun()
    with c2:
        _n_all = len(db.list_draft_policies(ME))
        if st.button(f"⇈ 배치 확정 ({_n_all})",
                     width="stretch",
                     disabled=(_n_all == 0)):
            confirmed = db.confirm_all_drafts(ME, note=note or None)
            state.log("policy_batch_confirm", f"{len(confirmed)} drafts")
            st.session_state.pop("_policy_loaded_scope", None)
            st.success(f"{len(confirmed)}개 draft 가 일괄 확정되었습니다.",
                       icon="✅")
            st.rerun()
    with c3:
        if st.button("↺ 이 조합 초기화", width="stretch"):
            db.discard_draft(ME, DBNAME, QTYPE)
            st.session_state.pop("_policy_loaded_scope", None)
            st.rerun()

    if not has_diff():
        st.caption("이 조합의 draft 값이 활성 정책과 동일합니다.")


# ── Matrix 뷰 ────────────────────────────────────────────
st.subheader("Matrix · 모든 조합의 현재 정책")
_active_map = db.list_active_policies()
_draft_map  = {(d["db_name"], d["query_type"]): d
               for d in db.list_draft_policies(ME)}

_rows = []
for _dn in ab.catalog.names():
    for _qt in db.QUERY_TYPES:
        _key = (_dn, _qt)
        _pol = _active_map.get(_key)
        _status = "확정" if _pol else "기본값"
        if _key in _draft_map:
            _status += " · draft"
        _rows.append({
            "DB":       _dn,
            "질의유형":  _qt,
            "상태":     _status,
            "질의당 ε": _pol["eps_per_query"]    if _pol else db.DEFAULT_POLICY["eps_per_query"],
            "기본 상한":_pol["eps_cap_default"]  if _pol else db.DEFAULT_POLICY["eps_cap_default"],
            "목표 폭":  _pol["target_rel_width"] if _pol else db.DEFAULT_POLICY["target_rel_width"],
            "step":    _pol["step"]             if _pol else db.DEFAULT_POLICY["step"],
            "확정 시각":_pol["confirmed_at"]     if _pol else "—",
        })
st.dataframe(pd.DataFrame(_rows), width="stretch", hide_index=True)


# ── Draft queue ──────────────────────────────────────────
st.subheader("Draft queue · 미확정 항목")
drafts = db.list_draft_policies(ME)
if not drafts:
    st.info("저장된 draft 가 없습니다.")
else:
    for d in drafts:
        with st.container(border=True):
            cA, cB, cC = st.columns([3, 1, 1])
            with cA:
                st.write(
                    f"**{d['db_name']}** · `{d['query_type']}` · "
                    f"ε={d['eps_per_query']:.2f}, cap={d['eps_cap_default']:.2f}, "
                    f"tgt={d['target_rel_width']:.1%}, step ×{d['step']:.2f}"
                )
            with cB:
                if st.button("✓ 확정",
                             key=f"cf_{d['db_name']}_{d['query_type']}",
                             width="stretch", type="primary"):
                    db.confirm_draft(ME, d["db_name"], d["query_type"])
                    st.session_state.pop("_policy_loaded_scope", None)
                    st.rerun()
            with cC:
                if st.button("삭제",
                             key=f"dl_{d['db_name']}_{d['query_type']}",
                             width="stretch"):
                    db.discard_draft(ME, d["db_name"], d["query_type"])
                    st.session_state.pop("_policy_loaded_scope", None)
                    st.rerun()


# ── 확정 이력 ────────────────────────────────────────────
st.subheader("History · 확정 이력")
_hist = db.policy_history(limit=15)
if not _hist:
    st.info("확정된 정책 이력이 없습니다.")
else:
    st.dataframe(
        pd.DataFrame(_hist)[
            ["confirmed_at", "db_name", "query_type", "admin",
             "eps_per_query", "eps_cap_default",
             "target_rel_width", "step", "note"]
        ].rename(columns={
            "confirmed_at":     "확정 시각",
            "db_name":          "DB",
            "query_type":       "질의유형",
            "admin":            "확정자",
            "eps_per_query":    "질의당 ε",
            "eps_cap_default":  "기본 상한",
            "target_rel_width": "목표 폭",
            "step":             "step",
            "note":             "노트",
        }),
        width="stretch", hide_index=True,
    )
