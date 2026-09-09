import os, numpy as np, pandas as pd, boto3
from pathlib import Path
from dotenv import load_dotenv
from scipy import stats

import core.utils as utils
from main import instantiate_pipeline_from_yaml

# ── 1. CardBase를 저장소 로더가 찾는 위치에 놓는다 ──────────────
DS_NAME = "CardBase"
COL     = "Credit_Limit"
QUESTION = f"What is the average {COL}?"

def prepare_dataset(csv_path="data/CardBase.csv", root="./competition"):
    d = Path(root) / DS_NAME
    d.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(csv_path)
    df.to_parquet(d / "all.parquet")
    df.head(20).to_parquet(d / "sample.parquet")   # lite용
    return df

# ── 2. 파이프라인 1회 = 에이전트 1회 응답 ──────────────────────
def build_pipe(config="config/claude3.5-sonnet.yaml", temperature=None):
    load_dotenv()
    client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name="us-west-2",
    )
    pipe, model = instantiate_pipeline_from_yaml(
        config_path=config,
        exemplar_indices=[(17,140),(0,132),(28,286),(31,303),(4,246),
                          (24,175),(20,176),(8,141),(14,12)],
        annotations_filename="annotation/annotations_cot.json",
        client=client, debug=False, lite=False,
    )
    if temperature is not None:                      # 변동성 관찰용
        pipe.main_pipeline.answerer.temperature = temperature
    return pipe

def ask_agent(pipe):
    """에이전트 1회 호출 → (값, 원본출력). 실패 시 값은 np.nan."""
    row = {"question": QUESTION, "dataset": DS_NAME}
    out = pipe(row)
    s = str(out)
    if s.startswith("__CODE_ERROR__") or s.startswith("__TIMEOUT__"):
        return np.nan, s
    try:
        return float(out), s
    except (TypeError, ValueError):
        return np.nan, s


# ── OpenAI answerer (Bedrock Claude 대체) ──────────────────────
from openai import OpenAI
from core.model_calls import Answerer

class OpenAIAnswerer(Answerer):
    """AILS-NTUA 파이프라인용 OpenAI answerer.
    입력: ClaudeChatBuilder가 만든 {"messages":[{role,content:[{type,text}]}]} dict
    출력: (응답문자열, input_tokens, output_tokens)
    """
    pit = 0.00015   # gpt-4o-mini 기준 1K 입력 토큰당 USD
    pot = 0.0006    # 1K 출력 토큰당 USD

    def __init__(self, model="gpt-4o-mini", temperature=0.0,
                 top_p=1.0, max_gen_len=300, client=None):
        super().__init__()
        self.model_id = model
        self.temperature = temperature
        self.top_p = top_p
        self.max_gen_len = max_gen_len
        self.client = client or OpenAI()   # OPENAI_API_KEY 환경변수 사용

    @staticmethod
    def _flatten(prompt):
        """Claude payload → (system, user_text). assistant prefill을 user로 전환."""
        parts = []
        for m in prompt["messages"]:
            c = m["content"]
            txt = c if isinstance(c, str) else "\n".join(b["text"] for b in c)
            parts.append(txt)
        body = "\n".join(parts)
        instr = (
            "Continue the following Python code. Complete the body of `answer(df)` "
            "only. Output the continuation itself with 4-space indentation, no "
            "markdown fences, no explanation, and end with a `return` statement.\n\n"
        )
        return instr + body

    def __call__(self, prompt, custom_gen_parameters=None):
        try:
            kw = dict(temperature=self.temperature, top_p=self.top_p,
                      max_tokens=self.max_gen_len)
            if custom_gen_parameters:
                kw.update(custom_gen_parameters)
            r = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": self._flatten(prompt)}],
                **kw,
            )
            out = r.choices[0].message.content or ""
            out = out.replace("```python", "").replace("```", "")
            if not out.startswith("    "):          # 후처리기가 4칸 들여쓰기를 기대
                out = "\n".join("    " + l.lstrip() if l.strip() else l
                                for l in out.split("\n"))
            return out, r.usage.prompt_tokens, r.usage.completion_tokens
        except Exception as e:
            print(f"ERROR: Can't invoke '{self.model_id}'. Reason: {e}")
            return "", 0, 0

    def __str__(self):
        return (f"OpenAIAnswerer(Answerer)\n\tmodel_id: {self.model_id}\n\t"
                f"temperature: {self.temperature}\n\ttop_p: {self.top_p}\n\t"
                f"max_gen_len: {self.max_gen_len}")


