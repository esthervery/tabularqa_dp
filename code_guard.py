"""LLM 생성 코드 실행 전 검사기 (code guard).

dp_agent_wrap.InlineStatementExecutor 가 exec() 직전에 호출한다.
  1) 정규식 1차 필터 — 주석을 뺀 코드에서 명백한 위험 패턴을 거른다.
  2) AST 검사       — 문장 종류 · 이름 · 속성 · 문자열 조립을 검사한다.
  3) 제한 builtins  — 실행 네임스페이스에는 허용 목록의 내장 함수만 넣는다.
"""
from __future__ import annotations

import ast
import builtins as _builtins
import re

MAX_CODE_CHARS = 4000
MAX_NODES = 2000
MAX_INT = 10 ** 9
MAX_POW = 64


class CodeGuardError(ValueError):
    """검사 불통과. 메시지는 오류 수정 LLM 에도 전달되므로 데이터 값을 담지 않는다."""


# ── 1) 정규식 (ast.unparse 결과에 적용 → 주석은 이미 빠져 있음) ──
_DENY_RE = [
    (re.compile(r"__"), "밑줄 두 개(__) 사용"),
    (re.compile(r"\bimport\b"), "import 사용"),
    (re.compile(r"\b(?:os|sys|subprocess|socket|shutil|pathlib|importlib|builtins)\s*\."),
     "시스템 모듈 접근"),
    (re.compile(r"\b(?:eval|exec|compile|open|getattr)\s*\("), "금지 함수 호출"),
]

# ── 2) AST 규칙 ──
_DENY_NODES: dict[type, str] = {
    ast.Import: "import 문", ast.ImportFrom: "import 문",
    ast.Global: "global 문", ast.Nonlocal: "nonlocal 문",
    ast.ClassDef: "class 정의", ast.AsyncFunctionDef: "async 함수",
    ast.Await: "await", ast.AsyncFor: "async for", ast.AsyncWith: "async with",
    ast.With: "with 문", ast.While: "while 반복문", ast.Raise: "raise 문",
    ast.Yield: "yield", ast.YieldFrom: "yield from",
    ast.JoinedStr: "f-string",
}

_DENY_NAMES = {
    "eval", "exec", "compile", "open", "input", "breakpoint", "help",
    "getattr", "setattr", "delattr", "hasattr", "globals", "locals", "vars", "dir",
    "memoryview", "bytearray", "bytes", "chr", "ord", "exit", "quit",
    "object", "type", "super", "classmethod", "staticmethod", "property", "print",
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "importlib", "builtins",
}

_DENY_ATTRS = {
    # 파일 쓰기 / 읽기 (read_* 는 접두어로 따로 차단)
    "to_csv", "to_excel", "to_parquet", "to_pickle", "to_json", "to_sql", "to_hdf",
    "to_feather", "to_html", "to_latex", "to_markdown", "to_clipboard", "to_stata",
    "to_orc", "to_xml", "to_gbq", "tofile", "fromfile", "load", "save", "savez",
    "savez_compressed", "savetxt", "loadtxt", "genfromtxt", "memmap", "DataSource",
    "ExcelWriter", "HDFStore", "savefig",
    # 문자열 코드 실행
    "eval", "exec",
    # 모듈 탈출 경로
    "os", "sys", "subprocess", "shutil", "socket", "builtins", "importlib", "pathlib",
    "io", "pickle", "ctypes", "ctypeslib", "compat", "testing", "f2py", "distutils",
    "lib", "util", "system", "popen", "modules",
    # 프레임 / 코드 객체
    "f_globals", "f_locals", "f_back", "f_builtins", "gi_frame", "gi_code",
    "cr_frame", "ag_frame", "tb_frame", "tb_next", "co_code",
}
_DENY_ATTR_PREFIX = ("_", "read_")

# agg/apply/transform 에 문자열로 넘길 수 있는 집계 이름 (문자열 → 메서드 호출 우회 차단)
_FUNC_METHODS = {"agg", "aggregate", "apply", "transform"}
_AGG_NAMES = {
    "sum", "mean", "median", "min", "max", "count", "std", "var", "nunique", "size",
    "first", "last", "prod", "idxmax", "idxmin", "any", "all", "quantile", "mode",
    "cumsum", "cummax", "cummin", "sem", "skew",
}

# ── 3) 실행 시 허용 builtins ──
_SAFE_BUILTIN_NAMES = (
    "abs all any bool dict divmod enumerate filter float format frozenset int "
    "isinstance iter len list map max min next range repr reversed round set slice "
    "sorted str sum tuple zip "
    "Exception ValueError TypeError KeyError IndexError ZeroDivisionError "
    "AttributeError StopIteration"
).split()
SAFE_BUILTINS = {n: getattr(_builtins, n) for n in _SAFE_BUILTIN_NAMES}


