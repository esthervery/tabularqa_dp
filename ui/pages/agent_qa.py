### 0928 수정
"""DP Agent Console — 분석가 메인 페이지.

Renders (위→아래):
  [메인]
    1) Query target : [누적 소모 도넛] + 도메인 + Database  (3열 1행)
    2) [예산 추가 요청] 버튼 (분석가만) → Budget Requests 페이지로 이동하며 db_name 프리셋
    3) 좌우 2컬럼 · 좌:Schema / 우: 탭(에이전트·수동) + 결과 블록 + 자연어 입력창
    4) 구분선
    5) History : 선택된 데이터셋의 질의·응답 기록 (최근 1건 항상 노출, 이하는 expander)

0928 수정 요약
    · 사이드바 'Chat history' 블록 제거 — 기록은 아래 History 섹션(query_log)이 전담한다.
    · KPI 행 제거 — 'Queries' 카드는 삭제(질의 횟수는 History 섹션 제목에서 확인),
      도넛 게이지는 Query target 컨테이너의 1열로 이동.
    · 자연어 입력창(st.chat_input)을 편집 컨테이너 안으로 이동 (화면 하단 고정 해제).
    · 데이터셋을 바꾸면 이전 데이터셋의 코드·결과를 on_change 콜백에서 비운다.
    · 에이전트 질의 실패(준비 실패 + 실행 중 오류)는 트레이스백 대신 안내 문구와
      '파이프라인 다시 준비' 버튼으로 수렴시킨다.

핵심 상태 키
    pending_q     : chat_input 이 넣은 질문. 다음 rerun 에서 Agent 탭이 처리.
    manual_code   : 수동 편집기 텍스트 (데이터셋 전환 시 기본값으로 리셋)
    last_result   : {value, ok, src, calls} (데이터셋 전환 시 None 으로 리셋)
"""
import html
import numbers
import pandas as pd
import traceback

import streamlit as st
from ui import agent_bridge as ab, boot, db, state, theme


theme.inject_global_css()


# ─────────────────────────────────────────────────
# 렌더링 세부 함수들 (top-level 스크립트에서 호출되기 전에 정의)
# ─────────────────────────────────────────────────

def _render_schema_panel() -> None:
    with st.expander("Schema · 컬럼 목록", expanded=False):
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
    """생성 코드를 작은 고정폭 글꼴로 스트리밍해 표시한다."""
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
        stt = None
        try:
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
        except Exception as e:
            # [0928] 준비 실패(PipelineUnavailable)와 실행 중 오류(OpenAI 인증/레이트리밋/
            # 네트워크 등)를 동일하게 처리한다. 어느 쪽이든 데모에서 빨간 트레이스백이
            # 그대로 노출되면 안 되므로, 안내 문구 + 재준비 버튼으로 수렴시킨다.
            #
            # mock 코드로 대체하지 않는 이유: 실행되지도 않는 가짜 코드가 '결과'처럼
            # 보이면 데모 신뢰도가 깨진다.
            # pending_q 를 지우지 않으므로, 재준비가 끝나고 리런되면 같은 질문이
            # 이어서 실행된다(질문을 다시 입력할 필요 없음).
            #
            # 사유는 화면에 한 줄로 남기고, 전체 스택은 서버 콘솔로만 보낸다
            # (화면에는 노출하지 않되 개발 중 원인 파악은 가능하게).
            reason = (str(e) if isinstance(e, ab.PipelineUnavailable)
                      else f"{type(e).__name__}: {e}")
            traceback.print_exc()

            # 예외로 빠져나오면 st.status 가 '작성 중…' 상태로 계속 돌아 보인다.
            # 오류 문구와 함께 스피너가 남지 않도록 상태를 마감한다.
            if stt is not None:
                try:
                    stt.update(label="파이프라인 오류", state="error",
                               expanded=False)
                except Exception:
                    pass

            st.error(
                "에이전트 파이프라인 준비에 실패했습니다. "
                "아래 버튼으로 다시 준비하거나 잠시 후 다시 시도하세요.",
                icon="⚠️",
            )
            st.caption(f"사유: {reason}")
            if st.button("파이프라인 다시 준비", key="retry_pipeline",
                         width='stretch'):
                boot.discard()
                boot.start()
                st.rerun()
            return

    st.session_state.manual_code = code
    out = trace.get("output")
    ok = out is not None and not trace.get("final_error")

    # 성공했더라도 "이 데이터셋"의 ε 예산 넘으면 결과 감춤
    # (예산은 데이터셋별로 관리된다 — state.spend 는 현재 선택된 DB 기준)
    if ok and not state.spend(st.session_state.eps, "query", q):
        ok, out = False, "ε 예산을 초과하여 결과를 반환하지 않았습니다."
        st.error(
            "ε 예산을 초과하여 결과를 반환하지 않았습니다. "
            "예산 추가 요청을 고려하세요.",
            icon="🚫",
        )

    # 질의·응답을 데이터셋별 history 에 기록.
    # 실행 실패·예산 초과 차단은 ok=False 로 남고 ε 은 소모되지 않는다.
    if ok:
        try:
            _answer = f"{float(out):,.2f}"
        except (TypeError, ValueError):
            _answer = str(out)
    else:
        _answer = "결과를 얻지 못했습니다."
    state.record_query(q, _answer, code=code, ok=ok)

    st.session_state.last_result = {
        "value": out, "ok": ok, "src": "agent",
        "calls": trace.get("n_llm_calls", 0),
    }
    st.session_state.pending_q = None
    st.rerun()


