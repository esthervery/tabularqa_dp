import streamlit as st
from ui import agent_bridge as ab, state

st.session_state.setdefault("pending_q", None)
st.session_state.setdefault("manual_code", "    return df.shape[0]")
st.session_state.setdefault("last_result", None)

with st.session_state.nav_slot:
    st.markdown("**질의 대상 DB**")
    dom = st.selectbox("도메인", ab.catalog.domains(), key="db_domain")
    choices = ab.catalog.names(dom)

    if not choices:
        st.error("data/ 에서 all.parquet 을 찾지 못했습니다.")
        st.stop()
    if st.session_state.db_name not in choices:
        st.session_state.db_name = choices[0]

    st.selectbox("Database", choices, key="db_name",
                 format_func=lambda n: f"{n} · {ab.catalog.meta(n)['title'][:28]}",
                 label_visibility="collapsed")

    m = ab.catalog.meta(st.session_state.db_name)
    # st.caption(f"{m['n_rows']:,}행 × {m['n_cols']}열 · {m['domain']}")
    # st.caption("🔒 원본 레코드 직접 접근 불가 · 스키마만 노출")


head, badge = st.columns([3, 1], vertical_alignment="center")
with head:
    st.title("DP Agent Console")
    st.caption("질문 → 코드 생성 → 편집기에 주입 → 자동 실행 → DP 보호")
with badge:
    st.success(f"● {st.session_state.db_name}", icon="🗄️")

m1, m2, m3, m4 = st.columns(4)
m1.metric("질의당 ε", f"{st.session_state.eps:.2f}", border=True)
m2.metric("누적 소모", f"{st.session_state.spent:.2f}", border=True)
m3.metric("상한까지 남음",
          f"{max(0.0, st.session_state.eps_cap - st.session_state.spent):.2f}",
          border=True)
m4.metric("질의 수",
          sum(1 for m in st.session_state.messages if m["role"] == "user"),
          border=True)
st.write("")

left, right = st.columns([1.3, 1.5], gap="medium")

# ── 좌: 스키마 ──────────────────────────────────────────────
with left:
    with st.container(border=True, height=560):
        st.markdown("##### 📋 스키마")
        try:
            sch = ab.schema_of(st.session_state.db_name)
            st.caption(f"{len(sch)}개 컬럼 · 값 미리보기 없음")
            kw = st.text_input("검색", placeholder="🔍 컬럼명",
                               label_visibility="collapsed")
            view = sch[sch["column"].str.contains(kw, case=False)] if kw else sch
            st.dataframe(view, hide_index=True, use_container_width=True,
                         height=min(38 * (len(view) + 1) + 3, 400),
                         column_config={
                             "column":   st.column_config.TextColumn("컬럼", width=120),
                             "dtype":    st.column_config.TextColumn("타입", width=300)})
                        #      "non_null": st.column_config.NumberColumn("non-null", width="small"),
                        #  })
        except Exception as e:
            st.warning(f"스키마 로드 실패: {e}")

# ── 우: 코드 편집기 + 결과 + 채팅 입력 ───────────────────────
with right:
    with st.container(border=True, height=560):
        st.markdown("##### ⌨️ 코드")
        # st.code("def answer(df: pd.DataFrame):", language="python")
        slot = st.empty()

        if st.session_state.pending_q:
            q = st.session_state.pending_q
            with slot.container():
                with st.status("에이전트가 코드를 작성 중…", expanded=True) as stt:
                    st.caption("① 스키마로 프롬프트 구성 (원본 레코드 미포함)")
                    code = st.write_stream(
                        ab.stream_code(q, st.session_state.db_name))
                    trace = st.session_state.get("_last_trace", {})
                    st.caption("② 샌드박스 실행")
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
                    st.error("ε 상한을 초과하여 결과를 반환하지 않았습니다.", icon="🚫")
            st.session_state.last_result = {
                "value": out, "ok": ok, "src": "agent",
                "calls": trace.get("n_llm_calls", 0)}
            st.session_state.messages += [
                {"role": "user", "content": q},
                {"role": "assistant",
                 "content": f"결과: **{float(out):,.2f}**" if ok else "결과를 얻지 못했습니다.",
                 "code": code}]
            st.session_state.pending_q = None
            st.rerun()

        slot.text_area("본문", key="manual_code", height=200,
                       label_visibility="collapsed")

        b1, b2 = st.columns([1, 2], vertical_alignment="center")
        if b1.button("▶ 실행", width="stretch", type="primary"):
            if not state.can_spend(st.session_state.eps):
                st.error("ε 상한을 초과했습니다. 관리자에게 예산 증액을 요청하세요.",
                         icon="🚫")
            else:
                r = ab.run_code(st.session_state.manual_code,
                                st.session_state.db_name)
                ok = not str(r).startswith(("__CODE_ERROR__", "__TIMEOUT__"))
                if ok:
                    state.spend(st.session_state.eps, "manual", "직접 코드 실행")
                st.session_state.last_result = {"value": r, "ok": ok,
                                                "src": "manual", "calls": 0}
                st.rerun()
        b2.caption(f"실행 시 ε = {st.session_state.eps} 소모")

        res = st.session_state.last_result
        if res:
            if res["ok"]:
                c1, c2, c3 = st.columns(3)
                c1.metric("실행 결과 (원시값)", f"{float(res['value']):,.2f}",
                          border=True, help="아직 노이즈가 적용되지 않은 참값입니다.")
                c2.metric("소모 ε", f"{st.session_state.eps:.2f}", border=True)
                c3.metric("LLM 호출", res["calls"], border=True)
                # st.caption("⚠️ 현재 단계에서는 라플라스 노이즈가 적용되지 않습니다. "
                #            "표시값은 참값이며, DP 보장은 라운드 루프 연결 후 적용됩니다.")
            else:
                st.error(str(res["value"]), icon="⚠️")

        st.divider()
        if q := st.chat_input("코드를 모르시겠나요? 자연어로 질문하세요"):
            st.session_state.pending_q = q
            st.rerun()