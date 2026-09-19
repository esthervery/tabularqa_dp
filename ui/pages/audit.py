# """Audit · 예산 결재 — 관리자용.

# Renders (위→아래):
#   [사이드바 슬롯]
#     1) Filters   : 상태(pending/approved/...) + 사용자 아이디 부분 검색
#     2) Snapshot  : 상태별 카운트 (대기/승인/부분승인/거절)

#   [메인]
#     3) 헤더    : "Audit · 예산 결재" + Admin 표시
#     4) KPI 4개 : 대기 / 승인 완료 / 거절 / 총 신청
#     5) 3-탭
#         📥 대기            : pending 신청들. 각 항목마다 승인금액 슬라이더 + [✓ 승인] [✕ 거절]
#         🕓 결재 타임라인    : 이미 결재된 항목들을 최근순 컨테이너 리스트
#         🔍 액세스 로그      : session-local audit 로그 dataframe

# 핵심 상태 키
#     _decide_<req_id> : "approved" | "rejected" — 승인/거절 버튼이 다음 rerun 에
#                        처리하도록 남겨두는 트랜지언트 플래그
# """
# import pandas as pd
# import streamlit as st
# from ui import requests as reqs, state, theme

# theme.inject_global_css()

# if not st.session_state.get("is_admin"):
#     st.error("이 페이지는 관리자 권한이 필요한 페이지입니다.")
#     st.stop()

# state.apply_active_policy()


# # ── 사이드바 필터 & 스냅샷 ────────────────────────────
# with st.session_state.nav_slot:
#     st.caption("Filters")
#     status = st.selectbox(
#         "상태",
#         ["전체", "pending", "approved", "partial", "rejected"],
#         format_func=lambda s: {
#             "전체": "전체",
#             "pending": "대기",
#             "approved": "승인",
#             "partial": "부분승인",
#             "rejected": "거절",
#         }.get(s, s),
#         key="req_filter_status",
#     )
#     user_q = st.text_input(
#         "사용자 검색", placeholder="아이디 일부", key="req_filter_user",
#     )

#     st.divider()
#     st.caption("Snapshot")
#     _s = reqs.stats()
#     st.write(f"대기 · **{_s['pending']}**")
#     st.write(f"승인 · **{_s['approved']}**")
#     st.write(f"부분승인 · **{_s['partial']}**")
#     st.write(f"거절 · **{_s['rejected']}**")


# # ── 헤더 ────────────────────────────────────────────
# head_l, head_r = st.columns([3, 1.2], vertical_alignment="center")
# with head_l:
#     st.title("Audit · 예산 결재")
#     st.caption("분석가의 ε 예산 증액 신청을 검토·조정·결재합니다.")
# with head_r:
#     st.write(f"🛡️ **Admin** · {st.session_state.username}")


# # ── KPI ─────────────────────────────────────────────
# stat = reqs.stats()
# c1, c2, c3, c4 = st.columns(4)
# c1.metric("대기",   stat["pending"])
# c2.metric("승인 완료", stat["approved"] + stat["partial"])
# c3.metric("거절",     stat["rejected"])
# c4.metric("총 신청",   sum(stat.values()))


# # ── 탭 ───────────────────────────────────────────────
# tab_queue, tab_hist, tab_access = st.tabs(
#     ["📥 대기", "🕓 결재 타임라인", "🔍 액세스 로그"]
# )


# # ── 탭 1: 대기 큐 ────────────────────────────────────
# def _render_pending_item(r: dict) -> None:
#     """대기 큐의 한 항목 카드 렌더링. 승인/거절 처리까지 포함."""
#     with st.container(border=True):
#         head_l, head_r = st.columns([3, 1.2], vertical_alignment="center")
#         with head_l:
#             st.write(
#                 f"**#{r['id']}** · **{r['username']}** · `{r['db_name']}`"
#             )
#             st.caption(f"신청 · {r['created_at'].replace('T', ' ')}")
#         with head_r:
#             st.warning(f"요청 {float(r['requested']):.2f} ε")

#         st.info(r["reason"])

