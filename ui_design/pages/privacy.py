"""관리자 · Privacy Policy 콘솔 (per (DB x Query type)).

- 상단에서 (DB, 질의유형) 조합을 고른 뒤 그 조합의 draft 를 편집.
- 그 아래 "실험실" 에서 라운드를 돌려 상대폭을 시뮬레이션.
- 조합별 [확정] 또는 [배치 확정] 지원.
- 확정되지 않은 조합은 시스템 기본값(DEFAULT_POLICY) 으로 자동 fallback.
"""
import random
import pandas as pd
import streamlit as st
from ui_design import agent_bridge as ab, db, state, theme

theme.inject_global_css()

if not st.session_state.get("is_admin"):
    st.error("이 페이지는 관리자 권한이 필요합니다.")
    st.stop()

ME = st.session_state.username


# ── 사이드바: 이 페이지의 정책 대상 스코프 선택 ─────────────
with st.session_state.nav_slot:
    theme.eyebrow("Policy scope")

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

    st.markdown("---")
    n_draft = len(db.list_draft_policies(ME))
    theme.eyebrow("My drafts")
    st.markdown(
        f'<div style="font-size:12.5px;">'
        f'저장된 draft <b>{n_draft}</b>건 (배치 확정 대상)</div>',
        unsafe_allow_html=True,
    )


DBNAME = st.session_state.db_name
QTYPE  = st.session_state.query_type
SCOPE  = f"{DBNAME}/{QTYPE}"

ACTIVE = db.get_active_policy(DBNAME, QTYPE)


# ── draft 값 세션 seed (조합이 바뀔 때만 재로드) ─────────────
if st.session_state.get("_policy_loaded_scope") != SCOPE:
    d = db.get_draft_policy(ME, DBNAME, QTYPE)
    st.session_state.draft_eps              = float(d["eps_per_query"])
    st.session_state.draft_eps_cap          = float(d["eps_cap_default"])
    st.session_state.draft_target_rel_width = float(d["target_rel_width"])
    st.session_state.draft_step             = float(d["step"])
    st.session_state._policy_loaded_scope   = SCOPE


def _has_diff() -> bool:
    return (
        abs(st.session_state.draft_eps              - ACTIVE["eps_per_query"])    > 1e-9
        or abs(st.session_state.draft_eps_cap      - ACTIVE["eps_cap_default"])  > 1e-9
        or abs(st.session_state.draft_target_rel_width - ACTIVE["target_rel_width"]) > 1e-9
        or abs(st.session_state.draft_step         - ACTIVE["step"])             > 1e-9
    )


# 조합별 라운드 로그
rounds = st.session_state.rounds_by_scope.setdefault(SCOPE, [])


# ── 헤더 ─────────────────────────────────────────────────────
h1, h2 = st.columns([3, 1.6], vertical_alignment="center")
with h1:
    st.markdown('<h1 style="margin:0;">Privacy Policy · 실험실</h1>'
                '<div style="color:#64748b;font-size:14px;">'
                '(DB × 질의 유형) 조합별로 상대폭 기반 라운드를 시뮬레이션한 뒤 '
                '만족스러운 값을 <b>확정</b> 하면 그 시점부터 분석가에게 적용됩니다.'
                '</div>', unsafe_allow_html=True)
with h2:
    tone  = "warning" if _has_diff() else ("primary"
             if ACTIVE.get("confirmed_at") else "muted")
    label = ("Draft 변경 있음" if _has_diff()
             else ("확정 정책" if ACTIVE.get("confirmed_at")
                   else "시스템 기본값 사용 중"))
    st.markdown(
        f'<div style="text-align:right;display:flex;flex-direction:column;'
        f'gap:6px;align-items:flex-end;">'
        f'  {theme.pill(f"🗄️ {DBNAME}", "primary")}'
        f'  {theme.pill(f"⚙ {QTYPE}", "muted")}'
        f'  {theme.pill(label, tone)}'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)


# ── 현재 적용 정책 배지 ─────────────────────────────────────
is_default = ACTIVE.get("confirmed_at") is None
active_when = (ACTIVE["confirmed_at"].replace("T", " ")
               if ACTIVE.get("confirmed_at") else "—")
