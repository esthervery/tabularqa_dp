"""전역 스타일 & 재사용 시각화 헬퍼.

Streamlit 기본 컴포넌트 위에 얇게 얹는 CSS만 사용한다.
색 팔레트:
  primary  #6366f1   indigo
  success  #10b981   emerald
  danger   #f43f5e   rose
  warning  #f59e0b   amber
  ink      #0f172a   slate-900
  muted    #64748b   slate-500
  border   #e2e8f0   slate-200
  wash     #f8fafc   slate-50
"""
from __future__ import annotations
import math
import streamlit as st


PALETTE = {
    "primary": "#6366f1",
    "primary_soft": "#eef2ff",
    "success": "#10b981",
    "success_soft": "#ecfdf5",
    "danger": "#f43f5e",
    "danger_soft": "#fff1f2",
    "warning": "#f59e0b",
    "warning_soft": "#fffbeb",
    "ink": "#0f172a",
    "muted": "#64748b",
    "border": "#e2e8f0",
    "wash": "#f8fafc",
}


_GLOBAL_CSS = """
<style>
/* ── Base ──────────────────────────────────────────── */
:root {
  --dp-primary: #6366f1;
  --dp-primary-soft: #eef2ff;
  --dp-success: #10b981;
  --dp-success-soft: #ecfdf5;
  --dp-danger: #f43f5e;
  --dp-danger-soft: #fff1f2;
  --dp-warning: #f59e0b;
  --dp-warning-soft: #fffbeb;
  --dp-ink: #0f172a;
  --dp-muted: #64748b;
  --dp-border: #e2e8f0;
  --dp-wash: #f8fafc;
}

html, body, [class*="css"] {
  color: var(--dp-ink);
}

/* 페이지 여백 살짝 조이기 */
.block-container {
  padding-top: 2.2rem;
  padding-bottom: 3rem;
  max-width: 1400px;
}

/* ── Typography ────────────────────────────────────── */
h1, h2, h3, h4 { letter-spacing: -0.01em; }
h1 { font-weight: 700; }
h2, h3 { font-weight: 650; }
h4 { font-weight: 600; color: var(--dp-ink); }

/* Streamlit caption을 좀 더 부드럽게 */
.st-emotion-cache-1weic72, .stCaption, [data-testid="stCaptionContainer"] {
  color: var(--dp-muted) !important;
}

/* ── Sidebar ───────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border-right: 1px solid var(--dp-border);
}

[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSlider label,
[data-testid="stSidebar"] .stTextInput label {
  font-size: 0.78rem;
  color: var(--dp-muted);
  font-weight: 500;
}

[data-testid="stSidebarUserContent"] {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding-bottom: 1rem;
}
[data-testid="stSidebarUserContent"] > div[data-testid="stVerticalBlock"] {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  height: 100%;
}
.st-key-sidebar_bottom { margin-top: auto; }

/* ── Brand block (sidebar top) ─────────────────────── */
.dp-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0 14px 0;
  border-bottom: 1px solid var(--dp-border);
  margin-bottom: 14px;
}
.dp-brand-mark {
  width: 34px; height: 34px;
  border-radius: 9px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  display: flex; align-items: center; justify-content: center;
  color: white; font-weight: 700; font-size: 16px;
  box-shadow: 0 6px 16px -6px rgba(99, 102, 241, 0.55);
}
.dp-brand-name {
  font-weight: 700; font-size: 15px; color: var(--dp-ink);
  line-height: 1.1;
}
.dp-brand-sub {
  font-size: 11px; color: var(--dp-muted); margin-top: 2px;
  letter-spacing: 0.02em;
}

/* ── Buttons ───────────────────────────────────────── */
.stButton>button, .stDownloadButton>button {
  border-radius: 9px;
  border: 1px solid var(--dp-border);
  font-weight: 500;
  transition: all 0.15s ease;
}
.stButton>button:hover {
  border-color: var(--dp-primary);
  color: var(--dp-primary);
}
.stButton>button[kind="primary"] {
  background: var(--dp-primary);
  border-color: var(--dp-primary);
  color: white;
  box-shadow: 0 4px 12px -4px rgba(99, 102, 241, 0.5);
}
.stButton>button[kind="primary"]:hover {
  background: #4f46e5;
  border-color: #4f46e5;
  color: white;
}

/* ── Metric card (bordered) ────────────────────────── */
[data-testid="stMetric"] {
  background: white;
  border-radius: 12px;
}
[data-testid="stMetricLabel"] {
  color: var(--dp-muted) !important;
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
[data-testid="stMetricValue"] {
  color: var(--dp-ink) !important;
  font-weight: 700 !important;
  font-variant-numeric: tabular-nums;
}

/* ── Container border override ─────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: 12px !important;
  border-color: var(--dp-border) !important;
  background: white;
}

/* ── Text input / textarea ─────────────────────────── */
.stTextInput input, .stTextArea textarea, .stNumberInput input {
  border-radius: 9px !important;
  border-color: var(--dp-border) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
  border-color: var(--dp-primary) !important;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12) !important;
}

/* ── Tabs ──────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap: 4px;
  border-bottom: 1px solid var(--dp-border);
}
.stTabs [data-baseweb="tab"] {
  padding: 8px 14px;
  border-radius: 8px 8px 0 0;
  color: var(--dp-muted);
  font-weight: 500;
}
.stTabs [aria-selected="true"] {
  color: var(--dp-primary) !important;
  background: var(--dp-primary-soft);
}

/* ── Chat message ──────────────────────────────────── */
[data-testid="stChatMessage"] {
  background: transparent;
  border: none;
  padding: 0.6rem 0;
}

/* ── Code block ────────────────────────────────────── */
pre, code { border-radius: 9px !important; }
[data-testid="stCodeBlock"] {
  border: 1px solid var(--dp-border);
  border-radius: 9px;
}

/* ── Custom badges & pills ─────────────────────────── */
.dp-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 9px; border-radius: 999px;
  font-size: 11.5px; font-weight: 600;
  letter-spacing: 0.01em;
  border: 1px solid transparent;
}
.dp-pill--primary { background: var(--dp-primary-soft); color: #4338ca; border-color: #c7d2fe; }
.dp-pill--success { background: var(--dp-success-soft); color: #047857; border-color: #a7f3d0; }
.dp-pill--danger  { background: var(--dp-danger-soft);  color: #be123c; border-color: #fecdd3; }
.dp-pill--warning { background: var(--dp-warning-soft); color: #b45309; border-color: #fde68a; }
.dp-pill--muted   { background: #f1f5f9; color: var(--dp-muted); border-color: var(--dp-border); }
.dp-pill--dot::before {
  content: ""; width: 6px; height: 6px; border-radius: 999px;
  background: currentColor;
}

/* ── Section label (small caps) ────────────────────── */
.dp-eyebrow {
  font-size: 11px; color: var(--dp-muted);
  text-transform: uppercase; letter-spacing: 0.08em;
  font-weight: 600; margin: 0 0 6px 0;
}

/* ── Gauge card ────────────────────────────────────── */
.dp-gauge-card {
  background: white;
  border: 1px solid var(--dp-border);
  border-radius: 12px;
  padding: 16px 18px;
  display: flex; align-items: center; gap: 16px;
}
.dp-gauge-meta { flex: 1 1 auto; }
.dp-gauge-meta .lbl {
  font-size: 11px; color: var(--dp-muted);
  text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600;
}
.dp-gauge-meta .val {
  font-size: 22px; font-weight: 700; color: var(--dp-ink);
  font-variant-numeric: tabular-nums;
  margin-top: 2px;
}
.dp-gauge-meta .sub {
  font-size: 12px; color: var(--dp-muted); margin-top: 2px;
  font-variant-numeric: tabular-nums;
}

/* ── Login split layout ────────────────────────────── */
.dp-login-hero {
  background: linear-gradient(150deg, #eef2ff 0%, #f8fafc 55%, #ecfdf5 120%);
  border: 1px solid var(--dp-border);
  border-radius: 16px;
  padding: 32px 30px;
  /* height:100% 제거 — 자연 높이로 흐르게 */
}
.dp-login-hero h2 {
  font-size: 1.6rem; font-weight: 700; margin: 12px 0 8px 0;
  color: var(--dp-ink);
}
.dp-login-hero p {
  color: var(--dp-muted); font-size: 14px; line-height: 1.55; margin: 0;
}
.dp-login-hero .bullet {
  display: flex; gap: 10px; margin-top: 14px; align-items: flex-start;
}
.dp-login-hero .bullet-dot {
  flex: 0 0 auto; width: 22px; height: 22px; border-radius: 6px;
  background: white; border: 1px solid var(--dp-border);
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; color: var(--dp-primary); font-weight: 700;
}
.dp-login-hero .bullet-text {
  font-size: 13px; color: var(--dp-ink); line-height: 1.5;
}
.dp-login-hero .bullet-text b { color: var(--dp-ink); font-weight: 600; }
.dp-login-hero .bullet-text span { color: var(--dp-muted); }

/* Login form card — st.container(border=True, key="login_card") 를 타깃 */
.st-key-login_card {
  padding: 18px 22px 16px 22px !important;
  border-radius: 16px !important;
}
/* 내부에 st.form(border=False) 를 쓰지만, Streamlit 버전에 따라
   여전히 중첩 border wrapper 가 생길 수 있어 제거해준다. */
.st-key-login_card [data-testid="stVerticalBlockBorderWrapper"] {
  background: transparent;
  border: 0 !important;
  padding: 0 !important;
}

/* ── Request card (Budget Requests) ────────────────── */
.dp-req-card {
  background: white;
  border: 1px solid var(--dp-border);
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 10px;
}
.dp-req-head {
  display: flex; justify-content: space-between; align-items: center;
  gap: 10px; margin-bottom: 8px;
}
.dp-req-user {
  font-weight: 600; color: var(--dp-ink); font-size: 14px;
}
.dp-req-time { font-size: 11px; color: var(--dp-muted); }
.dp-req-reason {
  font-size: 13px; color: var(--dp-ink); line-height: 1.55;
  background: var(--dp-wash);
  border-radius: 8px; padding: 10px 12px;
  margin: 8px 0;
}
.dp-req-kv {
  display: flex; gap: 18px; font-size: 12px; color: var(--dp-muted);
  font-variant-numeric: tabular-nums;
}
.dp-req-kv b { color: var(--dp-ink); font-weight: 600; }

/* ── Timeline (approval history) ───────────────────── */
.dp-timeline { padding-left: 4px; }
.dp-timeline-item {
  position: relative; padding-left: 22px; padding-bottom: 14px;
  border-left: 2px solid var(--dp-border);
  margin-left: 6px;
}
.dp-timeline-item::before {
  content: ""; position: absolute; left: -7px; top: 2px;
  width: 12px; height: 12px; border-radius: 999px;
  background: white; border: 2px solid var(--dp-primary);
}
.dp-timeline-item.approved::before { border-color: var(--dp-success); }
.dp-timeline-item.rejected::before { border-color: var(--dp-danger); }
.dp-timeline-item.partial::before  { border-color: var(--dp-warning); }
.dp-timeline-time { font-size: 11px; color: var(--dp-muted); }
.dp-timeline-body { font-size: 13px; color: var(--dp-ink); margin-top: 2px; }

/* ── Hide default streamlit padding under st.status ── */
[data-testid="stStatusWidget"] { border-radius: 12px !important; }

/* ── Divider ───────────────────────────────────────── */
hr { border-color: var(--dp-border) !important; }
</style>
"""


