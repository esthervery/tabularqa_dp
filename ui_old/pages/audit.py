import pandas as pd
import streamlit as st

if not st.session_state.get("is_admin"):
    st.error("ε 관리자 권한이 필요한 페이지입니다.")
    st.stop()

with st.session_state.nav_slot:
    st.subheader("감사")
    st.metric("기록 수", len(st.session_state.audit))
    st.metric("누적 ε", f"{st.session_state.spent:.2f}")

st.title("📜 Audit Log")
st.caption("에이전트가 DB에 접근한 이력과 예산 소모 내역입니다.")

if st.session_state.audit:
    st.dataframe(pd.DataFrame(st.session_state.audit),
                 use_container_width=True, hide_index=True)
else:
    st.info("기록이 없습니다.")