def namespace(**mods) -> dict:
    """exec 용 전역 네임스페이스 — builtins 는 허용 목록만."""
    ns = {"__builtins__": dict(SAFE_BUILTINS)}
    ns.update(mods)
    return ns


# ── 헬퍼 ──
def _is_str(node) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _is_small_num(node) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        node = node.operand
    return (isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
            and abs(node.value) <= MAX_POW)


def _check_func_spec(node) -> None:
    """agg/apply/transform 의 함수 지정: 집계 이름 문자열 · lambda · 허용 builtin · 속성만."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str) and node.value not in _AGG_NAMES:
            raise CodeGuardError(f"허용되지 않은 집계 이름: {node.value!r}")
        return
    if isinstance(node, (ast.Lambda, ast.Attribute)):
        return
    if isinstance(node, ast.Name):
        if node.id not in SAFE_BUILTINS:
            raise CodeGuardError("집계 함수로 변수를 넘길 수 없습니다")
        return
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for e in node.elts:
            _check_func_spec(e)
        return
    if isinstance(node, ast.Dict):
        for v in node.values:
            _check_func_spec(v)
        return
    raise CodeGuardError("집계 함수는 이름(문자열) · lambda · 함수로만 지정할 수 있습니다")


def _check_call(node: ast.Call) -> None:
    f = node.func
    if not isinstance(f, ast.Attribute):
        return
    if f.attr == "query":
        if not node.args or not _is_str(node.args[0]):
            raise CodeGuardError("query() 조건은 문자열 상수로만 쓸 수 있습니다")
    if f.attr in _FUNC_METHODS:
        if node.args:
            _check_func_spec(node.args[0])
        for kw in node.keywords:
            if kw.arg is None:
                raise CodeGuardError("집계 함수에 ** 인자를 쓸 수 없습니다")
            if kw.arg == "func":
                _check_func_spec(kw.value)
            elif (f.attr in ("agg", "aggregate") and isinstance(kw.value, ast.Tuple)
                  and len(kw.value.elts) == 2):            # named aggregation
                _check_func_spec(kw.value.elts[1])


# ── 공개 API ──
def check(code: str) -> None:
    """통과하면 None, 불통과면 CodeGuardError. 문법 오류는 SyntaxError 그대로."""
    if len(code) > MAX_CODE_CHARS:
        raise CodeGuardError(f"코드가 너무 깁니다({len(code)}자)")
    tree = ast.parse(code)
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise CodeGuardError("코드가 너무 복잡합니다")

    body = tree.body
    if (len(body) != 1 or not isinstance(body[0], ast.FunctionDef)
            or body[0].name != "answer"):
        raise CodeGuardError("최상위에는 answer 함수만 둘 수 있습니다")
    top = body[0]

    flat = ast.unparse(tree)
    for rx, why in _DENY_RE:
        if rx.search(flat):
            raise CodeGuardError(why)

    for node in nodes:
        why = _DENY_NODES.get(type(node))
        if why:
            raise CodeGuardError(f"허용되지 않은 문법: {why}")
        if isinstance(node, ast.FunctionDef) and node is not top:
            raise CodeGuardError("함수 안에 함수를 정의할 수 없습니다(lambda 는 가능)")
        if isinstance(node, ast.Name) and (node.id.startswith("_") or node.id in _DENY_NAMES):
            raise CodeGuardError(f"허용되지 않은 이름: {node.id}")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith(_DENY_ATTR_PREFIX) or node.attr in _DENY_ATTRS:
                raise CodeGuardError(f"허용되지 않은 속성: .{node.attr}")
            if _is_str(node.value):
                raise CodeGuardError("문자열 메서드로 문자열을 조립할 수 없습니다")
        if isinstance(node, ast.Constant):
            v = node.value
            if isinstance(v, str) and ("__" in v or v in _DENY_ATTRS or v.startswith("read_")):
                raise CodeGuardError("허용되지 않은 문자열 상수")
            if isinstance(v, bytes):
                raise CodeGuardError("bytes 상수는 허용되지 않습니다")
            if isinstance(v, int) and not isinstance(v, bool) and abs(v) > MAX_INT:
                raise CodeGuardError("너무 큰 정수 상수")
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Pow) and not _is_small_num(node.right):
                raise CodeGuardError(f"거듭제곱 지수는 {MAX_POW} 이하의 숫자 상수만 가능합니다")
            if (isinstance(node.op, (ast.Add, ast.Mod, ast.Mult))
                    and (_is_str(node.left) or _is_str(node.right))):
                raise CodeGuardError("문자열 조립(+, %, *)은 허용되지 않습니다")
        if isinstance(node, ast.Call):
            _check_call(node)