active_by   = ACTIVE.get("admin") or "system"

st.markdown(
    f'<div style="border:1px solid #e2e8f0;border-radius:12px;'
    f'padding:14px 16px;background:{"#f8fafc" if is_default else "white"};">'
    f'  <div style="display:flex;justify-content:space-between;align-items:center;">'
    f'    <div>'
    f'      <div class="dp-eyebrow" style="margin:0;">'
    f'        Currently applied · {DBNAME} / {QTYPE}</div>'
    f'      <div style="font-size:15px;font-weight:600;margin-top:2px;">'
    f'        {("시스템 기본값 (fallback)" if is_default else "확정된 운영 정책")}'
    f'      </div>'
    f'      <div style="font-size:12px;color:#64748b;margin-top:2px;">'
    f'        {("이 조합의 확정 정책이 없어 DEFAULT_POLICY 가 적용됩니다."
                if is_default else f"확정 · {active_when} · by {active_by}")}'
    f'      </div>'
    f'    </div>'
    f'    <div style="display:flex;gap:20px;font-variant-numeric:tabular-nums;font-size:13px;">'
    f'      <div><span style="color:#64748b;">질의당 ε </span>'
    f'           <b>{ACTIVE["eps_per_query"]:.2f}</b></div>'
    f'      <div><span style="color:#64748b;">기본 상한 </span>'
    f'           <b>{ACTIVE["eps_cap_default"]:.2f}</b></div>'
    f'      <div><span style="color:#64748b;">목표 폭 </span>'
    f'           <b>{ACTIVE["target_rel_width"]:.1%}</b></div>'
    f'      <div><span style="color:#64748b;">step </span>'
    f'           <b>×{ACTIVE["step"]:.2f}</b></div>'
    f'    </div>'
    f'  </div>'
    f'</div>',
    unsafe_allow_html=True,
)


# ── Draft 슬라이더 ──────────────────────────────────────────
st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
theme.eyebrow(f"Draft parameters · {DBNAME} / {QTYPE}")

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

# 슬라이더 변경분 자동 저장 (draft 로)
db.save_draft(
    ME,
    db_name=DBNAME, query_type=QTYPE,
    eps_per_query=st.session_state.draft_eps,
    eps_cap_default=st.session_state.draft_eps_cap,
    target_rel_width=st.session_state.draft_target_rel_width,
    step=st.session_state.draft_step,
)


# ── 실험실: 게이지 + 메트릭 ────────────────────────────────
st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
theme.eyebrow("Lab · draft 값으로 시뮬레이션")

d_eps  = st.session_state.draft_eps
d_cap  = st.session_state.draft_eps_cap
d_tgt  = st.session_state.draft_target_rel_width
d_step = st.session_state.draft_step

# 이 실험에서의 누적 소비 ε (라운드마다 alloc 만큼 소비했다고 가정)
lab_spent = sum(r["alloc"] for r in rounds)
ratio     = lab_spent / max(d_cap, 1e-9)
tone      = ("success" if ratio < 0.6
             else ("warning" if ratio < 0.9 else "danger"))

# 마지막 라운드의 상대폭이 목표 이하로 내려갔는지
converged = bool(rounds and rounds[-1]["rel_width"] <= d_tgt + 1e-9)

g1, g2 = st.columns(2)
with g1:
    st.markdown(
        theme.donut_gauge(
            "누적 소모 / 기본 상한 (draft)", lab_spent, d_cap,
            unit="ε", tone=tone,
            sub=f"잔여 {max(0.0, d_cap-lab_spent):.2f} ε · 질의당 {d_eps:.2f}",
        ),
        unsafe_allow_html=True,
    )
with g2:
    # 다음 라운드 배정 예산 = d_eps * step^(k)
    next_alloc = d_eps * (d_step ** len(rounds))
    st.markdown(
        theme.bar_gauge(
            f"다음 라운드 배정 (round {len(rounds)+1})",
            next_alloc, d_cap,
            unit="ε", tone="primary",
            sub=f"step ×{d_step:.2f} · target {d_tgt:.1%}",
        ),
        unsafe_allow_html=True,
    )

