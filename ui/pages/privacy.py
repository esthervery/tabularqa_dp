import pandas as pd
import streamlit as st
from ui import agent_bridge as ab, state

if not st.session_state.get("is_admin"):
    st.error("ε 관리자 권한이 필요한 페이지입니다.")
    st.stop()

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


    # st.subheader("예산 파라미터")
    st.markdown("\n")
    st.markdown("**예산 파라미터**")
    st.slider("질의당 ε", 0.25, 2.0, key="eps", step=0.25)
    st.slider("전체 상한 ε", 1.0, 50.0, key="eps_cap", step=1.0)
    st.slider("목표 상대폭", 0.005, 0.1, key="target_rel_width",
              step=0.005, format="%.3f")
    st.slider("step (다음 라운드 예산 배율)", 1.05, 1.5, key="step", step=0.01)
    st.metric("누적 소모", f"{st.session_state.spent:.2f}")


head, badge = st.columns([3, 1], vertical_alignment="center")
with head:
    st.title("🎚️ Privacy Budget")
    st.caption("""상대폭 기반 라운드 방식으로 배정 예산을 키웁니다. 
    정지 규칙: 상대폭이 목표 이하가 되는 첫 라운드에서 종료.""")
with badge:
    st.success(f"● {st.session_state.db_name}", icon="🗄️")
# st.title("🎚️ Privacy Budget")
# st.caption("상대폭 기반 라운드 방식으로 배정 예산을 키웁니다. "
#            "정지 규칙: 상대폭이 목표 이하가 되는 첫 라운드에서 종료.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("질의당 ε", st.session_state.eps, border=True)
c2.metric("현재 배정 예산", f"{st.session_state.eps_alloc:.2f}", border=True)
c3.metric("목표 상대폭", f"{st.session_state.target_rel_width:.1%}", border=True)
c4.metric("라운드 수", len(st.session_state.rounds), border=True)

st.progress(min(1.0, st.session_state.spent / max(st.session_state.eps_cap, 1e-9)),
            text=f"누적 소모 {st.session_state.spent:.2f} / 상한 {st.session_state.eps_cap:.1f}")

if st.button("라운드 실행", type="primary"):
    st.info("run_fixed_k / explore 루프를 여기에 연결하세요.", icon="🔧")

if st.session_state.rounds:
    df = pd.DataFrame(st.session_state.rounds)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.line_chart(df.set_index("round")[["rel_width"]])
else:
    st.info("아직 실행된 라운드가 없습니다.")