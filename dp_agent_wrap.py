"""
SR(샘플 행) 없이 스키마만 노출하는 DataBench 파이프라인 래퍼.

위협 모델: 프롬프트에는 컬럼명, dtype, 원소의 파이썬 타입, 컬럼별 non-null 개수만
포함되며 개별 레코드 값은 포함되지 않는다.
(non-null 개수는 데이터 의존적 통계이므로 SENS와 함께 공개 정보로 가정한다.)
"""

import sys

# [수정 1] core/prompt_generators.py 는 f-string 치환식 안에서 백슬래시를 쓴다.
# 이는 PEP 701(Python 3.12)에서야 허용된 문법이라 3.11 이하에서는 import 시점에
# SyntaxError 가 난다. 아래 import 보다 먼저 막아서 원인을 분명히 한다.
if sys.version_info < (3, 12):
    raise RuntimeError(
        f"core/* 모듈은 Python 3.12+ 가 필요합니다 (현재 {sys.version_info.major}.{sys.version_info.minor}). "
        "f-string 치환식 내 백슬래시(PEP 701) 때문입니다."
    )

import ast
import os
import re
import textwrap
import threading

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

import core.executors as executors
import core.pipelines as pipelines
import core.postprocessors as postprocessors
import core.prompt_generators as prompt_generators
import core.utils as utils

# main.py 와 동일한 exemplar 선택
EXEMPLAR_INDICES = [(17, 140), (0, 132), (28, 286), (31, 303), (4, 246),
                    (24, 175), (20, 176), (8, 141), (14, 12)]
ANNOTATIONS_FILE = "annotation/annotations_cot.json"


# ======================================================================
# 1. SR 을 제거한 Zero-Shot 생성기 (TD + CD 만)
# ======================================================================
class SchemaOnlyZeroShot(prompt_generators.ZeroShotGenerator):
    """원본 ZeroShotDetailedTypesRowsExValuesNullsOneLineRowsVol2 에서
    'The first N rows from the dataframe' 블록만 제거한 버전.
    나머지 레이아웃(공백/개행)은 FewShot 이 이어붙일 때 깨지지 않도록 그대로 유지한다.

    주의: f-string 치환식 안에 백슬래시를 쓰지 않는다(3.12 미만에서도 파싱은 되게).
    """

    def __init__(self, loader, num_rows: int = 0, lite: bool = False):
        super().__init__(loader)
        self.num_rows = 0          # SR 없음. 인자는 YAML 호환용으로만 받는다.
        self.lite = lite

    def __call__(self, row) -> str:
        df = self.loader(row["dataset"])
        info = "\n        ".join(
            prompt_generators.custom_info_csv_2(df).split("\n")
        )
        return (
            "# TODO: complete the following function. It should give the answer to: "
            + row["question"] + "\n"
            "def answer(df: pd.DataFrame):\n"
            '    """\n'
            "        " + info + "\n"
            '    """\n'
            "\n\n"
            "    df.columns = " + repr(list(df.columns)) + "\n"
            "    "
        )

    def __str__(self):
        return f"SchemaOnlyZeroShot(no sample rows, lite={self.lite})"


# ======================================================================
# 2. OpenAI Answerer (프리필 → user 메시지 접기)
# ======================================================================
_CONTINUE_INSTRUCTION = """\
You are completing a Python function. Below is an unfinished code block.
Continue it EXACTLY where it stops and output ONLY the continuation.

Rules:
- Do not repeat any part of the given code.
- Do not write explanations and do not use markdown code fences.
- Your first line continues the last, unfinished line of the given code.
- Every following line of the function body is indented by exactly 4 spaces
  (nested blocks add 4 more).
- Finish with a single top-level `return` statement.
"""

_FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*$")

# max_tokens 대신 max_completion_tokens 를 요구하고 temperature 를 고정값으로만
# 받는 계열. 새 모델을 쓸 때는 여기에 추가하거나 reasoning=True 로 넘긴다.
_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5")