def inject_global_css() -> None:
    """모든 페이지 최상단에서 한 번씩 호출한다."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


# ── HTML helpers ─────────────────────────────────────────────────────

def pill(label: str, tone: str = "muted") -> str:
    """dp-pill 마크업. tone: primary|success|danger|warning|muted"""
    return (
        f'<span class="dp-pill dp-pill--{tone} dp-pill--dot">{label}</span>'
    )


def eyebrow(text: str) -> None:
    st.markdown(f'<div class="dp-eyebrow">{text}</div>',
                unsafe_allow_html=True)


def brand_block(product: str = "DP Agent", tagline: str = "Differential Privacy Workspace") -> None:
    """사이드바 최상단 브랜드."""
    st.markdown(
        f'''
        <div class="dp-brand">
          <div class="dp-brand-mark">ε</div>
          <div>
            <div class="dp-brand-name">{product}</div>
            <div class="dp-brand-sub">{tagline}</div>
          </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


# ── SVG donut gauge ──────────────────────────────────────────────────

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
    """0..1 진행률을 도넛으로 그린 카드 HTML 문자열을 반환."""
    total = max(total, 1e-9)
    ratio = max(0.0, min(1.0, value / total))
    color_map = {
        "primary": PALETTE["primary"],
        "success": PALETTE["success"],
        "danger":  PALETTE["danger"],
        "warning": PALETTE["warning"],
    }
    color = color_map.get(tone, PALETTE["primary"])
    # SVG donut
    r = (size - 12) / 2
    cx = cy = size / 2
    circ = 2 * math.pi * r
    dash = circ * ratio
    gap = circ - dash
    if sub is None:
        sub = f"{value:.2f} / {total:.2f} {unit}"
    return (
        f'<div class="dp-gauge-card">'
        f'  <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'            stroke="#e2e8f0" stroke-width="10"/>'
        f'    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'            stroke="{color}" stroke-width="10" stroke-linecap="round"'
        f'            stroke-dasharray="{dash:.2f} {gap:.2f}"'
        f'            transform="rotate(-90 {cx} {cy})"/>'
        f'    <text x="{cx}" y="{cy+5}" text-anchor="middle" '
        f'          font-size="18" font-weight="700" fill="#0f172a" '
        f'          font-family="Source Sans Pro, sans-serif">'
        f'      {ratio*100:.0f}%</text>'
        f'  </svg>'
        f'  <div class="dp-gauge-meta">'
        f'    <div class="lbl">{label}</div>'
        f'    <div class="val">{value:.2f} <span style="font-size:14px;color:#64748b;font-weight:500;">{unit}</span></div>'
        f'    <div class="sub">{sub}</div>'
        f'  </div>'
        f'</div>'
    )


def bar_gauge(
    label: str,
    value: float,
    total: float,
    *,
    unit: str = "",
    tone: str = "primary",
    sub: str | None = None,
) -> str:
    """수평 막대 진행률 카드."""
    total = max(total, 1e-9)
    ratio = max(0.0, min(1.0, value / total))
    color_map = {
        "primary": PALETTE["primary"],
        "success": PALETTE["success"],
        "danger":  PALETTE["danger"],
        "warning": PALETTE["warning"],
    }
    color = color_map.get(tone, PALETTE["primary"])
    if sub is None:
        sub = f"{value:.3f} / {total:.3f} {unit}".strip()
    return (
        f'<div class="dp-gauge-card" style="flex-direction:column;align-items:stretch;gap:8px;">'
        f'  <div class="dp-gauge-meta" style="display:flex;justify-content:space-between;align-items:baseline;">'
        f'    <div>'
        f'      <div class="lbl">{label}</div>'
        f'      <div class="val">{value:.3f} <span style="font-size:13px;color:#64748b;font-weight:500;">{unit}</span></div>'
        f'    </div>'
        f'    <div class="sub">{sub}</div>'
        f'  </div>'
        f'  <div style="height:8px;border-radius:999px;background:#f1f5f9;overflow:hidden;">'
        f'    <div style="height:100%;width:{ratio*100:.1f}%;background:{color};border-radius:999px;"></div>'
        f'  </div>'
        f'</div>'
    )