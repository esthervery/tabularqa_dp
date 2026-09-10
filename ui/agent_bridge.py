"""dp_agent_wrap 파이프라인과 Streamlit UI 사이의 어댑터."""
import os, time
import pandas as pd
import streamlit as st

DB_CHOICES = ["CardBase", "066_IBM_HR", "052_Professional"]   # 데모용 목록


@st.cache_resource(show_spinner="에이전트 파이프라인 준비 중…")
def get_pipe(model: str = "gpt-4o-mini", temperature: float = 0.0):
    try:
        import dp_agent_wrap as W
        return W.build_pipe_nosr(model=model, temperature=temperature), None
    except Exception as e:
        return None, str(e)


@st.cache_data(show_spinner=False)
def load_df(db_name: str) -> pd.DataFrame:
    import core.utils as utils
    return utils.generic_load_table(db_name)


@st.cache_data(show_spinner=False)
def schema_of(db_name: str) -> pd.DataFrame:
    df = load_df(db_name)
    return pd.DataFrame({
        "column": df.columns,
        "dtype": [str(t) for t in df.dtypes],
        "non_null": [int(df[c].notnull().sum()) for c in df.columns],
    })


def stream_code(question: str, db_name: str, model="gpt-4o-mini", temperature=0.0):
    """생성 코드를 조각으로 흘려보내는 제너레이터.

    현재 OpenAIAnswerer 는 non-streaming 이라, 여기서는 완성된 코드를
    타이핑 효과로 흘린다. 진짜 토큰 스트리밍이 필요하면 Answerer 에
    stream=True 경로를 추가하고 이 함수만 교체하면 된다.
    """
    pipe, err = get_pipe(model, temperature)
    row = {"question": question, "dataset": db_name}

    if pipe is None:                       # 목 경로
        code = ("    # The columns used to answer the question: ['Credit_Limit']\n"
                "    # The types of the columns used to answer the question: ['int64']\n"
                "    # The type of the answer: number\n"
                "    return df['Credit_Limit'].mean()")
        trace = {"output": None, "code": code, "n_llm_calls": 0,
                 "n_fix_attempts": 0, "final_error": True, "mock": True,
                 "pipe_error": err}
    else:
        trace = pipe.run_one_traced(row)
        code = trace["code"]

    for line in code.split("\n"):
        for i in range(0, len(line), 12):
            yield line[i:i + 12]
            time.sleep(0.012)
        yield "\n"

    st.session_state._last_trace = trace


def run_code(code: str, db_name: str):
    """수동 입력 코드도 에이전트와 동일한 샌드박스로 실행."""
    try:
        import dp_agent_wrap as W
        import core.utils as utils
        ex = W.InlineStatementExecutor(utils.generic_load_table, timeout=30)
        return ex((code, db_name))
    except Exception as e:
        return f"__CODE_ERROR__: {e}"