k1, k2, k3, k4 = st.columns(4)
k1.metric("질의당 ε",   f"{d_eps:.2f}",   border=True)
k2.metric("기본 상한 ε", f"{d_cap:.2f}",   border=True)
k3.metric("목표 상대폭", f"{d_tgt:.1%}",   border=True)
k4.metric("라운드 수",   len(rounds),      border=True,
          delta=("수렴 ✓" if converged else None),
          delta_color=("normal" if converged else "off"))


# ── 실험실: 라운드 실행 컨트롤 ─────────────────────────────
st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

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
            st.markdown(
                f'<div style="color:#047857;font-size:13px;">'
                f'✓ 목표 상대폭 <b>{d_tgt:.1%}</b> 이하 도달. 확정을 고려하세요.'
                f'</div>',
                unsafe_allow_html=True,
            )
        elif rounds:
            st.markdown(
                f'<div style="color:#64748b;font-size:13px;">'
                f'현재 상대폭 <b>{rounds[-1]["rel_width"]:.3f}</b> · '
                f'목표 <b>{d_tgt:.3f}</b>. 라운드를 더 돌려보세요.'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="color:#94a3b8;font-size:13px;">'
                'draft 값으로 상대폭 기반 라운드를 시뮬레이션합니다.'
                '</div>',
                unsafe_allow_html=True,
            )

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)


# ── 실험실: 라운드 로그 & 그래프 ───────────────────────────
if rounds:
    df = pd.DataFrame(rounds)
    left, right = st.columns([1.1, 1], gap="medium")
    with left:
        theme.eyebrow("Rounds")
        st.dataframe(
            df, width="stretch", hide_index=True,
            column_config={
                "round":     st.column_config.NumberColumn("ROUND", width="small"),
                "alloc":     st.column_config.NumberColumn("ALLOC ε",  format="%.3f"),
                "estimate":  st.column_config.NumberColumn("ESTIMATE", format="%.3f"),
                "rel_width": st.column_config.NumberColumn("REL_WIDTH", format="%.4f"),
            },
        )
    with right:
        theme.eyebrow("Relative width vs target")
        chart_df = df.set_index("round")[["rel_width"]].copy()
        chart_df["target"] = d_tgt
        st.line_chart(chart_df, width="stretch")
else:
    st.markdown(
        '<div style="border:1px dashed #e2e8f0;border-radius:12px;'
        'padding:32px;text-align:center;color:#94a3b8;font-size:14px;">'
        '아직 실험된 라운드가 없습니다. <b>▶ 라운드 실험</b>으로 시작하세요.'
        '</div>',
        unsafe_allow_html=True,
    )


# ── 확정 / 초기화 / 배치 확정 ───────────────────────────────
st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown(
        '<div class="dp-eyebrow" style="margin:0;">Confirm</div>'
        '<div style="font-size:14px;color:#0f172a;font-weight:600;margin:2px 0 8px 0;">'
        '실험 결과를 운영 정책으로 확정</div>'
        '<div style="font-size:12.5px;color:#64748b;margin-bottom:10px;">'
        '<b>이 조합만 확정</b> · 현재 편집 중인 (DB, 질의유형) 조합만 활성화합니다.<br/>'
        '<b>배치 확정</b> · 저장된 모든 draft 를 한 번에 활성화합니다.'
        '</div>',
        unsafe_allow_html=True,
    )
    note = st.text_input(
        "확정 노트 (선택)",
        placeholder="예) v2 – 평균 질의 상대폭 1% 도달 확인.",
        key="policy_confirm_note",
    )
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 2],
                                 vertical_alignment="center")
    with c1:
        if st.button("✓ 이 조합만 확정", type="primary", width="stretch",
                     disabled=(not _has_diff())):
            new_active = db.confirm_draft(
                ME, DBNAME, QTYPE, note=note or None,
            )
            state.log("policy_confirm",
                      f"{DBNAME}/{QTYPE}: eps={new_active['eps_per_query']:.2f}, "
                      f"cap={new_active['eps_cap_default']:.2f}")
            st.session_state.pop("_policy_loaded_scope", None)
            st.success(
                f"{DBNAME} / {QTYPE} 조합이 활성 정책으로 확정되었습니다.",
                icon="✅",
            )
            st.rerun()
    with c2:
        n_all = len(db.list_draft_policies(ME))
        if st.button(f"⇈ 배치 확정 ({n_all})", width="stretch",
                     disabled=(n_all == 0)):
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
    with c4:
        if not _has_diff():
            st.markdown(
                '<div style="color:#94a3b8;font-size:12.5px;text-align:right;">'
                '이 조합의 draft 값이 활성 정책과 동일합니다.'
                '</div>',
                unsafe_allow_html=True,
            )


