# """DP Agent Console — 분석가 메인 페이지.

# Renders (위→아래):
#   [사이드바 슬롯]
#     1) DB 도메인/이름 selectbox 2단
#     2) 질의 유형(mean/count/...) selectbox
#     3) 채팅 히스토리 요약 (최근 5개 사용자 질문)

#   [메인]
#     4) 헤더  : "DP Agent Console" + 부제 + 현재 DB 표시
#     5) KPI  : 도넛 게이지(누적 소모) · 세션 질의 수 · 데이터 접근 정책 안내
#     6) 좌우 2컬럼
#        좌) 🔒 Schema  : parquet 컬럼 목록 + 이름 필터
#        우) Agent/수동 편집 탭
#              - Agent 탭   : chat_input 으로 온 질문을 에이전트에 넘겨
#                             생성 코드를 스트리밍 → 자동 실행 → ε 소비
#              - 수동 탭    : 코드 직접 편집 → [▶ 실행] 버튼 → ε 소비
#              - 공통 하단  : 실행 결과 / 소모 ε / LLM 호출 metric 3개
#     7) [하단]  st.chat_input — 자연어 질문 입력

# 핵심 상태 키
#     pending_q     : chat_input 에서 보낸 질문. 다음 rerun 에서 Agent 탭이 처리.
#     manual_code   : 수동 편집기 텍스트 (에이전트 결과도 여기 반영됨)
#     last_result   : {value, ok, src, calls} — 결과 표시용
# """
# import streamlit as st
# from ui import agent_bridge as ab, db, state, theme

# theme.inject_global_css()

# # 현재 (DB × query_type) 정책 + 개인 상한을 세션에 반영
# state.apply_active_policy()


# # ─────────────────────────────────────────────────────────
# # 렌더링 세부 함수들 (top-level 스크립트에서 호출되기 전에 정의)
# # ─────────────────────────────────────────────────────────

# def _render_sidebar_chat_history() -> None:
#     """최근 사용자 질문 5개를 요약해서 사이드바에 표시."""
#     user_msgs = [m for m in st.session_state.messages if m["role"] == "user"][-5:]
#     if not user_msgs:
#         st.caption("_아직 질문이 없습니다._")
#         return
#     for i, mm in enumerate(reversed(user_msgs), 1):
#         snippet = mm["content"][:36] + ("…" if len(mm["content"]) > 36 else "")
#         st.write(f"**Q{i}.** {snippet}")


# def _render_schema_panel() -> None:
#     """좌측: 스키마 컬럼 목록 (검색 가능) — 값 프리뷰 없이 이름/타입만."""
#     with st.container(border=True, height=540):
#         st.subheader("🔒 Schema")
#         try:
#             sch = ab.schema_of(st.session_state.db_name)
#         except Exception as e:
#             st.warning(f"스키마 로드 실패: {e}")
#             return

#         st.caption(f"{len(sch)}개 컬럼 · 값 미리보기 없음")
#         kw = st.text_input("검색", placeholder="🔍 컬럼명 필터",
#                            label_visibility="collapsed")
#         view = sch[sch["column"].str.contains(kw, case=False)] if kw else sch
#         st.dataframe(
#             view, hide_index=True, width="stretch",
#             height=min(38 * (len(view) + 1) + 3, 400),
#             column_config={
#                 "column": st.column_config.TextColumn("컬럼", width=140),
#                 "dtype":  st.column_config.TextColumn("타입", width=280),
#             },
#         )


# def _run_agent_streaming(slot, q: str) -> None:
#     """pending_q 를 에이전트에 넘겨 코드를 스트리밍 → 실행 → 결과 저장."""
#     with slot.container():
#         with st.status("에이전트가 코드를 작성 중…", expanded=True) as stt:
#             st.caption("① 스키마로 프롬프트 구성 (원본 레코드 미포함)")
#             code = st.write_stream(
#                 ab.stream_code(q, st.session_state.db_name)
#             )
#             trace = st.session_state.get("_last_trace", {})
#             st.caption("② 샌드박스에서 실행")
#             stt.update(
#                 label="완료" if not trace.get("final_error") else "실행 실패",
#                 state="complete" if not trace.get("final_error") else "error",
#                 expanded=False,
#             )

