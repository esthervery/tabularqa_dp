"""로컬 데이터셋 카탈로그.

`competition/` 하위 폴더를 스캔해 (all.parquet + info.yml) 있는
디렉터리를 하나의 "DB" 로 취급한다.

주요 API
    catalog()      DataFrame(name, title, domain, source, n_rows, n_cols, path)
    names(domain?) 도메인 필터를 걸어 이름 목록
    domains()      ['전체', ...도메인 목록]
    meta(name)     특정 DB 의 메타 dict
    table_path(name)  parquet 경로
    load_df(name)     parquet 을 DataFrame 으로 (캐시됨)
    schema_of(name)   parquet 메타에서 컬럼/타입만 빠르게 추출
"""
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
SEARCH_DIRS = [ROOT / "competition"]


def _read_info(d: Path) -> dict:
    """info.yml 이 있으면 파싱해서 dict 로. 없으면 빈 dict."""
    f = d / "info.yml"
    if not f.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


CATALOG_COLUMNS = [
    "name",
    "title",
    "domain",
    "source",
    "n_rows",
    "n_cols",
    "path",
]


@st.cache_data(show_spinner=False)
def catalog() -> pd.DataFrame:
    """all.parquet 을 가진 하위 디렉터리를 수집. 앞쪽 SEARCH_DIRS 우선."""
    rows, seen = [], set()
    for base in SEARCH_DIRS:
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            p = d / "all.parquet"
            if not (d.is_dir() and p.exists()) or d.name in seen:
                continue
            seen.add(d.name)
            info = _read_info(d)
            try:
                md = pq.ParquetFile(p).metadata
                n_rows, n_cols = md.num_rows, md.num_columns
            except Exception:
                n_rows, n_cols = -1, -1
            rows.append({
                "name":   d.name,
                "title":  str(info.get("Title") or d.name),
                "domain": str(info.get("domain") or "-"),
                "source": str(info.get("Source") or ""),
                "n_rows": n_rows,
                "n_cols": n_cols,
                "path":   str(p),
            })

    df = pd.DataFrame(rows, columns=CATALOG_COLUMNS)
    return df


def names(domain: str | None = None) -> list[str]:
    c = catalog()
    if c.empty or "domain" not in c.columns:
        return []
    if domain and domain != "전체":
        c = c[c["domain"] == domain]
    return c["name"].tolist()


def domains() -> list[str]:
    c = catalog()
    if c.empty or "domain" not in c.columns:
        return ["전체"]
    return ["전체"] + sorted(c["domain"].dropna().astype(str).unique().tolist())


def meta(name: str) -> dict:
    c = catalog()
    if c.empty or "name" not in c.columns:
        return {}
    hit = c[c["name"] == name]
    return {} if hit.empty else hit.iloc[0].to_dict()


def table_path(name: str) -> str:
    m = meta(name)
    if not m:
        raise FileNotFoundError(f"로컬 카탈로그에 '{name}' 없음")
    return m["path"]


@st.cache_data(show_spinner="테이블 로드 중…")
def load_df(name: str) -> pd.DataFrame:
    return pd.read_parquet(table_path(name))


@st.cache_data(show_spinner=False)
def schema_of(name: str) -> pd.DataFrame:
    """parquet 메타데이터만으로 컬럼/타입 표를 만든다 (전체 로드 안 함)."""
    pf = pq.ParquetFile(table_path(name))
    arrow = pf.schema_arrow
    return pd.DataFrame({
        "column": arrow.names,
        "dtype":  [str(t) for t in arrow.types],
    })
