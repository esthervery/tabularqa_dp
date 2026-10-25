"""필드 힌트 — 화면에 올릴 카드 페이로드.

정본은 `ui/hints.json` 이다. 이 파일은 두 가지 일만 한다.

    load()            hints.json 을 읽어 {db: payload} 로 반환 (실패 시 빈 dict)
    rebuild(force)    parquet 을 다시 읽어 hints.json 을 재생성

왜 json 을 정본으로 두는가
    화면 렌더 경로에서 parquet 을 읽지 않기 위해서다. 카드 1장을 그리려고
    수만 행짜리 parquet 을 매 rerun 마다 여는 것은 낭비이고, Streamlit 은
    rerun 마다 스크립트를 처음부터 다시 실행한다.

값 노출 규칙 (프라이버시)
    범주형   → 값 종류(이름)만. 건수·비율은 수집만 하고 화면에 내보내지 않는다.
    수치형   → Q1·Q2·Q3 만. 최소·최대·평균·표준편차·분포 금지.
    측정 대상 → 힌트 밴드에 표시하지 않는다 (결과의 대상이므로).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ui.fields import SPECS, ENABLED

JSON_PATH = Path(__file__).resolve().parent / "hints.json"

_MAX_CAT_KINDS = 15   # 범주형 상한 — 넘으면 스펙 오분류
_MIN_FIL_KINDS = 5    # 수치형 하한 — 이보다 적으면 범주형이어야 한다


# ── 읽기 ────────────────────────────────────────────────

def load() -> dict:
    """{db_name: payload}. 파일이 없거나 깨졌으면 빈 dict (화면은 밴드를 생략)."""
    try:
        return json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def cards_of(db_name: str, bucket: str = "all") -> list[dict]:
    """카드 순서: 조건(cat) → 수치형(filter) → 이진(pattern)."""
    p = load().get(db_name) or {}
    cat = p.get("cat") or []
    fil = p.get("fil") or []
    pat = p.get("pat") or []
    if bucket == "cat":
        return cat
    if bucket == "fil":
        return fil
    if bucket == "pat":
        return pat

    out: list[dict] = []
    for f in cat:
        out.append({"col": f["col"], "label": f["label"], "kind": "categorical",
                    "n": f.get("kinds", 0),
                    "values": _values(db_name, f["col"], f.get("ordered", False))})
    for f in fil:
        out.append({"col": f["col"], "label": f["label"], "kind": "filter",
                    "unit": f.get("unit", ""), "n": f.get("kinds", 0),
                    "quartiles": f.get("q", [])})
    for f in pat:
        out.append({"col": f["col"], "label": f["label"], "kind": "pattern",
                    "n": f.get("kinds", 2),
                    "values": _values(db_name, f["col"], False)})
    return out


# ── 재생성 ──────────────────────────────────────────────

def _quartiles(s: pd.Series) -> list[float]:
    q = s.quantile([0.25, 0.5, 0.75])
    return [round(float(v), 2) for v in q]


def build(name: str, df: pd.DataFrame) -> dict:
    """스펙 1개 + 실제 parquet → 힌트 payload. 어긋나면 ValueError (fail-closed)."""
    spec = SPECS[name]
    cols = set(df.columns)
    need = ([spec["measure"]["col"]]
            + [c["col"] for c in spec["cat"]]
            + [c["col"] for c in spec["fil"]]
            + [spec["measure"]["col"]] * 0
            + [c["col"] for c in spec["pat"]])
    missing = [c for c in need if c not in cols]
    if missing:
        raise ValueError(f"{name}: parquet 에 없는 컬럼 {missing}")

    m = df[spec["measure"]["col"]]
    if not pd.api.types.is_numeric_dtype(m):
        raise ValueError(f"{name}.{spec['measure']['col']}: 측정 대상이 수치형이 아니다")

    cat, fil, pat = [], [], []
    for c in spec["cat"]:
        k = int(df[c["col"]].nunique(dropna=True))
        if k > _MAX_CAT_KINDS:
            raise ValueError(f"{name}.{c['col']}: 범주형인데 값이 {k}종 (>{_MAX_CAT_KINDS})")
        cat.append({**c, "kinds": k})
    for c in spec["fil"]:
        k = int(df[c["col"]].nunique(dropna=True))
        if k < _MIN_FIL_KINDS:
            raise ValueError(f"{name}.{c['col']}: 수치형인데 값이 {k}종 (<{_MIN_FIL_KINDS})")
        fil.append({**c, "kinds": k, "q": _quartiles(df[c["col"]].astype(float))})
    for c in spec["pat"]:
        k = int(df[c["col"]].nunique(dropna=True))
        if k != 2:
            raise ValueError(f"{name}.{c['col']}: 이진 결과인데 값이 {k}종")
        pat.append({**c, "kinds": k})

    return {
        "name": name,
        "title": spec["title"],
        "rows": int(len(df)),
        "cols_total": int(df.shape[1]),
        "measure": spec["measure"],
        "cat": cat, "fil": fil, "pat": pat,
        "counts": {
            "categorical": len(cat), "filter": len(fil), "pattern": len(pat),
            "exposed": len(cat) + len(fil) + len(pat),
        },
    }


def rebuild(write: bool = True) -> dict:
    """ENABLED 데이터셋 전체를 다시 계산. parquet 로더는 호출자가 준다."""
    from ui import catalog
    out = {}
    for name in ENABLED:
        out[name] = build(name, catalog.load_df(name))
    if write:
        JSON_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    return out


# ── 내부: 값 이름 (건수 제외) ───────────────────────────

def _values(db_name: str, col: str, ordered: bool) -> list[dict]:
    """범주형 값 이름만. 건수·비율은 담지 않는다.

    정렬: ordered=True 면 값 자체 순서(사전/수치), 아니면 알파벳.
    """
    from ui import catalog
    try:
        s = catalog.load_df(db_name)[col]
    except Exception:
        return []
    if ordered:
        try:
            keys = sorted(s.dropna().unique().tolist())
        except TypeError:
            keys = sorted(s.dropna().astype(str).unique().tolist())
    else:
        keys = sorted(s.dropna().astype(str).unique().tolist())
    return [{"t": _label(v), "w": 0} for v in keys]


def _label(v) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)