#     st.session_state.manual_code = code
#     out = trace.get("output")
#     ok = out is not None and not trace.get("final_error")

#     # 성공했더라도 ε 상한을 넘으면 결과를 감춘다
#     if ok and not state.spend(st.session_state.eps, "query", q):
#         ok, out = False, None
#         st.error(
#             "ε 상한을 초과하여 결과를 반환하지 않았습니다. "
#             "Budget Requests 페이지에서 예산을 신청하세요.",
#             icon="🚫",
#         )

#     st.session_state.last_result = {
#         "value": out, "ok": ok, "src": "agent",
#         "calls": trace.get("n_llm_calls", 0),
#     }
#     st.session_state.messages += [
#         {"role": "user", "content": q},
#         {"role": "assistant",
#          "content": (f"결과: **{float(out):,.2f}**"
#                      if ok else "결과를 얻지 못했습니다."),
#          "code": code},
#     ]
#     st.session_state.pending_q = None
#     st.rerun()


# def _run_manual_code() -> None:
#     """수동 편집 탭의 [▶ 실행] 처리."""
#     if not state.can_spend(st.session_state.eps):
#         st.error(
#             "ε 상한을 초과했습니다. "
#             "Budget Requests 페이지에서 예산 증액을 신청하세요.",
#             icon="🚫",
#         )
#         return
#     r = ab.run_code(st.session_state.manual_code, st.session_state.db_name)
#     ok = not str(r).startswith(("__CODE_ERROR__", "__TIMEOUT__"))
#     if ok:
#         state.spend(st.session_state.eps, "manual", "직접 코드 실행")
#     st.session_state.last_result = {
#         "value": r, "ok": ok, "src": "manual", "calls": 0,
#     }
#     st.rerun()


# def _render_agent_tab() -> None:
#     """Agent 탭 몸통."""
#     slot = st.empty()

#     if st.session_state.pending_q:
#         _run_agent_streaming(slot, st.session_state.pending_q)
#         return

#     last = st.session_state.get("last_result")
#     if last and last.get("src") == "agent":
#         st.code(st.session_state.manual_code, language="python")
#     else:
#         st.caption(
#             "아직 에이전트가 생성한 코드가 없습니다. "
#             "아래 채팅창에 자연어로 질문해보세요."
#         )


# def _render_manual_tab() -> None:
#     """수동 편집 탭 몸통."""
#     st.text_area(
#         "코드 본문", key="manual_code", height=220,
#         label_visibility="collapsed",
#         help="`return` 으로 스칼라 값을 반환하는 함수 본문을 작성하세요.",
#     )
#     b1, b2 = st.columns([1, 2], vertical_alignment="center")
#     if b1.button("▶ 실행", width="stretch", type="primary",
#                  key="run_manual"):
#         _run_manual_code()
#     b2.caption(f"실행 시 ε = {st.session_state.eps:.2f} 소모")


# def _render_result_metrics() -> None:
#     """Agent / 수동 탭 아래에 공통으로 붙는 결과 요약."""
#     res = st.session_state.last_result
#     if not res:
#         return

#     if not res["ok"]:
#         st.error(str(res["value"]), icon="⚠️")
#         return

#     try:
#         val_str = f"{float(res['value']):,.2f}"
#     except Exception:
#         val_str = str(res["value"])[:24]

#     c1, c2, c3 = st.columns(3)
#     c1.metric("실행 결과", val_str,
#               help="아직 노이즈가 적용되지 않은 참값입니다.")
#     c2.metric("소모 ε", f"{st.session_state.eps:.2f}")
#     c3.metric("LLM 호출", res["calls"])


