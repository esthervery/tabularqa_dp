"""시각화 유틸리티 (개발 단계용 · 최소 CSS).

이 모듈이 제공하는 것:
    inject_global_css()  - 각 페이지 상단에서 한 번 호출. 지금은 no-op 에 가깝다.
    donut_gauge(...)     - 진행률 도넛(SVG) HTML 문자열. st.markdown 으로 렌더.
    bar_gauge(...)       - 진행률 막대(SVG) HTML 문자열. st.markdown 으로 렌더.

CSS 를 걷어냈기 때문에 컨테이너, 버튼, 배지 같은 요소는
Streamlit 기본 스타일 그대로 노출된다.
게이지처럼 시각적으로 필요한 것들만 SVG 로 남긴다.
"""
from __future__ import annotations
import math
import streamlit as st


# 색 팔레트 (SVG 게이지가 참조)
PALETTE = {
    "primary": "#6366f1",   # 인디고 - 기본
    "success": "#10b981",   # 에메랄드 - 안전 (60% 미만)
    "warning": "#f59e0b",   # 앰버   - 주의 (60-90%)
    "danger":  "#f43f5e",   # 로즈   - 초과 임박 (90% 이상)
}


def inject_global_css() -> None:
    """개발 단계에서는 거의 아무것도 하지 않는다.
    운영 배포 시 이 함수의 st.markdown 을 채우면 전역 CSS 를 다시 켤 수 있다."""
    return None


# ── 도넛 게이지 ─────────────────────────────────────────────

def donut_gauge(
    label: str,
    value: float,
    total: float,
    *,
    unit: str = "ε",
    size: int = 96,
    tone: str = "primary",
    sub: str | None = None,
) -> str:
    """진행률(value/total)을 도넛으로 그린 카드 HTML 을 반환.

    사용법:
        st.markdown(theme.donut_gauge("누적 소모", spent, cap, tone="warning"),
                    unsafe_allow_html=True)

    tone: primary / success / warning / danger
    """
    total = max(total, 1e-9)
    ratio = max(0.0, min(1.0, value / total))
    color = PALETTE.get(tone, PALETTE["primary"])

    r = (size - 12) / 2
    cx = cy = size / 2
    circ = 2 * math.pi * r
    dash = circ * ratio
    gap = circ - dash
    if sub is None:
        sub = f"{value:.2f} / {total:.2f} {unit}"

    return f'''
<div style="display:flex;align-items:center;gap:16px;padding:12px 14px;
            border:1px solid #e2e8f0;border-radius:10px;background:white;">
  <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none"
            stroke="#e2e8f0" stroke-width="10"/>
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none"
            stroke="{color}" stroke-width="10" stroke-linecap="round"
            stroke-dasharray="{dash:.2f} {gap:.2f}"
            transform="rotate(-90 {cx} {cy})"/>
    <text x="{cx}" y="{cy+5}" text-anchor="middle"
          font-size="18" font-weight="700" fill="#0f172a">
      {ratio*100:.0f}%</text>
  </svg>
  <div>
    <div style="font-size:11px;color:#64748b;text-transform:uppercase;
                letter-spacing:0.06em;font-weight:600;">{label}</div>
    <div style="font-size:22px;font-weight:700;margin-top:2px;">
      {value:.2f} <span style="font-size:14px;color:#64748b;">{unit}</span></div>
    <div style="font-size:12px;color:#64748b;margin-top:2px;">{sub}</div>
  </div>
</div>
'''


# ── 막대 게이지 ─────────────────────────────────────────────

def bar_gauge(
    label: str,
    value: float,
    total: float,
    *,
    unit: str = "",
    tone: str = "primary",
    sub: str | None = None,
) -> str:
    """수평 막대 진행률 카드 HTML 을 반환.

    도넛 대신 세로 공간이 부족한 곳에서 사용.
    """
    total = max(total, 1e-9)
    ratio = max(0.0, min(1.0, value / total))
    color = PALETTE.get(tone, PALETTE["primary"])
    if sub is None:
        sub = f"{value:.3f} / {total:.3f} {unit}".strip()

    return f'''
<div style="padding:12px 14px;border:1px solid #e2e8f0;border-radius:10px;
            background:white;">
  <div style="display:flex;justify-content:space-between;align-items:baseline;">
    <div>
      <div style="font-size:11px;color:#64748b;text-transform:uppercase;
                  letter-spacing:0.06em;font-weight:600;">{label}</div>
      <div style="font-size:20px;font-weight:700;margin-top:2px;">
        {value:.3f} <span style="font-size:12px;color:#64748b;">{unit}</span></div>
    </div>
    <div style="font-size:12px;color:#64748b;">{sub}</div>
  </div>
  <div style="height:8px;border-radius:999px;background:#f1f5f9;
              overflow:hidden;margin-top:8px;">
    <div style="height:100%;width:{ratio*100:.1f}%;background:{color};
                border-radius:999px;"></div>
  </div>
</div>
'''