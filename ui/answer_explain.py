"""질의 콘솔 — 응답 아래 자연어 해설 (OpenAI 1회 호출).

넘기는 정보: 질문 · 통계 종류(질의코드) · 통계 대상 · 응답값(노이즈 적용 후) · 단위 · ε
원칙
    · 분석가 응답은 노이즈를 붙인 값만 넘긴다 (원본 금지).
    · 숫자는 여기서 소수점 둘째 자리로 정리해 넘기고, LLM 이 바꾸면 버린다.
    · 실패해도 질의는 그대로 진행 — 정해진 문장으로 대신한다.
DP_EXPLAIN=off 이면 LLM 을 부르지 않고 정해진 문장만 쓴다.
"""
from __future__ import annotations

import json
import os

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT = 8.0

CODE_LABEL = {
    "MEAN": "평균", "MEDIAN": "중앙값", "MAX": "최댓값", "MIN": "최솟값",
    "DIFF_MEAN": "두 집단의 평균 차이", "DIFF_MEDIAN": "두 집단의 중앙값 차이",
    "DIFF_MAX": "두 집단의 최댓값 차이", "DIFF_MIN": "두 집단의 최솟값 차이",
    "MAX_MIN": "최댓값과 최솟값의 차이", "MEAN_MEDIAN": "평균과 중앙값의 차이",
}

_SYSTEM = """너는 차등 프라이버시 데이터 플랫폼의 질의 콘솔에서 통계 응답을 한두 문장으로 풀어 주는 도우미다.
읽는 사람은 비전문가 분석가다.

[작성 규칙]
- 한국어 존댓말, 정확히 2문장, 120자 안팎. 마크다운·목록·이모지 금지.
- 1문장: 질문에 대한 답을 자연스러운 문장으로 말한다.
  값은 입력의 value 문자열을 글자 그대로 옮긴다(반올림·단위 변환·자릿수 변경 금지).
  unit 이 있으면 값 뒤에 붙이고, 비어 있으면 단위를 지어내지 마라.
  noised 가 true 이면 값 앞에 '약' 또는 '대략'을 붙인다.
- 2문장:
  noised 가 true 이면 "개인정보 보호를 위해 ε={epsilon} 차등 프라이버시를 보장하는 노이즈가 더해진 값이에요" 라는 취지로 쓴다.
  noised 가 false 이면 "관리자 계정이라 노이즈를 더하지 않은 원본 값이에요" 라는 취지로 쓴다.
- 질문에 없는 비교·원인·해석(예: '흡연자보다 낮습니다')은 덧붙이지 마라."""


def fmt_value(v) -> str:
    """7249.80844 → '7,249.81'. 숫자가 아니면 문자열 그대로."""
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v).strip()


def template(value_s: str, *, unit: str = "", eps: float = 0.1, noised: bool = True) -> str:
    u = f" {unit}" if unit else ""
    if noised:
        return (f"결과는 약 {value_s}{u}입니다. 개인정보 보호를 위해 "
                f"ε={eps:g} 차등 프라이버시를 보장하는 노이즈가 더해진 값이에요.")
    return f"결과는 {value_s}{u}입니다. 관리자 계정이라 노이즈를 더하지 않은 원본 값이에요."


def _on() -> bool:
    return os.getenv("DP_EXPLAIN", "on").strip().lower() not in ("off", "0", "false", "no")


def explain(question: str, value, *, qcode: str | None, measure: str,
            unit: str = "", eps: float = 0.1, noised: bool = True,
            model: str = DEFAULT_MODEL, timeout: float = DEFAULT_TIMEOUT) -> str:
    value_s = fmt_value(value)
    fallback = template(value_s, unit=unit, eps=eps, noised=noised)
    if not _on():
        return fallback

    payload = {
        "question": question,
        "statistic": CODE_LABEL.get(qcode or "", "통계량"),
        "measure": measure,
        "value": value_s,
        "unit": unit,
        "noised": noised,
        "epsilon": eps,
    }
    try:
        from openai import OpenAI
        resp = OpenAI().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=150,
            timeout=timeout,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text or value_s not in text:        # 숫자를 바꿨으면 버린다
            print(f"[explain] fallback: value mismatch → {text[:60]!r}")
            return fallback
        return text
    except Exception as e:                          # noqa: BLE001
        print(f"[explain] fallback: {type(e).__name__}: {e}")
        return fallback