"""관리자 뷰: 예산 신청 결재 큐 + 승인 이력 타임라인 + 접근 로그.

기존 audit.py 는 액세스 로그만 있었으나, 요구사항에 따라
'예산 신청 결재' 워크플로우가 주된 기능이 된다.
"""
import streamlit as st
from ui import requests as reqs, state, theme

theme.inject_global_css()

if not st.session_state.get("is_admin"):
    st.error("이 페이지는 관리자 권한이 필요한 페이지입니다.")
    st.stop()

state.apply_active_policy()


# ── 사이드바 필터 ────────────────────────────────────────────
with st.session_state.nav_slot:
    theme.eyebrow("Filters")
    status = st.selectbox(
        "상태",
        ["전체", "pending", "approved", "partial", "rejected"],
        format_func=lambda s: {
            "전체": "전체",
            "pending": "대기",
            "approved": "승인",
            "partial": "부분승인",
            "rejected": "거절",
        }.get(s, s),
        key="req_filter_status",
    )
    user_q = st.text_input(
        "사용자 검색",
        placeholder="아이디 일부",
        key="req_filter_user",
    )
    st.markdown("---")

    s = reqs.stats()
    theme.eyebrow("Snapshot")
    st.markdown(
        f'<div style="font-size:12.5px;line-height:1.9;">'
        f'<div>대기 <b style="color:#b45309;float:right;">{s["pending"]}</b></div>'
        f'<div>승인 <b style="color:#047857;float:right;">{s["approved"]}</b></div>'
        f'<div>부분승인 <b style="color:#4338ca;float:right;">{s["partial"]}</b></div>'
        f'<div>거절 <b style="color:#be123c;float:right;">{s["rejected"]}</b></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── 헤더 ─────────────────────────────────────────────────────
h1, h2 = st.columns([3, 1.2], vertical_alignment="center")
with h1:
    st.markdown('<h1 style="margin:0;">Audit &nbsp;·&nbsp; 예산 결재</h1>'
                '<div style="color:#64748b;font-size:14px;">'
                '분석가의 ε 예산 증액 신청을 검토·조정·결재합니다.'
                '</div>', unsafe_allow_html=True)
with h2:
    st.markdown(
        f'<div style="text-align:right;">'
        f'{theme.pill("🛡️ Admin · " + st.session_state.username, "primary")}'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

# ── KPI ──────────────────────────────────────────────────────
stat = reqs.stats()
c1, c2, c3, c4 = st.columns(4)
c1.metric("대기 큐",   stat["pending"],  border=True)
c2.metric("승인 완료", stat["approved"] + stat["partial"], border=True)
c3.metric("거절",     stat["rejected"], border=True)
c4.metric("총 신청",   sum(stat.values()), border=True)

st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

# ── 탭 ───────────────────────────────────────────────────────
tab_queue, tab_hist, tab_access = st.tabs(
    ["📥 대기 큐", "🕓 결재 타임라인", "🔍 액세스 로그"]
)

# ── 대기 큐 ─────────────────────────────────────────────────
with tab_queue:
    items = reqs.list_all(status="pending", user=user_q or None)
    if not items:
        st.markdown(
            '<div style="border:1px dashed #e2e8f0;border-radius:12px;'
            'padding:32px;text-align:center;color:#94a3b8;font-size:14px;">'
            '검토 대기 중인 신청이 없습니다.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        for r in items:
            with st.container(border=True):
                head_l, head_r = st.columns([3, 1.2],
                                            vertical_alignment="center")
                with head_l:
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;">'
                        f'<span style="color:#64748b;font-size:11px;'
                        f'font-weight:600;letter-spacing:.05em;">'
                        f'#{r["id"]}</span>'
                        f'<span style="font-weight:600;font-size:15px;">'
                        f'{r["username"]}</span>'
                        f'<span style="color:#64748b;font-size:12px;">'
                        f'· {r["db_name"]}</span>'
                        f'</div>'
                        f'<div style="color:#94a3b8;font-size:11.5px;'
                        f'margin-top:3px;">신청 · '
                        f'{r["created_at"].replace("T", " ")}</div>',
                        unsafe_allow_html=True,
                    )
                with head_r:
                    req_amt = float(r["requested"])
                    st.markdown(
                        f'<div style="text-align:right;">'
                        f'{theme.pill(f"요청 {req_amt:.2f} ε", "warning")}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    f'<div class="dp-req-reason">{r["reason"]}</div>',
                    unsafe_allow_html=True,
                )

                # 결재 컨트롤
                dec_l, dec_r = st.columns([2, 1], gap="medium")
                with dec_l:
                    approved = st.slider(
                        "승인 금액 (ε)",
                        0.0, max(r["requested"] * 1.5, 1.0),
                        value=float(r["requested"]),
                        step=0.25,
                        key=f"appr_{r['id']}",
                        help="부분 승인 시 요청보다 낮은 값을 설정하세요.",
                    )
                    note = st.text_input(
                        "관리자 노트 (선택)",
                        key=f"note_{r['id']}",
                        placeholder="결재 사유를 남기면 신청자에게 함께 전달됩니다.",
                    )
                with dec_r:
                    st.markdown("<div style='height:24px;'></div>",
                                unsafe_allow_html=True)
                    if st.button("✓ 승인", type="primary",
                                 key=f"ok_{r['id']}",
                                 width="stretch"):
                        st.session_state[f"_decide_{r['id']}"] = "approved"
                    if st.button("✕ 거절",
                                 key=f"no_{r['id']}",
                                 width="stretch"):
                        st.session_state[f"_decide_{r['id']}"] = "rejected"

                # 결재 처리
                dec = st.session_state.pop(f"_decide_{r['id']}", None)
                if dec == "approved":
                    status = ("partial"
                              if approved + 1e-9 < r["requested"]
                              else "approved")
                    reqs.decide(r["id"],
                                reviewer=st.session_state.username,
                                status=status,
                                approved=float(approved),
                                note=note)
                    state.log("approve", f"#{r['id']} → {status} {approved:.2f}ε")
                    st.success(
                        f"#{r['id']} · {r['username']} 에게 "
                        f"{approved:.2f} ε 을 {'부분 승인' if status=='partial' else '승인'} 했습니다."
                    )
                    st.rerun()
                elif dec == "rejected":
                    reqs.decide(r["id"],
                                reviewer=st.session_state.username,
                                status="rejected",
                                approved=0.0, note=note)
                    state.log("reject", f"#{r['id']} 거절")
                    st.warning(f"#{r['id']} · {r['username']} 의 신청을 거절했습니다.")
                    st.rerun()


# ── 결재 타임라인 ────────────────────────────────────────────
with tab_hist:
    items = reqs.list_all(
        status=None if status == "전체" else status,
        user=user_q or None,
    )
    # 이미 결재된 것만
    decided = [r for r in items if r["status"] != "pending"]
    # 최근 결재 순
    decided.sort(key=lambda r: r["reviewed_at"] or "", reverse=True)

    if not decided:
        st.markdown(
            '<div style="border:1px dashed #e2e8f0;border-radius:12px;'
            'padding:32px;text-align:center;color:#94a3b8;font-size:14px;">'
            '해당 조건의 결재 이력이 없습니다.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="dp-timeline">', unsafe_allow_html=True)
        LABEL = {"approved": ("승인", "approved"),
                 "partial":  ("부분 승인", "partial"),
                 "rejected": ("거절", "rejected")}
        for r in decided:
            lbl, cls = LABEL[r["status"]]
            appr = (f'{r["approved"]:.2f} ε' if r["approved"]
                    else "—")
            when = (r["reviewed_at"] or "").replace("T", " ")
            note = r["admin_note"] or ""
            note_html = (f'<div style="color:#64748b;font-size:12.5px;'
                         f'margin-top:4px;">"{note}"</div>' if note else "")
            st.markdown(
                f'<div class="dp-timeline-item {cls}">'
                f'  <div class="dp-timeline-time">{when} · '
                f'#{r["id"]} · reviewer <b>{r["reviewer"] or "-"}</b></div>'
                f'  <div class="dp-timeline-body">'
                f'    <b>{r["username"]}</b> · <span style="color:#64748b;">'
                f'{r["db_name"]}</span> · {lbl} · '
                f'요청 {r["requested"]:.2f} ε → 확정 <b>{appr}</b>'
                f'  </div>'
                f'  {note_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)


# ── 액세스 로그 (기존 audit 유지) ───────────────────────────
with tab_access:
    import pandas as pd
    if st.session_state.audit:
        df = pd.DataFrame(st.session_state.audit)
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.markdown(
            '<div style="border:1px dashed #e2e8f0;border-radius:12px;'
            'padding:24px;text-align:center;color:#94a3b8;font-size:14px;">'
            '아직 액세스 기록이 없습니다.'
            '</div>',
            unsafe_allow_html=True,
        )