class OpenAIAnswerer:
    """Claude 스타일 payload({'messages': [...]})를 받아 OpenAI Chat Completions 로 보낸다.

    OpenAI 는 assistant 프리필(이어 쓰기)을 지원하지 않으므로 assistant 메시지를
    user 메시지 끝에 붙이고, '이어서 쓰라'는 지시문을 앞에 둔다.
    """

    def __init__(self, client=None, model="gpt-4o-mini", temperature=0.0,
                 top_p=1.0, max_gen_len=300, reasoning=None,
                 pit=0.0, pot=0.0):
        self.client = client or OpenAI()
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.max_gen_len = max_gen_len
        self.reasoning = (
            reasoning if reasoning is not None
            else model.startswith(_REASONING_PREFIXES)
        )
        # 비용 누적(core.cost.CostAccumulator)용 단가. 실제 값은 호출부에서 지정.
        self.pit = pit
        self.pot = pot

    @staticmethod
    def _flatten(payload) -> str:
        if isinstance(payload, str):
            return _CONTINUE_INSTRUCTION + "\n" + payload
        user_parts, assistant_parts = [], []
        for m in payload["messages"]:
            text = "".join(c["text"] for c in m["content"])
            (user_parts if m["role"] == "user" else assistant_parts).append(text)
        chunks = [_CONTINUE_INSTRUCTION]
        if user_parts:
            chunks.append("\n\n".join(user_parts))
        chunks.append("### Unfinished code (continue from the very end):\n"
                      + "\n\n".join(assistant_parts))
        return "\n\n".join(chunks)

    @staticmethod
    def _normalize(text: str) -> str:
        """[수정 4] 첫 줄은 잘린 CUAT 주석의 연장이므로 그대로 두고,
        나머지 줄은 공통 들여쓰기를 제거한 뒤 4칸으로 한 번에 민다.
        (기존 '    ' + l.lstrip() 방식은 중첩 블록을 평탄화해 로직을 깨뜨렸다.)
        """
        lines = [l for l in text.split("\n") if not _FENCE.match(l)]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return "    return None"
        head, tail = lines[0].strip(), lines[1:]
        if not tail:
            return head
        body = textwrap.indent(textwrap.dedent("\n".join(tail)), "    ")
        return head + "\n" + body

    def __call__(self, prompt, custom_gen_parameters=None):
        kwargs = {
            "model": self.model,
            "messages": [{"role": "user", "content": self._flatten(prompt)}],
        }
        # [수정 9] 추론 계열은 max_tokens/temperature/top_p 를 거부한다.
        if self.reasoning:
            kwargs["max_completion_tokens"] = self.max_gen_len
        else:
            kwargs["max_tokens"] = self.max_gen_len
            kwargs["temperature"] = self.temperature
            kwargs["top_p"] = self.top_p
        if custom_gen_parameters:
            kwargs.update(custom_gen_parameters)

        try:
            r = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            print(f"ERROR: Can't invoke '{self.model}'. Reason: {e}")
            return "", 0, 0

        text = r.choices[0].message.content or ""
        usage = getattr(r, "usage", None)
        return (
            self._normalize(text),
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
        )

    def __str__(self):
        return (f"OpenAIAnswerer(Answerer)\n\tmodel: {self.model}"
                f"\n\ttemperature: {self.temperature}\n\ttop_p: {self.top_p}"
                f"\n\tmax_gen_len: {self.max_gen_len}\n\treasoning: {self.reasoning}")


# ======================================================================
# 3. 스레드 기반 실행기 (Windows spawn/pickle 회피)
# ======================================================================
class InlineStatementExecutor(executors.Executor):
    def __init__(self, loader, timeout: int = 60):
        super().__init__(loader)
        self.timeout = timeout      # ErrorFixingAndTimeoutPipeline 이 이 속성을 건드린다

    def __call__(self, inp):
        statement, dataset = inp
        try:
            df = self.loader(dataset)
        except Exception as e:
            return f"__CODE_ERROR__: table load failed: {e}"

        code = "def answer(df):\n" + statement + "\n"
        box = {}

        def work():
            try:
                ns = {"pd": pd, "np": np, "ast": ast}
                exec(code, ns, ns)
                box["ans"] = ns["answer"](df)
            except Exception as e:
                box["err"] = f"__CODE_ERROR__: {type(e).__name__}: {e}"

        t = threading.Thread(target=work, daemon=True)
        t.start()
        t.join(self.timeout)
        if t.is_alive():
            return "__TIMEOUT__"
        if "err" in box:
            return box["err"]
        return box.get("ans")

    def __str__(self):
        return (f"InlineStatementExecutor(Executor)\n\tloader: {self.loader}"
                f"\n\ttimeout: {self.timeout}\n")