#         # 결재 컨트롤
#         dec_l, dec_r = st.columns([2, 1], gap="medium")
#         with dec_l:
#             approved = st.slider(
#                 "승인 금액 (ε)",
#                 0.0, max(r["requested"] * 1.5, 1.0),
#                 value=float(r["requested"]), step=0.25,
#                 key=f"appr_{r['id']}",
#                 help="부분 승인 시 요청보다 낮은 값을 설정하세요.",
#             )
#             note = st.text_input(
#                 "관리자 노트 (선택)",
#                 key=f"note_{r['id']}",
#                 placeholder="결재 사유를 남기면 신청자에게 함께 전달됩니다.",
#             )
#         with dec_r:
#             # 상단 여백 맞추기용 caption
#             st.caption(" ")
#             if st.button("✓ 승인", type="primary",
#                          key=f"ok_{r['id']}", width="stretch"):
#                 st.session_state[f"_decide_{r['id']}"] = "approved"
#             if st.button("✕ 거절",
#                          key=f"no_{r['id']}", width="stretch"):
#                 st.session_state[f"_decide_{r['id']}"] = "rejected"

#         # 승인/거절 후처리 (다음 rerun 에서 실행)
#         _apply_decision(r, approved, note)


# def _apply_decision(r: dict, approved: float, note: str) -> None:
#     """직전 클릭이 세팅한 _decide_ 플래그를 소비해 실제 결재를 수행."""
#     dec = st.session_state.pop(f"_decide_{r['id']}", None)
#     if dec == "approved":
#         status = "partial" if approved + 1e-9 < r["requested"] else "approved"
#         reqs.decide(r["id"],
#                     reviewer=st.session_state.username,
#                     status=status, approved=float(approved), note=note)
#         state.log("approve", f"#{r['id']} → {status} {approved:.2f}ε")
#         st.success(
#             f"#{r['id']} · {r['username']} 에게 {approved:.2f} ε 을 "
#             f"{'부분 승인' if status == 'partial' else '승인'} 했습니다."
#         )
#         st.rerun()
#     elif dec == "rejected":
#         reqs.decide(r["id"],
#                     reviewer=st.session_state.username,
#                     status="rejected", approved=0.0, note=note)
#         state.log("reject", f"#{r['id']} 거절")
#         st.warning(f"#{r['id']} · {r['username']} 의 신청을 거절했습니다.")
#         st.rerun()


# with tab_queue:
#     _items = reqs.list_all(status="pending", user=user_q or None)
#     if not _items:
#         st.info("검토 대기 중인 신청이 없습니다.")
#     else:
#         for _r in _items:
#             _render_pending_item(_r)


# # ── 탭 2: 결재 타임라인 ──────────────────────────────
# def _render_timeline(items: list[dict]) -> None:
#     """결재 완료 항목을 최근순으로 컨테이너 카드로 나열."""
#     for r in items:
#         with st.container(border=True):
#             lbl = {"approved": "✅ 승인",
#                    "partial":  "🟡 부분 승인",
#                    "rejected": "❌ 거절"}[r["status"]]
#             when = (r["reviewed_at"] or "").replace("T", " ")
#             appr = f"{r['approved']:.2f} ε" if r["approved"] else "—"

#             st.write(
#                 f"**{lbl}** · #{r['id']} · **{r['username']}** · "
#                 f"`{r['db_name']}` · 요청 {r['requested']:.2f} ε → 확정 **{appr}**"
#             )
#             st.caption(f"{when} · reviewer: {r['reviewer'] or '-'}")
#             if r["admin_note"]:
#                 st.caption(f"관리자 노트 — \"{r['admin_note']}\"")


# with tab_hist:
#     _all = reqs.list_all(
#         status=None if status == "전체" else status,
#         user=user_q or None,
#     )
#     _decided = [r for r in _all if r["status"] != "pending"]
#     _decided.sort(key=lambda r: r["reviewed_at"] or "", reverse=True)

#     if not _decided:
#         st.info("해당 조건의 결재 이력이 없습니다.")
#     else:
#         _render_timeline(_decided)


