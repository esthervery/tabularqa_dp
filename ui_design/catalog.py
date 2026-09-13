"""로컬 data/ 디렉터리를 스캔해 DB 카탈로그를 만든다."""
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
SEARCH_DIRS = [ROOT / "competition"]


def _read_info(d: Path) -> dict:
    f = d / "info.yml"
    if not f.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


@st.cache_data(show_spinner=False)
def catalog() -> pd.DataFrame:
    """all.parquet 을 가진 디렉터리만 수집. name 기준 중복은 앞쪽 dir 우선."""
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
    return pd.DataFrame(rows)


def names(domain: str | None = None) -> list[str]:
    c = catalog()
    if domain and domain != "전체":
        c = c[c["domain"] == domain]
    return c["name"].tolist()


def domains() -> list[str]:
    return ["전체"] + sorted(catalog()["domain"].unique().tolist())


def meta(name: str) -> dict:
    c = catalog()
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
    """전체 로드 없이 parquet 메타데이터만으로 스키마를 만든다.

    non-null 은 row group 통계의 null_count 합으로 구하고,
    통계가 없으면 -1 로 둔다(80종 중 일부는 통계가 비어 있을 수 있음).
    """
    pf = pq.ParquetFile(table_path(name))
    md, arrow = pf.metadata, pf.schema_arrow
    nulls = {c: 0 for c in arrow.names}
    ok = True
    for g in range(md.num_row_groups):
        rg = md.row_group(g)
        for i in range(rg.num_columns):
            col = rg.column(i)
            leaf = col.path_in_schema.split(".")[0]
            if col.statistics is None or col.statistics.null_count is None:
                ok = False
            elif leaf in nulls:
                nulls[leaf] += col.statistics.null_count
    return pd.DataFrame({
        "column":   arrow.names,
        "dtype":    [str(t) for t in arrow.types]})