# def _render_editor_panel() -> None:
#     """우측 컨테이너: Agent 탭 + 수동 편집 탭 + 결과 metric."""
#     with st.container(border=True, height=540):
#         tab_agent, tab_manual = st.tabs(["🤖 Agent", "✍️ 수동 편집"])
#         with tab_agent:
#             _render_agent_tab()
#         with tab_manual:
#             _render_manual_tab()
#         _render_result_metrics()


# # ─────────────────────────────────────────────────────────
# # 페이지 본체 (top-level)
# # ─────────────────────────────────────────────────────────

# # ── 사이드바 컨텍스트 ────────────────────────────────────
# with st.session_state.nav_slot:
#     st.caption("Query target")

#     dom = st.selectbox(
#         "도메인", ab.catalog.domains(),
#         key="db_domain", label_visibility="collapsed",
#     )
#     choices = ab.catalog.names(dom)
#     if not choices:
#         st.error("`competition/` 아래에서 `all.parquet` 을 찾지 못했습니다.")
#         st.stop()
#     if st.session_state.db_name not in choices:
#         st.session_state.db_name = choices[0]

#     st.selectbox(
#         "Database", choices, key="db_name",
#         format_func=lambda n: f"{n} · {ab.catalog.meta(n)['title'][:26]}",
#         label_visibility="collapsed",
#     )
#     # ===qa 페이지에는 필요 없는 코드=== + 쿼리 타입은 기본 mean으로 설정됨
#     # if st.session_state.is_admin:
#     #     st.selectbox(
#     #         # "Query type"라는 제목으로 드롭다운을 만듦
#     #         # 선택지는 db.QUERY_TYPES에 들어 있는 값들("mean", "count", "sum", "variance", "max")
#     #         # 선택된 값은 세션 상태의 "query_type" 키에 저장됨
#     #         "Query type", db.QUERY_TYPES, key="query_type",

#     #         # format_func을 써서 내부 값(mean, count, sum 등)을 사람이 보기 쉽게 한글+영문으로 표시
#     #         format_func=lambda q: {
#     #             "mean":     "평균 (mean)",
#     #             "count":    "카운트 (count)",
#     #             "sum":      "합계 (sum)",
#     #             "variance": "분산 (variance)",
#     #             "max":      "최댓값 (max)",
#     #         }.get(q, q),
#     #     )

#     if not(st.session_state.is_admin):
#         st.divider()
#         st.caption("Chat history")
#         _render_sidebar_chat_history()


# # ── 헤더 ────────────────────────────────────────────────
# head_l, head_r = st.columns([3, 1.2], vertical_alignment="center")
# with head_l:
#     st.title("DP Agent Console")
#     st.caption("질문 → 코드 생성 → 샌드박스 실행 → ε 원장 기록")
# with head_r:
#     st.write(f"**DB** · `{st.session_state.db_name}`")


# # ── KPI 3개 (도넛 게이지 + metric 2개) ──────────────────
# _eps_cap   = max(st.session_state.eps_cap, 1e-9)
# _spent     = st.session_state.spent
# _remaining = max(0.0, _eps_cap - _spent)
# _ratio     = _spent / _eps_cap
# _tone      = ("success" if _ratio < 0.6
#               else ("warning" if _ratio < 0.9 else "danger"))

# g1, g2, g3 = st.columns(3)
# with g1:
#     # 시각적 이해가 필요한 지표 → SVG 도넛 유지
#     st.markdown(
#         theme.donut_gauge(
#             "누적 소모", _spent, _eps_cap,
#             unit="ε", tone=_tone,
#             sub=f"잔여 {_remaining:.2f} ε",
#         ),
#         unsafe_allow_html=True,
#     )
# with g2:
#     _n_queries = sum(1 for m in st.session_state.messages if m["role"] == "user")
#     st.metric("Queries (session)", _n_queries,
#               help=f"질의당 ε · {st.session_state.eps:.2f}")
# with g3:
#     st.metric("Data access", "Sandbox",
#               help="원본 레코드 직접 접근 불가")


# st.divider()


# # ── 라이브 코딩 영역 ───────────────────────────────────
# left, right = st.columns([1, 1.55], gap="medium")
# with left:
#     _render_schema_panel()
# with right:
#     _render_editor_panel()


