"""DP 노이즈 — 질의코드 → 민감도 Δ → 라플라스 노이즈.

흐름
    guardrail.check() 가 '허용 + 질의코드' 를 돌려준다
    → 에이전트가 정답(숫자 하나)을 계산한다
    → privatize(정답, 질의코드, 데이터셋, ε) 가 Δ 를 골라 Laplace(0, Δ/ε) 를 더한다.

민감도 파일
    루트의 sensitivity.json (sensitivity.ipynb 셀 7 이 생성).
    datasets[<db>]["delta"] = {"mean", "median", "max", "min"} — 국소 민감도(한 행 교체).
    범위 정보가 들어 있으므로 커밋하지 않는다(.gitignore).

원칙
    fail-closed — 파일·데이터셋·질의코드·정답 중 하나라도 이상하면 NoiseError.
    노이즈 없는 정답이 밖으로 나가는 경로를 만들지 않는다.
"""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import numpy as np

SENS_FILE = Path(os.getenv("DP_SENS_FILE")
                 or Path(__file__).resolve().parent.parent / "sensitivity.json")

# Δ 하한 = FLOOR_RATIO × (그 데이터셋의 평균 Δ).
# 같은 값이 많은 컬럼에서 국소 Δ 가 0 이 되어 노이즈가 사라지는 것을 막는다. 0 이면 하한 없음.
FLOOR_RATIO = 1.0

# 질의코드 → ((통계량, 계수), ...).   Δ = Σ 계수 × max(D[통계량], 하한)
# guardrail.QUERY_CODES 와 같은 목록이어야 한다.
TERMS: dict[str, tuple[tuple[str, int], ...]] = {
    "MEAN":        (("mean", 1),),
    "MEDIAN":      (("median", 1),),
    "MAX":         (("max", 1),),
    "MIN":         (("min", 1),),
    "DIFF_MEAN":   (("mean", 2),),
    "DIFF_MEDIAN": (("median", 2),),
    "DIFF_MAX":    (("max", 2),),
    "DIFF_MIN":    (("min", 2),),
    "MAX_MIN":     (("max", 1), ("min", 1)),
    "MEAN_MEDIAN": (("mean", 1), ("median", 1)),
}

# seed 를 고정하지 않는다 — 고정하면 노이즈 순서를 재현해 빼낼 수 있다.
_rng = np.random.default_rng()
_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_cache: dict = {"mtime": None, "data": {}}


class NoiseError(RuntimeError):
    """노이즈를 붙일 수 없음 — 호출 측은 응답을 내보내지 말고 차단해야 한다."""


def _datasets() -> dict:
    """sensitivity.json 의 datasets. 파일이 바뀌면(수정 시각) 다시 읽는다."""
    try:
        mtime = SENS_FILE.stat().st_mtime
    except FileNotFoundError:
        raise NoiseError(f"민감도 파일이 없습니다 ({SENS_FILE.name})") from None
    if _cache["mtime"] != mtime:
        try:
            data = json.loads(SENS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise NoiseError(f"민감도 파일을 읽지 못했습니다 ({type(e).__name__})") from None
        _cache.update(mtime=mtime, data=data.get("datasets") or {})
    return _cache["data"]


def delta_of(code: str, db_name: str) -> float:
    """질의코드 × 데이터셋 → 최종 Δ (하한 적용 후)."""
    terms = TERMS.get(code)
    if not terms:
        raise NoiseError(f"알 수 없는 질의코드입니다 ({code or '없음'})")
    ent = _datasets().get(db_name)
    if not ent:
        raise NoiseError(f"{db_name} 의 민감도가 정의되어 있지 않습니다")
    d = ent.get("delta") or {}
    try:
        floor = FLOOR_RATIO * float(d["mean"])
        total = sum(c * max(float(d[s]), floor) for s, c in terms)
    except (KeyError, TypeError, ValueError) as e:
        raise NoiseError(f"{db_name} 민감도 항목이 올바르지 않습니다 ({e})") from None
    if not math.isfinite(total) or total <= 0:
        raise NoiseError(f"{db_name} · {code} 의 민감도가 0 이하입니다")
    return total


def _to_number(ans) -> float:
    """에이전트 정답 → float. 숫자 하나가 아니면 NoiseError."""
    if isinstance(ans, (bool, np.bool_)):
        raise NoiseError("정답이 참/거짓 값입니다")
    if isinstance(ans, str):
        nums = _NUM.findall(ans.replace(",", ""))
        if len(nums) != 1:
            raise NoiseError("정답이 숫자 하나가 아닙니다")
        x = float(nums[0])
    else:
        try:
            arr = np.asarray(ans, dtype=float).ravel()
        except (TypeError, ValueError):
            raise NoiseError("정답을 숫자로 바꿀 수 없습니다") from None
        if arr.size != 1:
            raise NoiseError("정답이 숫자 하나가 아닙니다")
        x = float(arr[0])
    if not math.isfinite(x):
        raise NoiseError("정답이 유한한 숫자가 아닙니다")
    return x


def privatize(answer, code: str, db_name: str, eps: float) -> dict:
    """정답 + Laplace(0, Δ/ε). 반환값에 노이즈 없는 정답은 넣지 않는다."""
    if not eps or eps <= 0:
        raise NoiseError("ε 가 0 이하입니다")
    true = _to_number(answer)
    delta = delta_of(code, db_name)
    scale = delta / eps
    return {"value": true + float(_rng.laplace(0.0, scale)),
            "delta": delta, "scale": scale, "code": code}