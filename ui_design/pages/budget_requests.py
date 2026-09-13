"""📝 분석가 뷰: 예산 추가 신청 + 내 신청 이력."""
import streamlit as st
from ui import agent_bridge as ab, requests as reqs, state, theme

theme.inject_global_css()
state.apply_active_policy()


# ── 사이드바 컨텍스트 ────────────────────────────────────────
with st.session_state.nav_slot:
    theme.eyebrow("Query Target")
    dom = st.selectbox("도메인", ab.catalog.domains(), key="db_domain",
                       label_visibility="collapsed")
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

    st.markdown("---")
    my = reqs.list_by_user(st.session_state.username)
    n_pending = sum(1 for r in my if r["status"] == "pending")
    theme.eyebrow("My Requests")
    st.markdown(
        f'<div style="font-size:12.5px;color:#0f172a;">'
        f'총 <b>{len(my)}</b>건 · 대기 <b style="color:#b45309;">{n_pending}</b>건</div>',
        unsafe_allow_html=True,
    )


# ── 헤더 ─────────────────────────────────────────────────────
h1, h2 = st.columns([3, 1.4], vertical_alignment="center")
with h1:
    st.markdown('<h1 style="margin:0;">Budget Requests</h1>'
                '<div style="color:#64748b;font-size:14px;">'
                'ε 상한을 다 쓴 경우 관리자에게 예산 증액을 요청합니다.'
                '</div>', unsafe_allow_html=True)
with h2:
    st.markdown(
        f'<div style="text-align:right;">'
        f'{theme.pill(st.session_state.username, "success")}'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

# ── 잔여 예산 안내 게이지 ───────────────────────────────────
eps_cap   = st.session_state.eps_cap
spent     = st.session_state.spent
remaining = max(0.0, eps_cap - spent)
ratio     = spent / max(eps_cap, 1e-9)
tone      = "success" if ratio < 0.6 else ("warning" if ratio < 0.9 else "danger")

st.markdown(
    theme.donut_gauge(
        "현재 상한 대비 소모", spent, eps_cap,
        unit="ε", tone=tone,
        sub=f"잔여 {remaining:.2f} ε · 상한 {eps_cap:.2f} ε",
    ),
    unsafe_allow_html=True,
)

st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

# ── 신청 폼 ─────────────────────────────────────────────────
with st.container(border=True):
    theme.eyebrow("New Request")
    st.markdown(
        '<div style="font-size:14px;color:#0f172a;margin-bottom:12px;">'
        '<b>추가 예산 신청서</b><br/>'
        '<span style="color:#64748b;font-size:12.5px;">'
        '관리자가 검토 후 승인·부분승인·거절 처리합니다.</span></div>',
        unsafe_allow_html=True,
    )
    with st.form("new_req", clear_on_submit=True):
        c1, c2 = st.columns([1, 1])
        with c1:
            # 대상 DB (현재 선택된 것 기본, 변경 가능)
            names = ab.catalog.names()
            default_idx = (names.index(st.session_state.db_name)
                           if st.session_state.db_name in names else 0)
            db_choice = st.selectbox(
                "대상 데이터베이스",
                names, index=default_idx,
                format_func=lambda n: f"{n} · {ab.catalog.meta(n)['title'][:32]}",
                help="현재 콘솔에서 선택한 DB가 기본값입니다. 필요 시 변경하세요.",
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
            "신청 제출", type="primary", width="stretch",
        )
        if submitted:
            if not reason.strip():
                st.error("사유를 입력해주세요.")
            else:
                rid = reqs.create(
                    st.session_state.username, db_choice,
                    float(requested), reason,
                )
                state.log("request", f"#{rid} +{requested:.2f}ε for {db_choice}")
                st.success(f"신청 #{rid} 가 접수되었습니다. 관리자 결재를 기다립니다.")
                st.rerun()

st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

# ── 내 신청 이력 ────────────────────────────────────────────
theme.eyebrow("History · 내 신청 이력")
mine = reqs.list_by_user(st.session_state.username)

if not mine:
    st.markdown(
        '<div style="border:1px dashed #e2e8f0;border-radius:12px;'
        'padding:32px;text-align:center;color:#94a3b8;font-size:14px;">'
        '아직 신청 이력이 없습니다.'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    PILL = {
        "pending":  ("대기", "warning"),
        "approved": ("승인", "success"),
        "partial":  ("부분승인", "primary"),
        "rejected": ("거절", "danger"),
    }
    for r in mine:
        label, tone = PILL[r["status"]]
        appr = (f'{r["approved"]:.2f}' if r["approved"] is not None
                else "—")
        note = r["admin_note"] or ""
        created_short = r["created_at"][5:16].replace("T", " ")
        reviewed_short = (r["reviewed_at"][5:16].replace("T", " ")
                          if r["reviewed_at"] else "")
        reviewed_html = (f'<span>결재 {reviewed_short}</span>'
                        if reviewed_short else "")
        note_html = (f'<div style="font-size:12.5px;color:#0f172a;'
                     f'margin-top:6px;"><b>관리자 노트:</b> '
                     f'<span style="color:#64748b;">{note}</span></div>'
                     if note else "")

        st.markdown(
            f'<div class="dp-req-card">'
            f'  <div class="dp-req-head">'
            f'    <div>'
            f'      <span style="color:#64748b;font-size:11px;font-weight:600;'
            f'letter-spacing:.05em;">#{r["id"]}</span>'
            f'      <span class="dp-req-user" style="margin-left:8px;">'
            f'        {r["db_name"]}</span>'
            f'    </div>'
            f'    {theme.pill(label, tone)}'
            f'  </div>'
            f'  <div class="dp-req-kv">'
            f'    <span>요청 <b>{r["requested"]:.2f}ε</b></span>'
            f'    <span>승인 <b>{appr}ε</b></span>'
            f'    <span>신청 {created_short}</span>'
            f'    {reviewed_html}'
            f'  </div>'
            f'  <div class="dp-req-reason">{r["reason"]}</div>'
            f'  {note_html}'
            f'</div>',
            unsafe_allow_html=True,
        )