def _run_manual_code() -> None:
    if not state.can_spend(st.session_state.eps):
        st.session_state.last_result = {
            "value": "사용 가능한 예산이 부족합니다. 예산을 추가한 뒤 다시 실행해주세요.",
            "ok": False, "src": "manual", "calls": 0,
        }
        return
    code = st.session_state.manual_code
    with st.spinner("선택한 데이터셋에서 실행 중…"):
        try:
            result = ab.run_code(code, st.session_state.db_name)
        except Exception:
            # 실행기 내부 예외가 Streamlit 화면까지 전파되지 않도록 한다.
            result = {
                "ok": False,
                "message": "코드를 실행하지 못했습니다. 내용을 수정한 뒤 다시 실행해주세요.",
            }
    if not isinstance(result, dict):
        result = {
            "ok": False,
            "message": "실행 결과 형식을 읽지 못했습니다. 코드를 수정한 뒤 다시 실행해주세요.",
        }
    ok = result["ok"]
    value = result.get("value") if ok else result["message"]
    if ok and not state.spend(st.session_state.eps, "manual", "직접 코드 실행"):
        ok, value = False, "사용 가능한 예산이 부족합니다."
    answer = "실행 완료 (반환값 없음)" if ok and value is None else str(value)
    state.record_query("(수동 코드 실행)", answer, code=code, ok=ok)
    st.session_state.last_result = {
        "value": value, "ok": ok, "src": "manual", "calls": 0,
    }
    st.rerun()


def _load_history_code(code: str, run: bool = False) -> None:
    st.session_state.manual_code = code
    st.session_state.pending_manual_run = run
    st.session_state.last_result = None


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
    if st.session_state.pop("pending_manual_run", False):
        _run_manual_code()
    st.text_area(
        "코드 본문", key="manual_code", height=220,
        label_visibility="collapsed",
        help="선택한 데이터는 df입니다. 예: df.shape[0] 또는 return df.shape[0]. 마지막 식이나 print 결과도 표시됩니다.",
    )
    st.caption("`df`는 현재 선택한 데이터셋입니다. 마지막 식 또는 `return` 값이 결과로 표시됩니다.")
    b1, b2 = st.columns([1, 2], vertical_alignment="center")
    if b1.button("▶ 실행", type="primary", width='stretch',
                 key="run_manual"):
        _run_manual_code()
    b2.caption(f"성공 시 ε = {st.session_state.eps:.2f} 소모 · 실패 시 차감 없음")