import threading, ast
from core.executors import Executor

class InlineStatementExecutor(Executor):
    """Windows 호환 실행기. multiprocessing 대신 thread + timeout."""
    def __init__(self, loader, timeout: int = 60):
        super().__init__(loader)
        self.timeout = timeout

    def __call__(self, inp):
        statement, dataset = inp
        total = "global ans\n\ndef answer(df):\n" + statement + "\nans = answer(df)"
        try:
            df = self.loader(dataset)
        except Exception as e:
            return f"__CODE_ERROR__: {e}"

        box = {}
        def work():
            try:
                g = {"df": df, "ans": None, "pd": pd, "np": np, "ast": ast}
                exec(total, g, {})
                box["ans"] = g.get("ans", None)
            except Exception as e:
                box["err"] = f"__CODE_ERROR__: {e}"

        t = threading.Thread(target=work, daemon=True)
        t.start(); t.join(self.timeout)
        if t.is_alive():
            return "__TIMEOUT__"
        return box.get("err", box.get("ans", "__CODE_ERROR__: No result returned"))

    def __str__(self):
        return f"InlineStatementExecutor(Executor)\n\tloader: {self.loader}\n\ttimeout: {self.timeout}"

import core.prompt_generators as pgs
import core.postprocessors as postprocessors
import core.pipelines as pipelines
import core.utils as utils


class SchemaOnlyZeroShot(pgs.ZeroShotGenerator):
    """TD + CD만 포함. 샘플 행(SR) 없음."""
    def __init__(self, loader):
        super().__init__(loader)

    def __call__(self, row):
        df = self.loader(row['dataset'])
        info = "\n        ".join(pgs.custom_info_csv_2(df).split('\n'))
        return f"""\
# TODO: complete the following function. It should give the answer to: {row['question']}
def answer(df: pd.DataFrame):
    \"\"\"
        {info}
    \"\"\"


    df.columns = {list(df.columns)}
    """

    def __str__(self):
        return f"SchemaOnlyZeroShot(loader={self.loader})"

# 예시 렌더링이 FewShot.__init__에서 일어나기 때문에, 생성기를 먼저 만든 뒤에
# 생성기를 넘겨서 조립부를 새로 생성해야 함
def build_pipe_nosr(model="gpt-4o-mini", temperature=0.0, debug=False):
    load_dotenv()
    loader = utils.generic_load_table

    _, exemplars = utils.annotation_reader("annotation/annotations_cot.json")
    idx = [17, 0, 28, 31, 4, 24, 20, 8, 14]          # main.py의 exemplar_indices 첫 성분
    shots = [exemplars[i] for i in idx]

    zs = SchemaOnlyZeroShot(loader)                   # 실제 질문용
    eb = pgs.ExemplarBuilder(loader, SchemaOnlyZeroShot(loader))   # 예시용(별도 인스턴스)
    few = pgs.FewShotChainOfThoughtBuilderWithTypesRowsAndPredictingResultingTypesVol2(
        loader, zs, eb, shots=shots)
    wrapped = pgs.ClaudeMessageEmbeddingPromptGenerator(loader, few)

    post = postprocessors.TillReturnLinePostProcessorMultipleIndents(
        loader, prefix=4,
        first_prefix='    # The columns used to answer the question: ')

    main_pipe = pipelines.Pipeline(
        wrapped,
        OpenAIAnswerer(model=model, temperature=temperature, max_gen_len=300),
        post,
        InlineStatementExecutor(loader),
        debug=debug,
    )

    ef_gen = pgs.ErrorFixingGeneratorClaudeVol2(
        loader, SchemaOnlyZeroShot(loader), num_rows=10)
    ef_pipe = pipelines.ErrorFixPipeline(
        ef_gen,
        OpenAIAnswerer(model=model, temperature=temperature, max_gen_len=1000),
        post,
        InlineStatementExecutor(loader),
    )

    return pipelines.ErrorFixingAndTimeoutPipeline(main_pipe, ef_pipe, 600, num_attempts=2)