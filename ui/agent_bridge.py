"""dp_agent_wrap 파이프라인 ↔ Streamlit UI 어댑터.

- install_local_loader() : core.utils 의 로더를 로컬 parquet 우선으로 교체.
- get_pipe(...)          : OpenAI Answerer 파이프라인을 캐시로 준비.
- stream_code(...)       : 질문을 받아 생성된 코드를 청크로 흘려보내는 제너레이터.
                           (실제 OpenAI streaming 이 준비되면 이 함수만 교체.)
- run_code(code, db)     : 수동 입력 코드도 동일한 샌드박스로 실행.
"""
import time
import pandas as pd
import streamlit as st
from ui import catalog


def local_load_table(name: str) -> pd.DataFrame:
    return pd.read_parquet(catalog.table_path(name))


def install_local_loader() -> bool:
    """core.utils 의 로더를 로컬 우선으로 갈아끼운다 (HF 다운로드 차단)."""
    try:
        import core.utils as utils
        utils.generic_load_table = local_load_table
        utils.generic_load_sample = lambda n: local_load_table(n).head(20)
        return True
    except Exception:
        return False


install_local_loader()


@st.cache_resource(show_spinner="에이전트 파이프라인 준비 중…")
def get_pipe(model: str = "gpt-4o-mini", temperature: float = 0.0):
    """OpenAIAnswerer 기반 파이프라인. 실패 시 (None, err_msg)."""
    try:
        import dp_agent_wrap as W
        return W.build_pipe_nosr(model=model, temperature=temperature), None
    except Exception as e:
        return None, str(e)


@st.cache_data(show_spinner=False)
def load_df(db_name: str) -> pd.DataFrame:
    return catalog.load_df(db_name)


@st.cache_data(show_spinner=False)
def schema_of(db_name: str) -> pd.DataFrame:
    return catalog.schema_of(db_name)


def stream_code(question: str, db_name: str,
                model: str = "gpt-4o-mini", temperature: float = 0.0):
    """질문을 실행하고 생성된 코드를 12자 청크로 흘려보내는 제너레이터.

    현재 OpenAIAnswerer 가 non-streaming 이라 완성된 코드를 타이핑 효과로 흘린다.
    실제 토큰 스트리밍이 필요하면 Answerer 에 stream=True 경로를 추가하고
    이 함수만 교체하면 된다.

    부수효과: st.session_state._last_trace 에 실행 결과 dict 를 남긴다.
    """
    pipe, err = get_pipe(model, temperature)
    row = {"question": question, "dataset": db_name}

    if pipe is None:
        # 다른 DB의 컬럼을 가리키는 목업 코드는 실행하지 않는다.
        code = "    # 에이전트 파이프라인을 준비하지 못했습니다.\n    return None"
        trace = {"output": None, "code": code, "n_llm_calls": 0,
                 "n_fix_attempts": 0,
                 "final_error": "에이전트 파이프라인 준비에 실패했습니다.",
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
    """수동 입력 코드도 에이전트와 동일한 샌드박스로 실행.

    성공 시 결과값, 실패 시 __CODE_ERROR__/__TIMEOUT__ 접두어 문자열.
    """
    try:
        import dp_agent_wrap as W
        import core.utils as utils
        ex = W.InlineStatementExecutor(utils.generic_load_table, timeout=30)
        return ex((code, db_name))
    except Exception as e:
        return f"__CODE_ERROR__: {e}"