def _render_result_block() -> None:
    """실행 결과 전용 블록 (1단계).

    ### 0928 수정
    기존에는 `st.columns(3)` 균등 3열에 metric 3개를 넣었다. 그러면
      · 답인 '실행 결과'가 1/3 폭만 받고,
      · st.metric 이 긴 값을 말줄임으로 잘라내고(게다가 앞에서 24자 슬라이스까지),
      · 코드 블록 바로 아래에 놓여 코드가 길면 화면 밖으로 밀렸다.
    그래서 결과만 전용 블록으로 분리하고 폭을 2.6 : 1 : 1 로 넓게 배분한다.
    남은 두 항목(소모 ε · LLM 호출)은 짧은 수치라 metric 을 그대로 쓴다.

    스타일은 정의하지 않는다. 전역 CSS 를 나중에 한꺼번에 입힐 예정이므로
    개발 단계에서는 네이티브 컴포넌트(border 컨테이너 · caption · write)만 쓴다.
    """
    res = st.session_state.last_result
    if not res:
        return

    if not res["ok"]:
        # 결과가 None 이면 예전에는 'None' 문자열이 그대로 보였다.
        # 사유가 있으면 그대로, 없으면 일반 문구로 대체한다.
        detail = res["value"]
        notice = st.info if res.get("src") == "manual" else st.error
        notice(
            "결과를 얻지 못했습니다." if detail is None else str(detail),
            icon="⚠️",
        )
        return

    # 값 표시 형식. 자르지 않는다 — 기존 [:24] 슬라이스가 리스트·문자열의
    # 뒷부분을 조용히 지웠다(화면에서 `['Premium'...` 로 보이던 원인).
    # 숫자 판별에 numbers 를 쓰는 이유: 실행기가 numpy 스칼라를 돌려줄 수 있는데
    # np.int64 는 int 의 서브클래스가 아니라 내장 isinstance 로는 놓친다.
    # bool 은 Integral 의 서브클래스이므로 먼저 걸러낸다.
    v = res["value"]
    if isinstance(v, (pd.DataFrame, pd.Series)):
        st.dataframe(v, width="stretch")
    elif isinstance(v, (list, dict, tuple)):
        st.json(v)
    if v is None:
        val_str = "—"
    elif isinstance(v, bool):
        val_str = str(v)
    elif isinstance(v, numbers.Integral):
        val_str = f"{int(v):,}"
    elif isinstance(v, numbers.Real):
        val_str = f"{float(v):,.2f}"
    else:
        val_str = str(v)

    c_res, c_eps, c_calls = st.columns([2.6, 1, 1],
                                       vertical_alignment="top")
    with c_res:
        with st.container(border=True):
            st.caption("실행 결과")
            st.write(val_str)
            st.caption("아직 노이즈가 적용되지 않은 참값입니다.")
    with c_eps:
        st.metric("소모 ε", f"{st.session_state.eps:.2f}")
    with c_calls:
        st.metric("LLM 호출", res["calls"])


def _render_editor_panel() -> None:
    schema_col, agent_col, manual_col = st.columns([1, 1.5, 1.5], gap="medium")
    with schema_col:
        _render_schema_panel()
    with agent_col:
        with st.container(border=True, key="agent_input_panel"):
            st.subheader("💬 에이전트 모드")
            _render_agent_tab()
            last = st.session_state.get("last_result")
            if last and last.get("src") == "agent":
                _render_result_block()
            if q := st.chat_input("선택한 데이터에 대해 질문하세요 (예: 총 몇 건인가요?)"):
                st.session_state.pending_q = q
                st.rerun()
    with manual_col:
        with st.container(border=True, key="manual_input_panel"):
            st.subheader("⌨️ 수동 입력 모드")
            _render_manual_tab()
            last = st.session_state.get("last_result")
            if last and last.get("src") == "manual":
                _render_result_block()


# [0928 수정] History 섹션
#   데이터셋 selectbox 를 바꾸면 이 패널의 내용도 함께 바뀐다 (조회 스코프 = 계정 × 데이터셋).
def _render_query_card(r: dict) -> None:
    """질의 1건 카드 (History 최신 1건과 expander 내부에서 공용)."""
    mark = "✅" if r["ok"] else "○"
    with st.container(border=True):
        st.write(f"{mark} **Q.** {r['question'] or '—'}")
        answer = r["answer"] or "—"
        if not r["ok"] and any(token in answer for token in ("__CODE_ERROR__", "__TIMEOUT__", "Traceback")):
            answer = "실행을 완료하지 못했습니다. 코드를 수정한 뒤 다시 실행해주세요."
        st.write(f"**A.** {answer}")
        st.caption(
            f"{(r['asked_at'] or '').replace('T', ' ')} · "
            f"소모 ε {float(r['eps_spent']):.2f}"
        )
        if r["code"]:
            st.code(r["code"], language="python")
            edit_col, run_col = st.columns(2)
            edit_col.button("수동 입력으로 가져오기", key=f"history_edit_{r['id']}",
                            on_click=_load_history_code, args=(r["code"], False))
            run_col.button("다시 실행", key=f"history_run_{r['id']}",
                           on_click=_load_history_code, args=(r["code"], True))


def _render_history_panel() -> None:
    """선택한 데이터셋의 질의·응답 기록.

    최근 1건은 항상 노출하고, 그 이전 기록은 expander 로 접는다.
    (콘솔 영역은 데이터셋 전환 시 비워지므로, 직전 응답을 여기서 바로 볼 수 있어야 한다.)
    """
    me = st.session_state.username
    dn = st.session_state.db_name
    try:
        rows = db.list_queries(me, dn, limit=100)
        n_ok = db.count_queries(me, dn, only_ok=True)
    except Exception as e:
        st.warning(f"질의 기록을 불러오지 못했습니다: {e}")
        return

    st.subheader(f"🗂️ History · `{dn}`")
    st.caption(f"응답 {n_ok}건 · 시도 {len(rows)}건 · 계정 **{me}**")

    if not rows:
        st.info(
            f"`{dn}` 에 대해 **{me}** 계정으로 남긴 질의 기록이 아직 없습니다."
        )
        return

    _render_query_card(rows[0])          # 최신 1건은 항상 노출

    if len(rows) > 1:
        with st.expander(f"이전 기록 {len(rows) - 1}건 더 보기", expanded=False):
            for r in rows[1:]:
                _render_query_card(r)