# st.divider()

# # ── 하단 자연어 채팅 입력 ──────────────────────────────
# if q := st.chat_input("코드를 모르시겠나요? 자연어로 질문하세요 "
#                       "(예: 신용한도 평균은 얼마인가요?)"):
#     st.session_state.pending_q = q
#     st.rerun()



### 0919 수정
"""DP Agent Console — 분석가 메인 페이지.

Renders (위→아래):
  [사이드바 슬롯]
    · 분석가일 때만 채팅 히스토리 요약 (최근 5개 사용자 질문)

  [메인]
    1) Query target : DB 도메인/이름 선택 (모든 사용자)
    2) 헤더  : "DP Agent Console" + 부제 + 현재 DB 요약
    3) KPI   : 도넛 게이지(누적 소모 / 유효 총 ε) · 세션 질의 수 · 유효 정책 뱃지
    4) [예산 추가 요청] 버튼 (분석가만) → Budget Requests 페이지로 이동하며 db_name 컨텍스트 프리셋
    5) 좌우 2컬럼 · 좌:Schema / 우: Agent 탭 + 수동 탭 + 결과 metric
    6) 하단 : st.chat_input (자연어 질문)

핵심 상태 키
    pending_q     : chat_input 이 넣은 질문. 다음 rerun 에서 Agent 탭이 처리.
    manual_code   : 수동 편집기 텍스트
    last_result   : {value, ok, src, calls}
"""
import html

import streamlit as st
from ui import agent_bridge as ab, state, theme


theme.inject_global_css()


# ─────────────────────────────────────────────────
# 렌더링 세부 함수들 (top-level 스크립트에서 호출되기 전에 정의)
# ─────────────────────────────────────────────────

def _render_sidebar_chat_history() -> None:
    """최근 사용자 질문 5개 요약."""
    user_msgs = [m for m in st.session_state.messages if m["role"] == "user"][-5:]
    if not user_msgs:
        st.caption("_아직 질문이 없습니다._")
        return
    for i, mm in enumerate(reversed(user_msgs), 1):
        snippet = mm["content"][:36] + ("…" if len(mm["content"]) > 36 else "")
        st.write(f"**Q{i}.** {snippet}")


def _render_schema_panel() -> None:
    with st.container(border=True, height=540):
        st.subheader("🔒 Schema")
        try:
            sch = ab.schema_of(st.session_state.db_name)
        except Exception as e:
            st.warning(f"스키마 로드 실패: {e}")
            return

        st.caption(f"{len(sch)}개 컬럼 · 값 미리보기 없음")
        kw = st.text_input("검색", placeholder="🔍 컬럼명 필터",
                           label_visibility="collapsed")
        view = sch[sch["column"].str.contains(kw, case=False)] if kw else sch
        st.dataframe(
            view, hide_index=True, width='stretch',
            height=min(38 * (len(view) + 1) + 3, 400),
            column_config={
                "column": st.column_config.TextColumn("컬럼", width=140),
                "dtype":  st.column_config.TextColumn("타입", width=280),
            },
        )


def _stream_compact_code(stream) -> str:
    placeholder = st.empty()
    chunks: list[str] = []
    for chunk in stream:
        chunks.append(chunk)
        placeholder.markdown(
            "<pre style=\"margin:0; font-size:0.78rem; line-height:1.45; "
            "white-space:pre-wrap; overflow-wrap:anywhere;\">"
            f"{html.escape(''.join(chunks))}</pre>",
            unsafe_allow_html=True,
        )
    return "".join(chunks)