# ======================================================================
# 4. 재시도 의미를 명확히 한 상위 파이프라인
# ======================================================================
class SafeErrorFixingPipeline(pipelines.ErrorFixingAndTimeoutPipeline):
    """상위 ErrorFixingAndTimeoutPipeline 대비 두 가지가 다르다.

    [수정 2] num_fix_attempts 는 '실제 에러 수정 LLM 호출 횟수'와 정확히 같다.
             (원본은 `if count > num_attempts: break` 라서 2를 주면 3회 돌았다.)
    [수정 5] 타임아웃 시 SaferMultiLineStatementExecutorListPassing(멀티프로세싱)으로
             갈아끼우지 않고, 같은 스레드 실행기의 timeout 만 늘려 재실행한다.
    """

    def __init__(self, main_pipeline, error_fix_pipeline,
                 max_timeout: int = 300, num_fix_attempts: int = 2):
        super().__init__(main_pipeline, error_fix_pipeline,
                         max_timeout=max_timeout, num_attempts=num_fix_attempts)
        self.num_fix_attempts = num_fix_attempts

    @staticmethod
    def _bad(x) -> bool:
        s = str(x)
        return s.startswith("__CODE_ERROR__") or s.startswith("__TIMEOUT__")

    def run_one(self, inp):
        row = inp
        prompt, raw, post, out, itok, otok = self.main_pipeline.run_one(row)
        prompts, raws, posts = [prompt], [raw], [post]
        n_calls = 1

        if str(out).startswith("__TIMEOUT__"):
            prev = self.main_pipeline.executor.timeout
            self.main_pipeline.executor.timeout = self.max_timeout
            try:
                p2, r2, s2, o2, i2, t2 = self.main_pipeline.run_one(row)
            finally:
                self.main_pipeline.executor.timeout = prev
            n_calls += 1
            itok += i2
            otok += t2
            tag = "TIMEOUT FIXED" if not str(o2).startswith("__TIMEOUT__") else "TIMEOUT NOT FIXED"
            prompts += [tag, str(p2)]
            raws += [tag, str(r2)]
            posts += [tag, str(s2)]
            if tag == "TIMEOUT FIXED":
                out, post = o2, s2

        n_fix = 0
        while self._bad(out) and n_fix < self.num_fix_attempts:
            pf, rf, sf, of, i3, t3 = self.error_fix_pipeline.run_one((row, post, out))
            n_fix += 1
            n_calls += 1
            itok += i3
            otok += t3
            fixed = not self._bad(of)
            tag = "ERROR FIXED" if fixed else "ERROR NOT FIXED"
            prompts += [tag, str(pf)]
            raws += [tag, str(rf)]
            posts += [tag, str(sf)]
            out, post = of, sf
            if fixed:
                break

        self.last_trace = {"n_llm_calls": n_calls, "n_fix_attempts": n_fix,
                           "final_error": self._bad(out)}
        return prompts, raws, posts, out, itok, otok

    def run_one_traced(self, row) -> dict:
        """실험 로깅용. err_pre / pre_unique 집계에 필요한 항목을 한 번에 돌려준다."""
        prompts, raws, posts, out, itok, otok = self.run_one(row)
        return {"output": out, "code": posts[-1], "raw": raws[-1],
                "input_tokens": itok, "output_tokens": otok, **self.last_trace}

    def __str__(self):
        return (f"SafeErrorFixingPipeline(num_fix_attempts={self.num_fix_attempts}, "
                f"max_timeout={self.max_timeout})\n\t{self.main_pipeline}\n\t{self.error_fix_pipeline}")