# ─────────────────────────────────────────────────
# 페이지 본체 (top-level)
# ─────────────────────────────────────────────────

# [0928 수정] 사이드바 'Chat history' 블록 제거.
#   기록의 단일 출처가 SQLite query_log + 아래 History 섹션으로 옮겨가면서
#   세션 messages 기반 목록은 데이터셋과 무관하게 쌓여 stale 값을 보여주는 문제가 있었다.


# ── 헤더 ────────────────────────────────────────
st.title("DP Agent Console")
st.caption("질문 → 코드 생성 → 샌드박스 실행 → ε 원장 기록")


# ── Query target · 대상 DB 선택 (3열: 도넛 / 도메인 / Database) ────
# [0928 수정] 도넛 게이지를 이 컨테이너의 1열로 올리고, KPI 행은 없앴다.
#   실행 순서 주의: 열을 먼저 만들어 위치를 고정하고, 도메인·Database 위젯을 먼저 채운 뒤
#   (선택값 확정 후) 정책을 로드해 마지막에 1열에 도넛을 쓴다.
#   → 화면상으로는 왼쪽이지만 값은 "새로 선택된 데이터셋" 기준으로 계산된다.
with st.container(border=True):
    st.subheader("Query target · 질의 대상 DB")

    col_gauge, col_dom, col_db = st.columns([1.1, 1, 2],
                                            vertical_alignment="center")

    with col_dom:
        dom = st.selectbox("도메인", ab.catalog.domains(), key="db_domain")

    with col_db:
        choices = ab.catalog.names(dom)
        if not choices:
            st.error("`competition/` 아래에서 `all.parquet` 을 찾지 못했습니다.")
            st.stop()
        if st.session_state.db_name not in choices:
            st.session_state.db_name = choices[0]
        st.selectbox(
            "Database", choices, key="db_name",
            # [0928 수정] on_change 콜백으로 이전 데이터셋의 코드·결과를 비운다.
            # 콜백은 스크립트 재실행 전에 실행되므로 깜빡임이 없다.
            # 콜백 시점의 db_name 이 새 값/이전 값 중 무엇인지는 여기서 의존하지 않는다.
            on_change=state.reset_console,
            format_func=lambda n: f"{n} · {ab.catalog.meta(n)['title'][:40]}",
        )

    _meta = ab.catalog.meta(st.session_state.db_name)
    st.markdown(f"**선택된 DB** · `{st.session_state.db_name}`")
    st.caption(
        f"{_meta.get('title', st.session_state.db_name)} · "
        f"{int(_meta.get('n_rows', 0)):,} rows · "
        f"{int(_meta.get('n_cols', 0)):,} columns"
    )


# ── 유효 정책 로드 + 도넛 게이지 ───────────────
# 데이터셋 선택이 반영된 "뒤"에 로드한다. 그래야 총 ε 예산과 누적 소모가
# 같은 데이터셋 기준으로 계산된다.
POLICY = state.apply_effective_policy(st.session_state.db_name)

_total_eps = max(float(POLICY["total_epsilon"]), 1e-9)
_spent     = state.spent_of()   # 선택된 데이터셋에서 소모한 ε (계정·데이터셋별 누적)
_remaining = max(0.0, _total_eps - _spent)
_ratio     = _spent / _total_eps
_tone      = ("success" if _ratio < 0.6
              else ("warning" if _ratio < 0.9 else "danger"))

# [0928 수정] KPI 행 대신 Query target 컨테이너의 1열에 도넛을 쓴다.
with col_gauge:
    st.markdown(
        theme.donut_gauge(
            "누적 소모", _spent, _total_eps,
            unit="ε", tone=_tone,
            sub=f"잔여 {_remaining:.2f} ε",
        ),
        unsafe_allow_html=True,
    )
    st.caption(f"질의당 ε {st.session_state.eps:.2f} · 총 예산 {_total_eps:.2f} ε")


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


# Schema and both input panels share one row.
_render_editor_panel()


# ── History · 선택한 데이터셋의 질의 기록 ────
# [0928 수정] 구분선 아래에 배치. 데이터셋을 바꾸면 내용도 함께 바뀐다.
st.divider()
_render_history_panel()