# # ── 탭 3: 액세스 로그 ────────────────────────────────
# with tab_access:
#     if st.session_state.audit:
#         st.dataframe(
#             pd.DataFrame(st.session_state.audit),
#             width="stretch", hide_index=True,
#         )
#     else:
#         st.info("아직 액세스 기록이 없습니다.")



### 0919 수정
"""Audit · 예산 결재 — 관리자용.

Renders (위→아래):
  [사이드바 슬롯]
    1) Filters   : 상태(pending/...) + 사용자 아이디 부분 검색
    2) Snapshot  : 상태별 카운트

  [메인]
    3) 헤더    : "Audit · 예산 결재" + Admin 표시
    4) KPI 4개 : 대기 큐 / 승인 완료 / 거절 / 총 신청
    5) 3-탭
        📥 대기 큐         : pending 신청들. 각 항목에 승인 레벨 라디오 + [승인] [거절]
        🕓 결재 타임라인   : 이미 결재된 항목들을 최근순 컨테이너 리스트
        🔍 액세스 로그     : session-local audit 로그 dataframe

핵심 상태 키
    _decide_<req_id> : "approved" | "rejected" — 승인/거절 버튼이 다음 rerun 에
                       처리하도록 남겨두는 트랜지언트 플래그
"""
import pandas as pd
import streamlit as st
from ui import db, requests as reqs, state, theme

theme.inject_global_css()

if not st.session_state.get("is_admin"):
    st.error("이 페이지는 관리자 권한이 필요한 페이지입니다.")
    st.stop()


# ── 사이드바 필터 & 스냅샷 ────────────────────
with st.session_state.nav_slot:
    st.caption("Filters")
    status = st.selectbox(
        "상태",
        ["전체", "pending", "approved", "partial", "rejected"],
        format_func=lambda s: {
            "전체": "전체", "pending": "대기", "approved": "승인",
            "partial": "부분승인", "rejected": "거절",
        }.get(s, s),
        key="req_filter_status",
    )
    user_q = st.text_input(
        "사용자 검색", placeholder="아이디 일부", key="req_filter_user",
    )

    st.divider()
    st.caption("Snapshot")
    _s = reqs.stats()
    st.write(f"대기 · **{_s['pending']}**")
    st.write(f"승인 · **{_s['approved']}**")
    st.write(f"부분승인 · **{_s['partial']}**")
    st.write(f"거절 · **{_s['rejected']}**")


# ── 헤더 ────────────────────────────────────
head_l, head_r = st.columns([3, 1.2], vertical_alignment="center")
with head_l:
    st.title("Audit · 예산 결재")
    st.caption("분석가의 리스크 업그레이드 신청을 검토·조정·결재합니다.")
with head_r:
    st.write(f"🛡️ **Admin** · {st.session_state.username}")


# ── KPI ────────────────────────────────────
stat = reqs.stats()
c1, c2, c3, c4 = st.columns(4)
c1.metric("대기 큐",   stat["pending"])
c2.metric("승인 완료", stat["approved"] + stat["partial"])
c3.metric("거절",     stat["rejected"])
c4.metric("총 신청",   sum(stat.values()))


# ── 탭 ─────────────────────────────────────
tab_queue, tab_hist, tab_access = st.tabs(
    ["📥 대기 큐", "🕓 결재 타임라인", "🔍 액세스 로그"]
)