# ── 매트릭스 뷰 ──────────────────────────────────────────────
st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
theme.eyebrow("Matrix · 모든 조합의 현재 정책")

active_map = db.list_active_policies()
draft_map  = {(d["db_name"], d["query_type"]): d
              for d in db.list_draft_policies(ME)}

rows_matrix = []
for dname in ab.catalog.names():
    for qt in db.QUERY_TYPES:
        key = (dname, qt)
        pol = active_map.get(key)
        status = "확정" if pol else "기본값"
        if key in draft_map:
            status += " · draft"
        rows_matrix.append({
            "DB":         dname,
            "질의유형":     qt,
            "상태":        status,
            "질의당 ε":    pol["eps_per_query"]    if pol else db.DEFAULT_POLICY["eps_per_query"],
            "기본 상한":   pol["eps_cap_default"]  if pol else db.DEFAULT_POLICY["eps_cap_default"],
            "목표 폭":     pol["target_rel_width"] if pol else db.DEFAULT_POLICY["target_rel_width"],
            "step":       pol["step"]             if pol else db.DEFAULT_POLICY["step"],
            "확정 시각":   pol["confirmed_at"]     if pol else "—",
        })
st.dataframe(pd.DataFrame(rows_matrix),
             width="stretch", hide_index=True)


# ── 미확정 draft 큐 ─────────────────────────────────────────
st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
theme.eyebrow("Draft queue · 미확정 항목")

drafts = db.list_draft_policies(ME)
if not drafts:
    st.markdown(
        '<div style="border:1px dashed #e2e8f0;border-radius:12px;'
        'padding:24px;text-align:center;color:#94a3b8;font-size:13.5px;">'
        '저장된 draft 가 없습니다.'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    for d in drafts:
        cA, cB, cC = st.columns([3, 1, 1])
        with cA:
            st.markdown(
                f'<div style="font-size:13.5px;">'
                f'<b>{d["db_name"]}</b> · {d["query_type"]} · '
                f'ε={d["eps_per_query"]:.2f}, cap={d["eps_cap_default"]:.2f}, '
                f'tgt={d["target_rel_width"]:.1%}, step ×{d["step"]:.2f}'
                f'</div>',
                unsafe_allow_html=True,
            )
        with cB:
            if st.button("✓ 확정", key=f"cf_{d['db_name']}_{d['query_type']}",
                         width="stretch", type="primary"):
                db.confirm_draft(ME, d["db_name"], d["query_type"])
                st.session_state.pop("_policy_loaded_scope", None)
                st.rerun()
        with cC:
            if st.button("삭제", key=f"dl_{d['db_name']}_{d['query_type']}",
                         width="stretch"):
                db.discard_draft(ME, d["db_name"], d["query_type"])
                st.session_state.pop("_policy_loaded_scope", None)
                st.rerun()


# ── 확정 이력 ────────────────────────────────────────────────
st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
theme.eyebrow("History · 확정 이력")

hist = db.policy_history(limit=15)
if not hist:
    st.markdown(
        '<div style="border:1px dashed #e2e8f0;border-radius:12px;'
        'padding:24px;text-align:center;color:#94a3b8;font-size:13.5px;">'
        '확정된 정책 이력이 없습니다.'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    st.dataframe(
        pd.DataFrame(hist)[
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