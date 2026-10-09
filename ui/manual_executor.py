"""Local manual Python execution in a separate, time-limited process.

This is process isolation for recovery, not a security sandbox for untrusted code.
"""
import ast
import contextlib
import io
import pickle
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


def execute(code: str, table: str, timeout: float = 30) -> dict:
    if not code.strip():
        return {"ok": False, "message": "실행할 코드를 입력해주세요."}
    try:
        with tempfile.TemporaryDirectory(prefix="dp-manual-") as folder:
            root = Path(folder)
            (root / "code.txt").write_text(code, encoding="utf-8")
            subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), str(root), table],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=timeout, check=False,
            )
            output = root / "result.pkl"
            if not output.exists():
                return {"ok": False, "message": "실행을 완료하지 못했습니다. 코드를 수정한 뒤 다시 실행해주세요."}
            with output.open("rb") as stream:
                return pickle.load(stream)
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "실행 시간이 초과되었습니다. 작업 범위를 줄여 다시 실행해주세요."}
    except Exception:
        return {"ok": False, "message": "데이터를 불러오거나 실행하지 못했습니다. 다시 시도해주세요."}


def _worker(folder: str, table: str) -> None:
    import numpy as np
    import pandas as pd
    root = Path(folder)
    try:
        body = textwrap.dedent((root / "code.txt").read_text(encoding="utf-8")).strip()
        tree = ast.parse("def answer(df):\n" + textwrap.indent(body, "    "))
        function = tree.body[0]
        # Notebook-style final expressions are returned automatically.
        if function.body and isinstance(function.body[-1], ast.Expr):
            function.body[-1] = ast.Return(value=function.body[-1].value)
        ast.fix_missing_locations(tree)
        namespace = {"pd": pd, "np": np, "ast": ast}
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            exec(compile(tree, "<manual>", "exec"), namespace)
            value = namespace["answer"](pd.read_parquet(table))
        if value is None and output.getvalue().strip():
            value = output.getvalue().strip()
        result = {"ok": True, "value": value, "message": "실행이 완료되었습니다."}
    except SyntaxError:
        result = {"ok": False, "message": "코드 문법이나 들여쓰기를 확인한 뒤 다시 실행해주세요."}
    except KeyError:
        result = {"ok": False, "message": "선택한 데이터셋의 컬럼명을 확인한 뒤 다시 실행해주세요."}
    except BaseException:
        result = {"ok": False, "message": "코드를 실행하지 못했습니다. 내용을 수정한 뒤 다시 실행해주세요."}
    try:
        payload = pickle.dumps(result)
    except Exception:
        payload = pickle.dumps({"ok": False, "message": "표시할 수 없는 결과입니다. 숫자·문자·표 형태로 반환해주세요."})
    (root / "result.pkl").write_bytes(payload)


if __name__ == "__main__":
    _worker(sys.argv[1], sys.argv[2])
