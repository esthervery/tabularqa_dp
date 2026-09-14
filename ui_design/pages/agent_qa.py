"""DP Agent Console — 라이브 코딩 스타일.

레이아웃
  [Sidebar]  DB 선택 · 채팅 히스토리(요약)
  [Main]     상단 KPI 게이지 → 코드 편집기(에이전트/수동 탭) → 결과
  [Bottom]   st.chat_input 자연어 질문
"""
import streamlit as st
from ui_design import agent_bridge as ab, db, state, theme

theme.inject_global_css()

# 현재 확정된 정책 + 개인 상한을 세션에 반영
state.apply_active_policy()

st.session_state.setdefault("pending_q", None)
st.session_state.setdefault("manual_code", "    return df.shape[0]")
st.session_state.setdefault("last_result", None)


# ── 사이드바 컨텍스트 ────────────────────────────────────────
with st.session_state.nav_slot:
    theme.eyebrow("Query Target")
    dom = st.selectbox("도메인", ab.catalog.domains(), key="db_domain",
                       label_visibility="collapsed")
    choices = ab.catalog.names(dom)
    if not choices:
        st.error("`competition/` 아래에서 `all.parquet` 을 찾지 못했습니다.")
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
    m = ab.catalog.meta(st.session_state.db_name)
    # st.markdown(
    #     f'<div style="font-size:11.5px;color:#64748b;'
    #     f'margin:-4px 0 14px 0;font-variant-numeric:tabular-nums;">'
    #     f'{m["n_rows"]:,} rows × {m["n_cols"]} cols · <em>{m["domain"]}</em>'
    #     f'</div>',
    #     unsafe_allow_html=True,
    # )

    st.markdown("---")
    theme.eyebrow("Chat History")
    msgs = st.session_state.messages
    if not msgs:
        st.markdown(
            '<div style="font-size:12px;color:#94a3b8;padding:6px 0;">'
            '아직 질문이 없습니다.</div>',
            unsafe_allow_html=True,
        )
    else:
        # 사용자 질의만 최근 5개 노출
        user_msgs = [m for m in msgs if m["role"] == "user"][-5:]
        for i, mm in enumerate(reversed(user_msgs), 1):
            snippet = mm["content"][:36] + ("…" if len(mm["content"]) > 36 else "")
            st.markdown(
                f'<div style="font-size:12.5px;color:#0f172a;'
                f'padding:6px 8px;border-radius:8px;background:white;'
                f'border:1px solid #e2e8f0;margin-bottom:6px;">'
                f'<span style="color:#64748b;font-size:10.5px;'
                f'font-weight:600;letter-spacing:.05em;">Q{i}</span>'
                f'<div style="margin-top:2px;">{snippet}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ── 메인 헤더 ────────────────────────────────────────────────
head_l, head_r = st.columns([3, 1.2], vertical_alignment="center")
with head_l:
    st.markdown(
        '<h1 style="margin:0 0 4px 0;">DP Agent Console</h1>'
        '<div style="color:#64748b;font-size:14px;">'
        '질문 → 코드 생성 → 샌드박스 실행 → ε 원장 기록'
        '</div>',
        unsafe_allow_html=True,
    )
with head_r:
    st.markdown(
        f'<div style="text-align:right;">'
        f'{theme.pill(st.session_state.db_name, "primary")}'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)


# ── KPI 게이지 3개 ───────────────────────────────────────────
eps_cap = max(st.session_state.eps_cap, 1e-9)
spent = st.session_state.spent
remaining = max(0.0, eps_cap - spent)
ratio = spent / eps_cap
tone = "success" if ratio < 0.6 else ("warning" if ratio < 0.9 else "danger")

g1, g2, g3 = st.columns(3)
with g1:
    st.markdown(
        theme.donut_gauge(
            "누적 소모", spent, eps_cap,
            unit="ε", tone=tone,
            sub=f"잔여 {remaining:.2f} ε",
        ),
        unsafe_allow_html=True,
    )
with g2:
    n_queries = sum(1 for m in st.session_state.messages if m["role"] == "user")
    st.markdown(
        f'<div class="dp-gauge-card">'
        f'  <div style="width:44px;height:44px;border-radius:10px;'
        f'background:#eef2ff;color:#4338ca;display:flex;'
        f'align-items:center;justify-content:center;'
        f'font-size:20px;font-weight:700;">Σ</div>'
        f'  <div class="dp-gauge-meta">'
        f'    <div class="lbl">Queries this session</div>'
        f'    <div class="val">{n_queries}</div>'
        f'    <div class="sub">질의당 ε · {st.session_state.eps:.2f}</div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )
with g3:
    st.markdown(
        f'<div class="dp-gauge-card">'
        f'  <div style="width:44px;height:44px;border-radius:10px;'
        f'background:#ecfdf5;color:#047857;display:flex;'
        f'align-items:center;justify-content:center;'
        f'font-size:20px;">🔒</div>'
        f'  <div class="dp-gauge-meta">'
        f'    <div class="lbl">Data Access</div>'
        f'    <div class="val">Sandbox</div>'
        f'    <div class="sub">원본 레코드 직접 접근 불가</div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)


# ── 라이브 코딩: 스키마 + 코드 편집기 ───────────────────────
left, right = st.columns([1, 1.55], gap="medium")

with left:
    with st.container(border=True, height=540):
        theme.eyebrow("Schema")
        try:
            sch = ab.schema_of(st.session_state.db_name)
            st.markdown(
                f'<div style="font-size:12px;color:#64748b;'
                f'margin:-6px 0 8px 0;">'
                f'{len(sch)}개 컬럼 · 값 미리보기 없음 🔒</div>',
                unsafe_allow_html=True,
            )
            kw = st.text_input("검색", placeholder="🔍 컬럼명 필터",
                               label_visibility="collapsed")
            view = sch[sch["column"].str.contains(kw, case=False)] if kw else sch
            st.dataframe(
                view, hide_index=True, width="stretch",
                height=min(38 * (len(view) + 1) + 3, 400),
                column_config={
                    "column": st.column_config.TextColumn("컬럼", width=140),
                    "dtype":  st.column_config.TextColumn("타입", width=280),
                },
            )
        except Exception as e:
            st.warning(f"스키마 로드 실패: {e}")

with right:
    with st.container(border=True, height=540):
        # 탭: Agent 생성 코드 vs 수동 코드
        tab_agent, tab_manual = st.tabs(["🤖 Agent", "✍️ 수동 편집"])

        with tab_agent:
            slot = st.empty()
            if st.session_state.pending_q:
                q = st.session_state.pending_q
                with slot.container():
                    with st.status("에이전트가 코드를 작성 중…",
                                   expanded=True) as stt:
                        st.caption("① 스키마로 프롬프트 구성 (원본 레코드 미포함)")
                        code = st.write_stream(
                            ab.stream_code(q, st.session_state.db_name))
                        trace = st.session_state.get("_last_trace", {})
                        st.caption("② 샌드박스에서 실행")
                        stt.update(
                            label="완료" if not trace.get("final_error") else "실행 실패",
                            state="complete" if not trace.get("final_error") else "error",
                            expanded=False)

                st.session_state.manual_code = code
                out = trace.get("output")
                ok = out is not None and not trace.get("final_error")
                if ok:
                    if not state.spend(st.session_state.eps, "query", q):
                        ok = False
                        out = None
                        st.error(
                            "ε 상한을 초과하여 결과를 반환하지 않았습니다. "
                            "Budget Requests 페이지에서 예산을 신청하세요.",
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
            else:
                last = st.session_state.get("last_result")
                if last and last.get("src") == "agent":
                    st.code(st.session_state.manual_code, language="python")
                else:
                    st.markdown(
                        '<div style="padding:60px 20px;text-align:center;'
                        'color:#94a3b8;font-size:14px;">'
                        '아직 에이전트가 생성한 코드가 없습니다.<br/>'
                        '아래 채팅창에 자연어로 질문해보세요.'
                        '</div>',
                        unsafe_allow_html=True,
                    )

        with tab_manual:
            st.text_area("코드 본문", key="manual_code", height=220,
                         label_visibility="collapsed",
                         help="`return` 으로 스칼라 값을 반환하는 함수 본문을 작성하세요.")
            b1, b2 = st.columns([1, 2], vertical_alignment="center")
            if b1.button("▶ 실행", width="stretch", type="primary",
                         key="run_manual"):
                if not state.can_spend(st.session_state.eps):
                    st.error(
                        "ε 상한을 초과했습니다. "
                        "Budget Requests 페이지에서 예산 증액을 신청하세요.",
                        icon="🚫",
                    )
                else:
                    r = ab.run_code(st.session_state.manual_code,
                                    st.session_state.db_name)
                    ok = not str(r).startswith(("__CODE_ERROR__", "__TIMEOUT__"))
                    if ok:
                        state.spend(st.session_state.eps, "manual",
                                    "직접 코드 실행")
                    st.session_state.last_result = {
                        "value": r, "ok": ok,
                        "src": "manual", "calls": 0,
                    }
                    st.rerun()
            b2.markdown(
                f'<div style="text-align:right;color:#64748b;font-size:12px;">'
                f'실행 시 <b>ε = {st.session_state.eps:.2f}</b> 소모'
                f'</div>',
                unsafe_allow_html=True,
            )

        # 실행 결과 (탭 아래 공통)
        res = st.session_state.last_result
        if res:
            st.markdown("<div style='height:8px;'></div>",
                        unsafe_allow_html=True)
            if res["ok"]:
                c1, c2, c3 = st.columns(3)
                try:
                    val_str = f"{float(res['value']):,.2f}"
                except Exception:
                    val_str = str(res["value"])[:24]
                c1.metric("실행 결과", val_str, border=True,
                          help="아직 노이즈가 적용되지 않은 참값입니다.")
                c2.metric("소모 ε", f"{st.session_state.eps:.2f}", border=True)
                c3.metric("LLM 호출", res["calls"], border=True)
            else:
                st.error(str(res["value"]), icon="⚠️")

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

# ── 하단 자연어 채팅 입력 ────────────────────────────────────
if q := st.chat_input("코드를 모르시겠나요? 자연어로 질문하세요 "
                       "(예: 신용한도 평균은 얼마인가요?)"):
    st.session_state.pending_q = q
    st.rerun()
