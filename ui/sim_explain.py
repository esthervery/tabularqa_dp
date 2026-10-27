"""프라이버시 분석 — 시뮬레이션 결과 LLM 해설.

넘기는 정보
    · Utility 1~5 각각의 질의 횟수 · 최종 95% 신뢰구간 폭 · 평균 대비 %
    · 선택한 Utility 의 시뮬레이션 결과 (추정 평균 · 실제 평균 · 신뢰구간 · 오차)
    · Utility 1 / 5 대비 배율 (LLM 이 직접 계산하지 않도록 미리 계산)

해설은 별도 스레드에서 만든다 → 애니메이션 재생과 동시에 진행.
같은 입력이면 프로세스 캐시를 쓴다 (seed 고정이라 같은 조합 = 같은 숫자).
"""
from __future__ import annotations

import json
import threading
from concurrent.futures import Future, ThreadPoolExecutor

from ui import dp_sim

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT = 20.0
LEVELS = [1, 2, 3, 4, 5]

_CACHE: dict[str, str] = {}
_LOCK = threading.Lock()
_POOL = ThreadPoolExecutor(max_workers=2)


def _r(v) -> float | None:
    try:
        return float(f"{float(v):.4g}")
    except Exception:
        return None


def _pct(part: float, whole: float) -> float | None:
    return _r(part / abs(whole) * 100) if whole else None


# ── 입력 정리 ─────────────────────────────────────────────
def build_payload(spec: dict, tr, sel: int) -> dict:
    m = spec["measure"]
    true = float(tr.true_mean)

    widths = {r: float(tr.final(r)[3]) for r in LEVELS}
    levels = [{
        "utility": r,
        "queries": int(tr.k_of(r)),
        "ci_width": _r(widths[r]),
        "ci_width_pct_of_mean": _pct(widths[r], true),
    } for r in LEVELS]

    k = int(tr.k_of(sel))
    i = k - 1
    est, lo, hi = float(tr.cum_means[i]), float(tr.ci_los[i]), float(tr.ci_his[i])
    w = hi - lo

    return {
        "dataset": spec.get("title", ""),
        "measure": m["label"],
        "unit": m.get("unit") or "",
        "query": f"{m['label']}의 평균 (조건 없음) 을 반복 질의",
        "levels": levels,
        "selected": {
            "utility": sel,
            "queries": k,
            "estimated_mean": _r(est),
            "true_mean": _r(true),
            "ci_95": [_r(lo), _r(hi)],
            "ci_width": _r(w),
            "ci_width_pct_of_mean": _pct(w, true),
            "error_pct": _pct(abs(est - true), true),
            "times_narrower_than_utility1": _r(widths[1] / w) if w else None,
            "times_wider_than_utility5": _r(w / widths[5]) if widths[5] else None,
        },
    }


# ── 프롬프트 ──────────────────────────────────────────────
_SYSTEM = """너는 차등 프라이버시 데이터 플랫폼의 관리자 화면에서 시뮬레이션 결과를 설명하는 해설가다.
읽는 사람은 통계·프라이버시 비전문가인 관리자이고, 이 해설을 보고 데이터셋의 Utility 레벨(1~5)을 고른다.

[배경 지식 — 해설에 그대로 옮길 필요는 없다]
- Utility 레벨이 높을수록 분석가가 같은 질의를 더 많이 반복할 수 있다(queries).
- 질의 응답에는 매번 무작위 노이즈가 섞인다. 응답을 많이 모아 평균 내면 실제 값에 가까워지고,
  95% 신뢰구간 폭이 좁아진다.
- 신뢰구간이 좁다 = 유틸리티 관점: 분석 결과가 정밀하다
                  = 프라이버시 관점: 같은 질의를 반복하는 사람이 실제 값을 더 정확히 알아낼 수 있다(보호가 약해진다).
- 이 시뮬레이션의 신뢰구간은 노이즈로 인한 불확실성만 나타낸다.

[작성 규칙]
- 한국어 존댓말, 한 문단, 4~6문장, 350자 안팎. 제목·목록·마크다운·이모지 금지.
- 순서:
  ① 선택한 Utility 에서 몇 번 질의한 뒤 신뢰구간 폭이 얼마인지, 평균값 대비 몇 % 인지로 체감되게 설명
  ② 다른 레벨(특히 Utility 1, Utility 5)과 비교
  ③ 유틸리티 관점(분석가가 얻는 정밀도)
  ④ 프라이버시 관점(반복 질의로 실제 값을 얼마나 좁혀 알아낼 수 있는지)
  ⑤ 어떤 상황에 이 레벨이 어울리는지 한 문장 — 특정 레벨을 정답처럼 강요하지 말 것
- 숫자는 입력 JSON 의 값만 쓰고 새로 계산하지 마라(배율·%는 이미 계산되어 있다). 금액에는 단위를 붙여라.
- 'ε', '엡실론', '라플라스', '민감도', '분산' 같은 전문 용어는 쓰지 말고 '노이즈', '질의 횟수'처럼 쉬운 말로 바꿔라.
- 레벨은 반드시 'Utility N' 으로 표기한다.
- "완벽히 안전하다", "위험하다" 같은 단정은 피한다."""


def _call(payload: dict, model: str, timeout: float) -> str:
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.3,
        max_tokens=600,
        timeout=timeout,
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise ValueError("빈 응답")
    return text


# ── 공개 API ──────────────────────────────────────────────
def _key(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def cached(payload: dict) -> str | None:
    with _LOCK:
        return _CACHE.get(_key(payload))


def submit(payload: dict, *, model: str = DEFAULT_MODEL,
           timeout: float = DEFAULT_TIMEOUT) -> Future:
    """해설 생성을 백그라운드로 시작한다. 실패는 Future.result() 에서 예외로 나온다(캐시 안 함)."""
    key = _key(payload)

    def job() -> str:
        with _LOCK:
            if key in _CACHE:
                return _CACHE[key]
        text = _call(payload, model, timeout)
        with _LOCK:
            _CACHE[key] = text
        return text

    return _POOL.submit(job)