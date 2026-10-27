"""dp_agent_wrap 파이프라인 ↔ Streamlit UI 어댑터.

- install_local_loader() : core.utils 의 로더를 로컬 parquet 우선으로 교체.
- get_pipe(...)          : OpenAI Answerer 파이프라인을 캐시로 준비.
- stream_code(...)       : 질문을 받아 생성된 코드를 청크로 흘려보내는 제너레이터.
                           준비 실패 시 mock 대신 PipelineUnavailable 을 올린다.
- run_code(code, db)     : 수동 입력 코드도 동일한 샌드박스로 실행.

[1025 수정] Few-shot 예시를 '로컬에 있는 데이터셋'으로만 채운다.
    dp_agent_wrap.build_pipe_nosr 는 annotation/annotations_cot.json 의 예시 9개를
    FewShot 으로 넣는데, FewShotChainOfThought...Vol2.__init__ 이 생성 시점에
    exemplar_builder 를 즉시 호출한다 → exemplar_builder 가 loader(예시의 dataset)
    를 부른다. 예시 데이터셋은 CardBench 원본(007_Fifa, 000_CardBase …)이라
    데모 저장소(competition/ 에 5개만 존재)에서는

        FileNotFoundError: 로컬 카탈로그에 '007_Fifa' 없음

    으로 파이프라인 생성 자체가 실패했다. 즉 데모에서는 FIFA 를 고르지 않았는데도
    FIFA 이름이 오류로 뜬다 — 예시 로딩이 실패한 것이다.

    그래서 로컬 카탈로그에 있는 예시만 shots 로 쓰고, 하나라도 없으면 shots=[] 로
    zero-shot 파이프라인을 만든다. 프롬프트에 없는 데이터셋의 스키마를 지어내지
    않으므로 환각이 없고, 데모 5개 데이터셋은 항상 정상 동작한다.
"""
import time


import pandas as pd
import streamlit as st
from ui import catalog
from ui.utils import boot


class PipelineUnavailable(RuntimeError):
    """에이전트 파이프라인이 준비되지 않아 질의를 진행할 수 없음.

    이전에는 준비 실패 시 mock 코드를 반환했다. 그러면 데모에서 실행되지도 않는
    가짜 코드가 결과처럼 표시되어 신뢰도를 깨뜨린다. 그래서 예외를 올리고,
    UI(ui/pages/console.py)가 이를 잡아 사유를 보여준다.

    속성:
        reason : 실패 사유 문자열(get_pipe 가 돌려준 err, 또는 import 오류).
    """

    def __init__(self, reason: str | None = None):
        self.reason = reason or "알 수 없는 오류"
        super().__init__(self.reason)


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


def _local_exemplars() -> tuple[list, int]:
    """로컬에 실제로 있는 예시만 고른다.

    Returns (shots, skipped) — skipped 는 로컬에 없어서 뺀 예시 수.
    """
    try:
        import dp_agent_wrap as W
        import core.utils as utils
        _, exemplars = utils.annotation_reader(W.ANNOTATIONS_FILE)
        cand = [exemplars[i] for i in (x[0] for x in W.EXEMPLAR_INDICES)]
    except Exception:
        # 어노테이션 파일·HF 캐시가 없으면 예시 없이 간다 (zero-shot).
        return [], -1

    have = set(catalog.names())
    shots = [(row, cot) for (row, cot) in cand if row.get("dataset") in have]
    return shots, len(cand) - len(shots)


def build_pipe_local(model: str = "gpt-4o-mini", temperature: float = 0.0):
    """build_pipe_nosr 과 같은 구조이되, 예시는 로컬 데이터셋만 사용한다.

    예시가 하나라도 빠지면 shots=[] (zero-shot). FewShot 생성기는 shots 가 비면
    exemplar_builder 를 한 번도 호출하지 않으므로 loader 도 불리지 않는다.
    """
    import dp_agent_wrap as W
    import core.pipelines as pipelines
    import core.postprocessors as postprocessors
    import core.prompt_generators as prompt_generators
    import core.utils as utils

    loader = utils.generic_load_table
    shots, _skipped = _local_exemplars()

    zs = W.SchemaOnlyZeroShot(loader)
    exemplar_builder = prompt_generators.ExemplarBuilder(loader, zs)
    fewshot = prompt_generators.FewShotChainOfThoughtBuilderWithTypesRowsAndPredictingResultingTypesVol2(
        loader, zs, exemplar_builder, shots=shots)
    pg = prompt_generators.ClaudeMessageEmbeddingPromptGenerator(loader, fewshot)

    post_main = postprocessors.TillReturnLinePostProcessorMultipleIndents(
        loader, prefix=4,
        first_prefix="    # The columns used to answer the question: ")

    main_pipe = pipelines.Pipeline(
        pg,
        W.OpenAIAnswerer(None, model=model, temperature=temperature,
                         max_gen_len=300),
        post_main,
        W.InlineStatementExecutor(loader, timeout=60),
    )

    post_fix = postprocessors.TillReturnLinePostProcessorMultipleIndents(
        loader, prefix=4, first_prefix="    ")

    fix_pipe = pipelines.ErrorFixPipeline(
        prompt_generators.ErrorFixingGeneratorClaudeVol2(
            loader, W.SchemaOnlyZeroShot(loader)),
        W.OpenAIAnswerer(None, model=model, temperature=temperature,
                         max_gen_len=1000),
        post_fix,
        W.InlineStatementExecutor(loader, timeout=60),
    )

    return W.SafeErrorFixingPipeline(main_pipe, fix_pipe,
                                     max_timeout=300, num_fix_attempts=2)


@st.cache_resource(show_spinner="에이전트 파이프라인 준비 중…")
def get_pipe(model: str = "gpt-4o-mini", temperature: float = 0.0):
    """파이프라인. 실패 시 (None, err_msg).

    ① 로컬 예시로 직접 조립 → ② 그래도 실패하면 원본 build_pipe_nosr 로 폴백.
    """
    try:
        return build_pipe_local(model=model, temperature=temperature), None
    except Exception as e1:
        try:
            import dp_agent_wrap as W
            return W.build_pipe_nosr(model=model, temperature=temperature), None
        except Exception as e2:
            return None, f"{type(e2).__name__}: {e2}  (로컬 조립 실패: {e1})"


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
    # 워밍업이 끝날 때까지 대기한다. 보통은 사용자가 로그인하는 동안
    # 이미 끝나 있어 즉시 통과한다. 준비 전이면 스피너를 띄우고 기다린다.
    if not boot.is_ready():
        with st.spinner("에이전트 파이프라인 준비 중…"):
            boot.wait_ready()

    pipe, err = get_pipe(model, temperature)
    row = {"question": question, "dataset": db_name}

    if pipe is None:
        raise PipelineUnavailable(err)

    trace = pipe.run_one_traced(row)
    code = trace["code"]

    for line in code.split("\n"):
        for i in range(0, len(line), 12):
            yield line[i:i + 12]
            time.sleep(0.012)
        yield "\n"

    st.session_state._last_trace = trace


def run_code(code: str, db_name: str) -> dict:
    """수동 입력 코드를 별도 프로세스에서 실행한다.

    반환: {"ok": bool, "value": Any, "message": str}
    에이전트 파이프라인(openai/botocore)에 의존하지 않는다.
    """
    from ui.manual_executor import execute
    try:
        table = catalog.table_path(db_name)
    except Exception:
        return {"ok": False, "message": "선택한 데이터셋을 불러오지 못했습니다."}
    return execute(code, str(table))