# ======================================================================
# 5. 조립
# ======================================================================
def assert_local_table(name: str, loader=None) -> pd.DataFrame:
    """[수정 6] generic_load_table 은 bare except 로 로컬 실패를 삼키고 조용히
    HuggingFace 로 폴백한다. CardBase 는 거기에 없으므로 미리 확인한다."""
    path = os.path.join("competition", name, "all.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{os.path.abspath(path)} 가 없습니다. 노트북 CWD 가 저장소 루트인지, "
            f"parquet 을 만들어 두었는지 확인하세요 (없으면 HuggingFace 로 폴백합니다)."
        )
    return (loader or utils.generic_load_table)(name)


def build_pipe_nosr(model="gpt-4o-mini", temperature=0.0, max_gen_len=300,
                    fix_max_gen_len=1000, num_fix_attempts=2,
                    exec_timeout=60, max_timeout=300,
                    lite=False, debug=False, client=None):
    load_dotenv()
    loader = utils.generic_load_sample if lite else utils.generic_load_table

    _, exemplars = utils.annotation_reader(ANNOTATIONS_FILE)
    shots = [exemplars[i] for i in (x[0] for x in EXEMPLAR_INDICES)]

    # --- 메인 프롬프트: 예시 9개도 전부 SR 없이 렌더링된다 ---
    zs = SchemaOnlyZeroShot(loader, lite=lite)
    exemplar_builder = prompt_generators.ExemplarBuilder(loader, zs)
    fewshot = prompt_generators.FewShotChainOfThoughtBuilderWithTypesRowsAndPredictingResultingTypesVol2(
        loader, zs, exemplar_builder, shots=shots)
    pg = prompt_generators.ClaudeMessageEmbeddingPromptGenerator(loader, fewshot)

    post_main = postprocessors.TillReturnLinePostProcessorMultipleIndents(
        loader, prefix=4,
        first_prefix="    # The columns used to answer the question: ")

    main_pipe = pipelines.Pipeline(
        pg,
        OpenAIAnswerer(client, model=model, temperature=temperature,
                       max_gen_len=max_gen_len),
        post_main,
        InlineStatementExecutor(loader, timeout=exec_timeout),
        debug=debug,
    )

    # --- 에러 수정: 프리필이 df.columns=[...] 로 끝나므로 CUAT 라벨을 붙이면 안 된다 ---
    # [수정 3] first_prefix 를 공백 4칸으로. ''로 두면 첫 줄 들여쓰기가 사라져 IndentationError.
    post_fix = postprocessors.TillReturnLinePostProcessorMultipleIndents(
        loader, prefix=4, first_prefix="    ")

    # [수정 7] ErrorFixingGeneratorClaudeVol2 는 num_rows 를 쓰지 않는다.
    #          SR 제거는 zero_shot_generator 를 바꾸는 것만으로 완결된다.
    fix_pipe = pipelines.ErrorFixPipeline(
        prompt_generators.ErrorFixingGeneratorClaudeVol2(
            loader, SchemaOnlyZeroShot(loader, lite=lite)),
        OpenAIAnswerer(client, model=model, temperature=temperature,
                       max_gen_len=fix_max_gen_len),
        post_fix,
        InlineStatementExecutor(loader, timeout=exec_timeout),
        debug=debug,
    )

    return SafeErrorFixingPipeline(main_pipe, fix_pipe,
                                   max_timeout=max_timeout,
                                   num_fix_attempts=num_fix_attempts)


def assert_no_sample_rows(pipe, row) -> str:
    """FewShot 최종 프롬프트(예시 9개 포함)에 SR 이 없는지 확인."""
    p = pipe.main_pipeline.prompt_generator.prompt_generator(row)
    assert "rows from the dataframe" not in p, "SR 이 남아 있습니다"
    n = p.count("The columns used to answer the question")
    assert n == len(pipe.main_pipeline.prompt_generator.prompt_generator.shots) + 1, \
        f"CUAT 라벨 개수 이상: {n}"
    return p