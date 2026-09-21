"""KCI 시뮬레이터 (Privacy Policy 페이지 전용).

관리자가 리스크 레벨 버튼을 누르면 이 모듈이:
    1) 대상 DB 의 관심 컬럼(SIM_TARGET) 을 로드
    2) 민감도 Δ = (max - min) / n 계산
    3) k = total_eps / eps_per_query 라운드만큼 라플라스 노이즈 응답 생성
    4) 라운드별 누적 평균 · 95% 신뢰구간 계산 → 시각화 A 데이터
    5) 마지막 라운드에서 원본 CI ↔ 인접 DB CI(Δ만큼 이동) 겹침 계산 → 시각화 B 데이터
을 dataclass 로 반환한다.

정지 규칙 없음 — k 라운드를 반드시 다 실행.
캐시 없음 — st.cache_data 로만 세션 내 재계산 회피.

주요 API
    SIM_TARGET                          : {db_name: target_col} 매핑
    RISK_LEVELS                         : {1..5: total_eps} 매핑
    simulate(db_name, risk_level)       : SimResult 반환 (전체 결과)
    is_supported(db_name)               : SIM_TARGET 에 등록된 DB 인지
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats

from ui import catalog


# ── 상수 ────────────────────────────────────────────

# 리스크 레벨 → 총 ε 예산 매핑 (NIST SP 800-226 참고)
RISK_LEVELS: dict[int, float] = {
    1: 2.0,     # 가장 보수적 (프라이버시 강함, 정확도 낮음)
    2: 4.0,
    3: 6.0,
    4: 8.0,
    5: 10.0,    # 가장 적극적 (정확도 높음, 프라이버시 약함)
}

# 질의당 ε (고정)
EPS_PER_QUERY: float = 0.1

# 재현성을 위한 seed 고정
SEED: int = 2027

# 95% 신뢰구간
ALPHA: float = 0.05

# DB → 시뮬레이션 대상 컬럼 매핑.
# 명시한 값은 우선 사용한다. 등록되지 않은 DB는 아래 자동 선택 로직이
# 결측이 아닌 수치형 컬럼을 찾아 모든 카탈로그 데이터셋을 지원한다.
SIM_TARGET: dict[str, str] = {
    "000_CardBase": "Credit_Limit",
    "003_Love":     "What is your age? 👶🏻👵🏻",
    "047_Bank":     "credit_limit",
}


# ── 결과 dataclass ─────────────────────────────────

@dataclass
class SimResult:
    """simulate() 가 반환하는 값. 시각화 A/B 가 이 하나로 모두 그려진다."""
    # 메타
    db_name:      str
    target_col:   str
    risk_level:   int
    total_eps:    float
    eps_per_query: float
    k:            int              # 라운드 수 (= total_eps / eps_per_query)
    seed:         int
    n_rows:       int              # 대상 DB 의 행 수
    sensitivity:  float            # Δ = (max-min)/n
    true_mean:    float            # 참 평균 (초록 점선)

    # 시각화 A: 라운드별 궤적 (길이 k)
    ks:              np.ndarray   # [1, 2, ..., k]
    noisy_responses: np.ndarray   # 각 라운드의 노이지 응답 (회색 점)
    cum_means:       np.ndarray   # 누적 평균 (파란 선)
    ci_los:          np.ndarray   # CI 하한 (파란 밴드)
    ci_his:          np.ndarray   # CI 상한 (파란 밴드)

    # 시각화 B: 마지막 라운드 스냅샷
    stop_mean:    float
    stop_ci_lo:   float
    stop_ci_hi:   float
    adj_ci_lo:    float           # stop_ci_lo - Δ (인접 DB CI)
    adj_ci_hi:    float           # stop_ci_hi - Δ
    overlap_lo:   Optional[float] # 겹칠 때만 값
    overlap_hi:   Optional[float]
    overlap_ratio: float          # 0.0..1.0


# ── 등록 여부 확인 ────────────────────────────────

def is_supported(db_name: str) -> bool:
    """시뮬레이션에 사용할 수치형 컬럼이 있는지."""
    return target_of(db_name) is not None


def target_of(db_name: str) -> Optional[str]:
    """명시 매핑 또는 자동 선택한 시뮬레이션 대상 수치형 컬럼."""
    return SIM_TARGET.get(db_name) or _infer_numeric_target(db_name)


@st.cache_data(show_spinner=False)
def _infer_numeric_target(db_name: str) -> Optional[str]:
    """식별자·이진값보다 연속적인 수치형 컬럼을 우선 선택한다."""
    try:
        df = catalog.load_df(db_name)
    except (FileNotFoundError, OSError, ValueError):
        return None

    candidates: list[tuple[tuple[int, int, int, int], str]] = []
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_bool_dtype(df[col]):
            continue
        values = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        unique = len(np.unique(values))
        if len(values) < 2 or unique < 2:
            continue

        label = str(col).lower()
        is_identifier = (
            label in {"id", "wid"}
            or label.endswith(" id")
            or label.endswith("id")
            or any(token in label for token in ("serial", "invoice", "customer"))
        )
        # 연속형 > 다값 범주형 > 이진값, 식별자 컬럼은 가장 나중에 선택.
        score = (
            int(not is_identifier),
            int(unique > 2),
            min(unique, 10_000),
            len(values),
        )
        candidates.append((score, str(col)))

    return max(candidates, default=(None, None))[1]


# ── 코어 시뮬레이션 ──────────────────────────────

def _laplace_stream(true_mean: float, delta: float,
                    eps_per_query: float, k: int,
                    seed: int) -> np.ndarray:
    """라플라스 노이즈를 붙인 k 개의 응답 벡터를 생성.

    라플라스 스케일 b = Δ / ε. 각 질의는 독립적으로 ε 을 소모하며,
    순차 구성 정리에 따라 총 예산은 k · ε 이 된다.
    """
    b = delta / eps_per_query
    rng = np.random.default_rng(seed)
    return true_mean + rng.laplace(loc=0.0, scale=b, size=k)


def _running_ci(responses: np.ndarray, alpha: float = ALPHA) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """응답 스트림에서 매 시점의 누적 평균 · CI 하한 · CI 상한을 계산.

    Returns
        cum_means, ci_los, ci_his — 각각 길이 k 의 배열.
        k=1 일 때는 표본분산이 정의되지 않아 CI 를 NaN 처리.
    """
    k = len(responses)
    cum_means = np.empty(k)
    ci_los    = np.empty(k)
    ci_his    = np.empty(k)

    s1 = 0.0    # Σx
    s2 = 0.0    # Σx²

    for i in range(k):
        v = float(responses[i])
        s1 += v
        s2 += v * v
        n = i + 1
        mean = s1 / n
        cum_means[i] = mean

        if n < 2:
            ci_los[i] = np.nan
            ci_his[i] = np.nan
            continue

        # 표본분산 (n-1 로 나눔). 수치 오차로 음수 나오는 것 방지.
        var = max((s2 - n * mean * mean) / (n - 1), 0.0)
        se  = np.sqrt(var) / np.sqrt(n)
        # t 분포 임계값
        moe = stats.t.ppf(1 - alpha / 2, df=n - 1) * se
        ci_los[i] = mean - moe
        ci_his[i] = mean + moe

    return cum_means, ci_los, ci_his


def _overlap(a_lo: float, a_hi: float,
             b_lo: float, b_hi: float) -> tuple[Optional[float], Optional[float], float]:
    """두 구간 [a_lo,a_hi], [b_lo,b_hi] 의 교집합과 겹침 비율.

    overlap_ratio = |교집합| / |구간 A|
    (인접 DB 를 관측했을 때 원본으로부터 얼마나 구별되기 어려운지)
    """
    lo = max(a_lo, b_lo)
    hi = min(a_hi, b_hi)
    if lo >= hi:
        return None, None, 0.0
    width_a = a_hi - a_lo
    if width_a <= 0:
        return lo, hi, 0.0
    return lo, hi, (hi - lo) / width_a


@st.cache_data(show_spinner="시뮬레이션 실행 중…")
def simulate(db_name: str, risk_level: int) -> SimResult:
    """리스크 레벨 하나에 대한 완전한 시뮬레이션 결과를 반환.

    캐시 키: (db_name, risk_level).
    seed 와 컬럼 매핑이 모듈 상수라 이 두 값만으로 유일하게 결정됨.
    """
    if not is_supported(db_name):
        raise ValueError(
            f"'{db_name}' 는 시뮬레이션 대상 컬럼이 등록되어 있지 않습니다. "
            f"ui/dp_sim.py 의 SIM_TARGET 에 추가하세요."
        )
    if risk_level not in RISK_LEVELS:
        raise ValueError(f"risk_level 은 1..5 만 지원합니다: {risk_level}")

    target_col = target_of(db_name)
    if target_col is None:
        raise ValueError(f"'{db_name}' 에 사용할 수치형 컬럼이 없습니다.")
    total_eps  = RISK_LEVELS[risk_level]
    k          = int(round(total_eps / EPS_PER_QUERY))

    # 데이터 로드 + 참 통계량
    df = catalog.load_df(db_name)
    x = pd.to_numeric(df[target_col], errors="coerce").to_numpy(dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        raise ValueError(f"'{db_name}/{target_col}' 에 유효한 수치값이 부족합니다.")
    n  = len(x)
    true_mean   = float(x.mean())
    sensitivity = float((x.max() - x.min()) / n)

    # 라운드별 노이지 응답 → 누적 평균/CI
    responses = _laplace_stream(true_mean, sensitivity, EPS_PER_QUERY, k, SEED)
    cum_means, ci_los, ci_his = _running_ci(responses, alpha=ALPHA)

    # 마지막 라운드 스냅샷 = 시각화 B
    stop_mean  = float(cum_means[-1])
    stop_ci_lo = float(ci_los[-1])
    stop_ci_hi = float(ci_his[-1])
    # 인접 DB: 원본 CI 를 -Δ 만큼 이동 (개인 한 명 포함 여부로 평균이 최대 Δ 변함)
    adj_ci_lo  = stop_ci_lo - sensitivity
    adj_ci_hi  = stop_ci_hi - sensitivity
    ov_lo, ov_hi, ratio = _overlap(stop_ci_lo, stop_ci_hi, adj_ci_lo, adj_ci_hi)

    return SimResult(
        db_name=db_name,
        target_col=target_col,
        risk_level=risk_level,
        total_eps=total_eps,
        eps_per_query=EPS_PER_QUERY,
        k=k,
        seed=SEED,
        n_rows=n,
        sensitivity=sensitivity,
        true_mean=true_mean,
        ks=np.arange(1, k + 1),
        noisy_responses=responses,
        cum_means=cum_means,
        ci_los=ci_los,
        ci_his=ci_his,
        stop_mean=stop_mean,
        stop_ci_lo=stop_ci_lo,
        stop_ci_hi=stop_ci_hi,
        adj_ci_lo=adj_ci_lo,
        adj_ci_hi=adj_ci_hi,
        overlap_lo=ov_lo,
        overlap_hi=ov_hi,
        overlap_ratio=ratio,
    )