def _run_agent_streaming(slot, q: str) -> None:
    with slot.container():
        with st.status("에이전트가 코드를 작성 중…", expanded=True) as stt:
            st.caption("① 스키마로 프롬프트 구성 (원본 레코드 미포함)")
            code = _stream_compact_code(
                ab.stream_code(q, st.session_state.db_name)
            )
            trace = st.session_state.get("_last_trace", {})
            st.caption("② 샌드박스에서 실행")
            stt.update(
                label="완료" if not trace.get("final_error") else "실행 실패",
                state="complete" if not trace.get("final_error") else "error",
                expanded=False,
            )

    st.session_state.manual_code = code
    out = trace.get("output")
    ok = out is not None and not trace.get("final_error")

    # 성공했더라도 총 ε 예산 넘으면 결과 감춤
    if ok and not state.spend(st.session_state.eps, "query", q):
        ok, out = False, None
        st.error(
            "ε 예산을 초과하여 결과를 반환하지 않았습니다. "
            "예산 추가 요청을 고려하세요.",
            icon="🚫",
        )

    st.session_state.last_result = {
        "value": out, "ok": ok, "src": "agent",
        "calls": trace.get("n_llm_calls", 0),
    }
    st.session_state.messages += [
        {"role": "user", "content": q},
        {"role": "assistant",
         "content": (f"결과: **{float(out):,.2f}**"
                     if ok else "결과를 얻지 못했습니다."),
         "code": code},
    ]
    st.session_state.pending_q = None
    st.rerun()


def _run_manual_code() -> None:
    if not state.can_spend(st.session_state.eps):
        st.error(
            "ε 예산을 초과했습니다. 예산 추가 요청을 고려하세요.",
            icon="🚫",
        )
        return
    r = ab.run_code(st.session_state.manual_code, st.session_state.db_name)
    ok = not str(r).startswith(("__CODE_ERROR__", "__TIMEOUT__"))
    if ok:
        state.spend(st.session_state.eps, "manual", "직접 코드 실행")
    st.session_state.last_result = {
        "value": r, "ok": ok, "src": "manual", "calls": 0,
    }
    st.rerun()


def _render_agent_tab() -> None:
    slot = st.empty()
    if st.session_state.pending_q:
        _run_agent_streaming(slot, st.session_state.pending_q)
        return
    last = st.session_state.get("last_result")
    if last and last.get("src") == "agent":
        st.code(st.session_state.manual_code, language="python")
    else:
        st.caption(
            "아직 에이전트가 생성한 코드가 없습니다. "
            "아래 채팅창에 자연어로 질문해보세요."
        )


def _render_manual_tab() -> None:
    st.text_area(
        "코드 본문", key="manual_code", height=220,
        label_visibility="collapsed",
        help="`return` 으로 스칼라 값을 반환하는 함수 본문을 작성하세요.",
    )
    b1, b2 = st.columns([1, 2], vertical_alignment="center")
    if b1.button("▶ 실행", type="primary", width='stretch',
                 key="run_manual"):
        _run_manual_code()
    b2.caption(f"실행 시 ε = {st.session_state.eps:.2f} 소모")


def _render_result_metrics() -> None:
    res = st.session_state.last_result
    if not res:
        return
    if not res["ok"]:
        st.error(str(res["value"]), icon="⚠️")
        return
    try:
        val_str = f"{float(res['value']):,.2f}"
    except Exception:
        val_str = str(res["value"])[:24]

    c1, c2, c3 = st.columns(3)
    c1.metric("실행 결과", val_str,
              help="아직 노이즈가 적용되지 않은 참값입니다.")
    c2.metric("소모 ε", f"{st.session_state.eps:.2f}")
    c3.metric("LLM 호출", res["calls"])


def _render_editor_panel() -> None:
    with st.container(border=True, height=540):
        tab_agent, tab_manual = st.tabs(["🤖 Agent", "✍️ 수동 편집"])
        with tab_agent:
            _render_agent_tab()
        with tab_manual:
            _render_manual_tab()
        _render_result_metrics()


# ─────────────────────────────────────────────────
# 페이지 본체 (top-level)
# ─────────────────────────────────────────────────

# ── 사이드바: 분석가일 때만 채팅 히스토리 ────
with st.session_state.nav_slot:
    if not st.session_state.is_admin:
        st.caption("Chat history")
        _render_sidebar_chat_history()