def _render_pending_item(r: dict) -> None:
    """대기 큐 항목 카드 + 결재 UI."""
    with st.container(border=True):
        head_l, head_r = st.columns([3, 1.2], vertical_alignment="center")
        with head_l:
            st.write(
                f"**#{r['id']}** · **{r['username']}** · `{r['db_name']}` · "
                f"Risk {r['current_level']} → Risk {r['requested_level']}"
            )
            st.caption(f"신청 · {r['created_at'].replace('T', ' ')}")
        with head_r:
            eps = db.RISK_TO_EPSILON[int(r["requested_level"])]
            st.warning(f"요청 Risk {r['requested_level']} (ε={eps:.0f})")

        st.info(r["reason"])

        # 결재 컨트롤
        dec_l, dec_r = st.columns([2, 1], gap="medium")
        with dec_l:
            # 승인 가능 레벨 = current+1 ~ requested_level
            options = list(range(int(r["current_level"]) + 1,
                                 int(r["requested_level"]) + 1))
            approved_level = st.radio(
                "승인할 리스크 레벨",
                options=options,
                index=len(options) - 1,   # 기본은 요청 그대로
                horizontal=True,
                key=f"appr_{r['id']}",
                format_func=lambda l: f"Risk {l} (ε={db.RISK_TO_EPSILON[l]:.0f})",
            )
            note = st.text_input(
                "관리자 노트 (선택)",
                key=f"note_{r['id']}",
                placeholder="결재 사유를 남기면 신청자에게 함께 전달됩니다.",
            )
        with dec_r:
            st.caption(" ")   # 상단 여백 맞춤
            if st.button("✓ 승인", type="primary",
                         key=f"ok_{r['id']}", width='stretch'):
                st.session_state[f"_decide_{r['id']}"] = "approved"
            if st.button("✕ 거절",
                         key=f"no_{r['id']}", width='stretch'):
                st.session_state[f"_decide_{r['id']}"] = "rejected"

        _apply_decision(r, approved_level, note)


def _apply_decision(r: dict, approved_level: int, note: str) -> None:
    dec = st.session_state.pop(f"_decide_{r['id']}", None)
    if dec == "approved":
        # 요청 레벨보다 낮으면 partial, 같으면 approved
        status = ("partial"
                  if int(approved_level) < int(r["requested_level"])
                  else "approved")
        reqs.decide(r["id"],
                    reviewer=st.session_state.username,
                    status=status,
                    approved_level=int(approved_level),
                    note=note)
        state.log(
            "approve",
            f"#{r['id']} → {status} Risk {approved_level} (user {r['username']})",
        )
        st.success(
            f"#{r['id']} · {r['username']} 에게 Risk {approved_level} 을 "
            f"{'부분 승인' if status == 'partial' else '승인'} 했습니다.",
        )
        st.rerun()
    elif dec == "rejected":
        reqs.decide(r["id"],
                    reviewer=st.session_state.username,
                    status="rejected", approved_level=None, note=note)
        state.log("reject", f"#{r['id']} 거절 (user {r['username']})")
        st.warning(f"#{r['id']} · {r['username']} 의 신청을 거절했습니다.")
        st.rerun()


# ── 탭 1: 대기 큐 ──────────────────────────
with tab_queue:
    _items = reqs.list_all(status="pending", user=user_q or None)
    if not _items:
        st.info("검토 대기 중인 신청이 없습니다.")
    else:
        for _r in _items:
            _render_pending_item(_r)


# ── 탭 2: 결재 타임라인 ────────────────────
def _render_timeline(items: list[dict]) -> None:
    for r in items:
        with st.container(border=True):
            lbl = {"approved": "✅ 승인",
                   "partial":  "🟡 부분 승인",
                   "rejected": "❌ 거절"}[r["status"]]
            when = (r["reviewed_at"] or "").replace("T", " ")
            appr = (f"Risk {r['approved_level']}"
                    if r["approved_level"] is not None else "—")

            st.write(
                f"**{lbl}** · #{r['id']} · **{r['username']}** · "
                f"`{r['db_name']}` · Risk {r['current_level']} → "
                f"Risk {r['requested_level']} → 확정 **{appr}**"
            )
            st.caption(f"{when} · reviewer: {r['reviewer'] or '-'}")
            if r["admin_note"]:
                st.caption(f"관리자 노트 — \"{r['admin_note']}\"")


with tab_hist:
    _all = reqs.list_all(
        status=None if status == "전체" else status,
        user=user_q or None,
    )
    _decided = [r for r in _all if r["status"] != "pending"]
    _decided.sort(key=lambda r: r["reviewed_at"] or "", reverse=True)

    if not _decided:
        st.info("해당 조건의 결재 이력이 없습니다.")
    else:
        _render_timeline(_decided)


# ── 탭 3: 액세스 로그 ──────────────────────
with tab_access:
    if st.session_state.audit:
        st.dataframe(
            pd.DataFrame(st.session_state.audit),
            width='stretch', hide_index=True,
        )
    else:
        st.info("아직 액세스 기록이 없습니다.")