# ── Query target · 대상 DB 선택 ────────────────
with st.container(border=True):
    st.subheader("Query target · 질의 대상 DB")
    sel_l, sel_r = st.columns([1, 2])
    with sel_l:
        dom = st.selectbox("도메인", ab.catalog.domains(), key="db_domain")
    with sel_r:
        choices = ab.catalog.names(dom)
        if not choices:
            st.error("`competition/` 아래에서 `all.parquet` 을 찾지 못했습니다.")
            st.stop()
        if st.session_state.db_name not in choices:
            st.session_state.db_name = choices[0]
        st.selectbox(
            "Database", choices, key="db_name",
            format_func=lambda n: f"{n} · {ab.catalog.meta(n)['title'][:40]}",
        )

# DB 선택이 세션에 반영된 뒤 유효 정책 로드
POLICY = state.apply_effective_policy(st.session_state.db_name)


# ── 헤더 ────────────────────────────────────────
head_l, head_r = st.columns([3, 1.2], vertical_alignment="center")
with head_l:
    st.title("DP Agent Console")
    st.caption("질문 → 코드 생성 → 샌드박스 실행 → ε 원장 기록")
with head_r:
    _meta = ab.catalog.meta(st.session_state.db_name)
    st.write(f"**DB** · `{st.session_state.db_name}`")
    st.caption(
        f"{_meta.get('title', st.session_state.db_name)} · "
        f"{int(_meta.get('n_rows', 0)):,} rows · "
        f"{int(_meta.get('n_cols', 0))} columns"
    )


# ── KPI 3개 (도넛 게이지 + metric 2개) ─────────
_total_eps = max(float(POLICY["total_epsilon"]), 1e-9)
_spent     = float(st.session_state.spent)
_remaining = max(0.0, _total_eps - _spent)
_ratio     = _spent / _total_eps
_tone      = ("success" if _ratio < 0.6
              else ("warning" if _ratio < 0.9 else "danger"))

g1, g2, g3 = st.columns(3)
with g1:
    st.markdown(
        theme.donut_gauge(
            "누적 소모", _spent, _total_eps,
            unit="ε", tone=_tone,
            sub=f"잔여 {_remaining:.2f} ε",
        ),
        unsafe_allow_html=True,
    )
with g2:
    _n_queries = sum(1 for m in st.session_state.messages if m["role"] == "user")
    st.metric("Queries (session)", _n_queries,
              help=f"질의당 ε · {st.session_state.eps:.2f}")
with g3:
    _source_label = {
        "override":       "개인 오버라이드",
        "db_default":     "DB 확정 정책",
        "system_default": "시스템 기본값",
    }[POLICY["source"]]
    st.metric(
        "유효 정책",
        f"Risk {POLICY['risk_level']} · ε={_total_eps:.1f}",
        help=f"출처 : {_source_label}",
    )


# ── 예산 추가 요청 버튼 (분석가만) ────────────
if not st.session_state.is_admin:
    b_l, b_r = st.columns([1, 4])
    with b_l:
        if st.button("💰 예산 추가 요청", type="secondary",
                     width='stretch'):
            # 현재 DB 컨텍스트를 프리셋으로 넘겨 Budget Requests 페이지로 이동
            st.session_state.req_prefill_db    = st.session_state.db_name
            st.session_state.req_prefill_level = min(
                5, int(POLICY["risk_level"]) + 1
            )
            st.switch_page("ui/pages/budget_requests.py")
    with b_r:
        st.caption(
            "예산이 부족하거나 더 정밀한 결과가 필요하면 관리자에게 "
            "리스크 레벨 업그레이드를 요청할 수 있습니다."
        )


st.divider()


# ── 라이브 코딩 영역 ─────────────────────────
left, right = st.columns([1, 1.55], gap="medium")
with left:
    _render_schema_panel()
with right:
    _render_editor_panel()


st.divider()

# ── 자연어 채팅 입력 ─────────────────────────
if q := st.chat_input("코드를 모르시겠나요? 자연어로 질문하세요 "
                      "(예: 신용한도 평균은 얼마인가요?)"):
    st.session_state.pending_q = q
    st.rerun()