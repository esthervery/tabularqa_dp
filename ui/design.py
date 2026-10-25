"""v17 디자인 시스템 — Streamlit 위에 얹는 시각 레이어.

이 파일이 지키는 세 가지
    1) 오버레이 금지. position:fixed/absolute 로 띄우는 요소를 만들지 않는다.
       (이전 화면에서 버튼이 구분선 위에 겹쳐 보인 것은 하단 고정 입력창과
        압축된 gap 이 만든 문제였다.)
    2) 간격은 넉넉하게. Streamlit 기본 gap 을 유지하고, 카드 안쪽 여백을 키운다.
       여백이 곧 위계다 — 조인 여백은 모든 요소를 같은 무게로 만들어 '양산형'이 된다.
    3) 타입은 4단계만. 22(수치) / 16(제목) / 13(본문) / 10(메타). 그 사이 값은 쓰지 않는다.

토큰은 v14 시안의 팔레트를 그대로 쓰고, 타이포는 Pretendard + IBM Plex Mono.
"""
from __future__ import annotations

import math
import re

import streamlit as st

TOKEN = {
    "pri": "#5457e0", "pri2": "#3f42b8", "prisoft": "#eef0fe", "priline": "#cdd2fb",
    "suc": "#0d9f7a", "sucsoft": "#e8f8f2", "sucline": "#a8e5d0",
    "dan": "#e0455f", "dansoft": "#fdeef0", "danline": "#f7c6cf",
    "wrn": "#c98a1a", "wrnsoft": "#fdf6e7", "wrnline": "#f3dfae",
    "ink": "#101828", "ink2": "#333f52", "mid": "#5a6779", "dim": "#8896a8",
    "bd": "#e4e8ee", "bd2": "#eef1f5", "wash": "#f7f9fc",
}


_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root{
  --pri:#5457e0; --pri2:#3f42b8; --prisoft:#eef0fe; --priline:#cdd2fb;
  --suc:#0d9f7a; --sucsoft:#e8f8f2; --sucline:#a8e5d0;
  --dan:#e0455f; --dansoft:#fdeef0; --danline:#f7c6cf;
  --wrn:#c98a1a; --wrnsoft:#fdf6e7; --wrnline:#f3dfae;
  --ink:#101828; --ink2:#333f52; --mid:#5a6779; --dim:#8896a8;
  --bd:#e4e8ee; --bd2:#eef1f5; --wash:#f7f9fc;
  --sans:'Pretendard Variable',Pretendard,-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
  --mono:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
}

/* ══ 골격 ═══════════════════════════════════════════════ */
html,body,[class*="st-"],.stApp,button,input,textarea,select{
  font-family:var(--sans) !important; -webkit-font-smoothing:antialiased;
}
.stApp{background:#fff}
p,li,span,div,label{color:var(--ink2)}
strong,b{color:var(--ink);font-weight:600}

/* 네이티브 사이드바는 쓰지 않는다 (라우팅은 hidden 네비게이션). */
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"]{display:none !important}
[data-testid="stHeader"]{background:transparent}
[data-testid="stToolbar"],[data-testid="stAppDeployButton"],
[data-testid="stDecoration"],[data-testid="stStatusWidget"],#MainMenu,footer{
  display:none !important;
}
[data-testid="stMainBlockContainer"],.block-container{
  padding:1.1rem 2rem 3rem !important; max-width:100% !important;
}

/* ══ 타이포 4단계 ═══════════════════════════════════════ */
h1,h2,h3,h4{color:var(--ink) !important;letter-spacing:-.02em;font-weight:700}
h1{font-size:1.15rem !important} h2{font-size:1rem !important}
h3{font-size:.9rem !important}  h4{font-size:.82rem !important}
[data-testid="stMarkdownContainer"] p{font-size:13px;line-height:1.65;letter-spacing:-.005em}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p{
  font-size:10px !important;color:var(--dim) !important
}

/* ══ 왼쪽 네비 칼럼 ═════════════════════════════════════ */
/* ══ 상단 네비게이션 ═══════════════════════════════════ */
.navbrand{display:flex;align-items:center;gap:10px;padding:0}
.navbrand .mark{width:28px;height:28px;border-radius:8px;background:var(--pri);color:#fff;
  display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;
  font-family:var(--mono);flex:0 0 28px;box-shadow:0 3px 10px -3px rgba(84,87,224,.55)}
.navbrand .who{display:flex;flex-direction:column;line-height:1.22}
.navbrand .who b{font-size:14px;font-weight:700;color:var(--ink);letter-spacing:-.02em}
.navbrand .who span{font-family:var(--mono);font-size:7.5px;letter-spacing:.13em;color:var(--dim)}

/* 탭 — 테두리·배경 없는 텍스트 링크.
   reference(AIPL) 처럼 외곽선이 보이지 않고, 선택된 항목만 색·굵기로 구분한다. */
[class*="st-key-nav_"] button{
  border:none !important; background:transparent !important;
  color:var(--mid) !important; font-size:13px !important; font-weight:500 !important;
  padding:9px 10px !important; min-height:0 !important; height:auto !important;
  box-shadow:none !important; border-radius:7px !important;
  letter-spacing:-.012em; white-space:nowrap;
}
[class*="st-key-nav_"] button:hover{
  background:var(--prisoft) !important; color:var(--pri2) !important;
  border:none !important; box-shadow:none !important;
}
[class*="st-key-nav_"] button[kind="primary"]{
  background:transparent !important; border:none !important;
  color:var(--pri) !important; font-weight:700 !important; box-shadow:none !important;
}
[class*="st-key-nav_"] button[kind="primary"]:hover{
  background:var(--prisoft) !important; color:var(--pri2) !important;
}
/* 로그아웃 — 같은 텍스트 톤. 계정 정보 바로 옆에 붙는다. */
[class*="st-key-nav_logout"] button{
  border:none !important; background:transparent !important;
  color:var(--dim) !important; font-size:12px !important; font-weight:500 !important;
  padding:9px 8px !important; min-height:0 !important; height:auto !important;
  box-shadow:none !important; border-radius:7px !important;
}
[class*="st-key-nav_logout"] button:hover{
  background:var(--dansoft) !important; color:var(--dan) !important;
}

/* 계정 (우측) */
.navuser{display:flex;align-items:center;gap:7px;padding:0 2px 0 6px}
.navuser .av{width:24px;height:24px;border-radius:7px;background:var(--prisoft);
  border:1px solid var(--priline);color:var(--pri2);display:flex;align-items:center;
  justify-content:center;font-family:var(--mono);font-size:8.5px;font-weight:600;flex:0 0 24px}
.navuser .u{display:flex;flex-direction:column;line-height:1.25;text-align:right;min-width:0}
.navuser .u b{font-size:12px;font-weight:600;color:var(--ink)}
.navuser .u span{font-family:var(--mono);font-size:8px;color:var(--dim)}

.navwarn{border:1px solid var(--danline);background:var(--dansoft);color:#a32a3f;
  border-radius:8px;padding:9px 12px;font-size:11px;line-height:1.55;margin-top:8px}
.navsep{width:1px;height:18px;background:var(--bd);margin:0 8px;flex:0 0 1px}
.navrule{height:1px;background:var(--bd);margin:14px 0 18px}

/* ══ 버튼 ═══════════════════════════════════════════════ */
.stButton>button,.stFormSubmitButton>button{
  border-radius:8px !important;border:1px solid var(--bd) !important;
  background:#fff !important;color:var(--ink2) !important;
  font-size:12.5px !important;font-weight:500 !important;
  padding:0.45rem 0.9rem !important;min-height:36px !important;
  box-shadow:0 1px 2px rgba(16,24,40,.04);letter-spacing:-.01em;
  transition:border-color .14s,background .14s,color .14s,box-shadow .14s;
}
.stButton>button:hover,.stFormSubmitButton>button:hover{
  border-color:var(--priline) !important;background:var(--prisoft) !important;
  color:var(--pri2) !important;box-shadow:0 3px 10px -4px rgba(84,87,224,.35);
}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{
  background:var(--pri) !important;border-color:var(--pri) !important;color:#fff !important;
  font-weight:600 !important;box-shadow:0 4px 12px -4px rgba(84,87,224,.55);
}
.stButton>button[kind="primary"]:hover,.stFormSubmitButton>button[kind="primary"]:hover{
  background:var(--pri2) !important;border-color:var(--pri2) !important;color:#fff !important;
}

/* ══ 입력 ═══════════════════════════════════════════════ */
[data-testid="stWidgetLabel"] p{font-size:10.5px !important;font-weight:500 !important;
  color:var(--dim) !important;letter-spacing:.01em}
div[data-baseweb="select"]>div{
  border-radius:8px !important;border:1px solid var(--bd) !important;background:#fff !important;
  min-height:38px !important;font-size:13px !important;font-weight:600 !important;
  color:var(--ink) !important;box-shadow:0 1px 2px rgba(16,24,40,.04);
}
div[data-baseweb="select"]>div:focus-within{border-color:var(--pri) !important;
  box-shadow:0 0 0 3px rgba(84,87,224,.13) !important}
.stTextInput input,.stTextArea textarea{
  border-radius:8px !important;border:1px solid var(--bd) !important;
  background:#fcfdff !important;font-size:13px !important;color:var(--ink2) !important;
}
.stTextInput input:focus,.stTextArea textarea:focus{
  border-color:var(--pri) !important;background:#fff !important;
  box-shadow:0 0 0 3px rgba(84,87,224,.13) !important;
}
.stTextArea textarea{line-height:1.65 !important;padding:0.6rem 0.75rem !important}

/* 라디오 → 세그먼트 카드 */
[data-testid="stRadio"] [role="radiogroup"]{display:flex !important;flex-wrap:wrap;gap:8px}
[data-testid="stRadio"] [role="radiogroup"]>label{
  flex:1 1 0;min-width:120px;margin:0 !important;display:flex !important;
  align-items:center;justify-content:center;padding:11px 14px !important;
  border:1px solid var(--bd);border-radius:9px;background:#fff;cursor:pointer;
  box-shadow:0 1px 2px rgba(16,24,40,.04);
  transition:border-color .14s,background .14s,box-shadow .14s;
}
[data-testid="stRadio"] [role="radiogroup"]>label:hover{border-color:var(--priline);background:var(--prisoft)}
[data-testid="stRadio"] [role="radiogroup"]>label>div:first-child{display:none !important}
[data-testid="stRadio"] [role="radiogroup"]>label p{
  font-size:12.5px !important;font-weight:600 !important;color:var(--ink2) !important;margin:0 !important
}
[data-testid="stRadio"] [role="radiogroup"]>label:has(input:checked){
  border-color:var(--pri);background:var(--prisoft);
  box-shadow:inset 0 0 0 1px var(--pri),0 4px 12px -5px rgba(84,87,224,.5);
}
[data-testid="stRadio"] [role="radiogroup"]>label:has(input:checked) p{color:var(--pri2) !important}

/* ══ 알림 / 폼 컨테이너 ═════════════════════════════════ */
[data-testid="stAlert"]{border-radius:9px !important;padding:0.7rem 0.9rem !important;
  box-shadow:none}
[data-testid="stAlert"] p{font-size:12px !important;line-height:1.6}
[data-testid="stForm"]{border:none !important;padding:0 !important}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:10px}

/* ══ 커스텀 블록 ════════════════════════════════════════ */
.topbar{display:flex;align-items:center;gap:10px;padding:0 0 14px;
  border-bottom:1px solid var(--bd);margin-bottom:16px}
.topbar .mark{width:26px;height:26px;border-radius:7px;background:var(--pri);color:#fff;
  display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;
  font-family:var(--mono);box-shadow:0 3px 10px -3px rgba(84,87,224,.55)}
.topbar .who{display:flex;flex-direction:column;line-height:1.2}
.topbar .who b{font-size:13.5px;font-weight:700;color:var(--ink);letter-spacing:-.02em}
.topbar .who span{font-family:var(--mono);font-size:7.5px;letter-spacing:.13em;color:var(--dim)}
.topbar .dv{width:1px;height:16px;background:var(--bd);margin:0 6px}
.topbar .crumb{font-size:11px;color:var(--dim)}
.topbar .crumb i{font-style:normal;font-family:var(--mono);font-size:9px;letter-spacing:.06em}
.topbar .crumb b{color:var(--ink2);font-weight:600}

.phead{display:flex;align-items:baseline;gap:10px;margin:0 0 16px}
.phead .ptitle{font-size:16px;font-weight:700;color:var(--ink);letter-spacing:-.025em}
.phead .pdesc{font-size:11px;color:var(--dim)}

.card{background:#fff;border:1px solid var(--bd);border-radius:11px;padding:18px 20px;
  margin:0 0 12px;box-shadow:0 1px 2px rgba(16,24,40,.03)}
.card .rh{font-size:13px;font-weight:700;color:var(--ink);margin-bottom:12px;letter-spacing:-.02em}
.card .rsub{font-size:11px;color:var(--dim)}

.band{border:1px solid var(--bd);border-radius:11px;background:var(--wash);
  padding:14px 16px 8px;margin:0 0 18px}
.bandhead{display:flex;align-items:center;gap:12px;margin-bottom:10px}
.blab{min-width:92px;display:flex;flex-direction:column;gap:2px}
.blab .t{font-size:11.5px;font-weight:700;color:var(--ink);letter-spacing:-.015em}
.blab .s{font-family:var(--mono);font-size:8px;color:var(--dim)}
.strip{display:flex;gap:9px;overflow-x:auto;padding-bottom:8px;scrollbar-width:thin}
.strip::-webkit-scrollbar{height:5px}
.strip::-webkit-scrollbar-thumb{background:#d5dbe4;border-radius:9px}
.fcard{flex:0 0 190px;width:190px;height:104px;border:1px solid var(--bd);border-radius:9px;
  background:#fff;padding:9px 11px;display:flex;flex-direction:column;overflow:hidden;
  box-sizing:border-box;box-shadow:0 1px 2px rgba(16,24,40,.03)}
.fcard .fct{display:flex;align-items:baseline;justify-content:space-between;gap:6px;
  padding-bottom:7px;border-bottom:1px solid var(--bd2)}
.fcard .fcl{font-size:10.5px;font-weight:600;color:var(--ink);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.fcard .fck{font-family:var(--mono);font-size:7.5px;color:var(--dim);white-space:nowrap}
.fcard .fcv{display:flex;flex-wrap:wrap;gap:5px;align-content:flex-start;margin-top:8px;
  overflow-y:auto;flex:1}
.fcard .fcv::-webkit-scrollbar{width:4px}
.fcard .fcv::-webkit-scrollbar-thumb{background:#dde2ea;border-radius:9px}
.vchip{font-family:var(--mono);font-size:8.5px;color:var(--ink2);background:var(--wash);
  border:1px solid var(--bd2);border-radius:5px;padding:3px 6px;white-space:nowrap}
.vchip.bin{background:var(--prisoft);border-color:var(--priline);color:var(--pri2)}
.faxis{margin-top:11px;flex:1;display:flex;flex-direction:column;justify-content:center;gap:9px}
.faxis .ftr{height:4px;border-radius:9px;position:relative;
  background:linear-gradient(90deg,#d9ddf1,#eceefb,#d9ddf1)}
.faxis .ftr i{position:absolute;top:-3px;width:1px;height:10px;background:var(--priline)}
.faxis .fql{display:flex;justify-content:space-between;font-family:var(--mono);
  font-size:8.5px;color:var(--mid)}
.faxis .fql b{color:var(--ink2);font-weight:600}

.donutwrap{display:flex;align-items:center;gap:10px;justify-content:flex-end}
.donutwrap .dt{display:flex;flex-direction:column;line-height:1.35;text-align:right}
.donutwrap .dt b{font-family:var(--mono);font-size:12px;color:var(--ink);font-weight:600}
.donutwrap .dt span{font-size:9px;color:var(--dim)}

.thread{display:flex;flex-direction:column;gap:20px;padding:4px 0 8px}
.msg{display:flex;gap:11px;align-items:flex-start}
.msg .av{width:24px;height:24px;border-radius:7px;flex:0 0 24px;display:flex;
  align-items:center;justify-content:center;font-family:var(--mono);font-size:9px;font-weight:600}
.msg.u .av{background:var(--wash);border:1px solid var(--bd);color:var(--mid)}
.msg.a .av{background:var(--pri);color:#fff;box-shadow:0 3px 10px -3px rgba(84,87,224,.55)}
.bub{flex:1;min-width:0}
.bub .q{font-size:13px;color:var(--ink);line-height:1.65;word-break:break-word;letter-spacing:-.01em}
.bub .qmeta{font-family:var(--mono);font-size:8px;color:var(--dim);margin-top:5px}
.anscode{background:#0f1729;border-radius:9px;padding:13px 15px;margin-top:9px;
  font-family:var(--mono);font-size:10px;line-height:1.7;color:#c8d2e4;
  white-space:pre-wrap;word-break:break-word;overflow-x:auto}
.anscode .cm{color:#6b7891}
.anscode .kw{color:#a5b4fc}
.res{display:flex;align-items:baseline;gap:10px;margin-top:9px;padding:11px 14px;
  border:1px solid var(--sucline);background:var(--sucsoft);border-radius:9px}
.res .rk{font-size:10.5px;color:var(--mid)}
.res .rn{font-family:var(--mono);font-size:17px;font-weight:600;color:var(--suc)}
.res .rt{margin-left:auto;font-family:var(--mono);font-size:8px;color:var(--dim)}
.warn{border:1px solid var(--danline);background:var(--dansoft);color:#a32a3f;
  border-radius:9px;padding:12px 14px;font-size:12px;line-height:1.6}
.hintline{border:1px solid var(--wrnline);background:var(--wrnsoft);color:#8a5f11;
  border-radius:9px;padding:10px 13px;font-size:11px;margin-top:9px}
.empty{border:1px dashed var(--bd);border-radius:11px;padding:38px 18px;text-align:center;
  color:var(--dim);font-size:12px;background:var(--wash)}

.reqline{display:flex;align-items:center;gap:9px;font-size:11px;color:var(--dim);
  border:1px solid var(--bd2);background:var(--wash);border-radius:8px;padding:10px 13px;
  margin:0 0 6px}
.reqline b{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--ink2)}
.reqline .vl{width:1px;height:10px;background:var(--bd);margin:0 4px}
.reqdiv{height:1px;background:var(--bd2);margin:16px 0 14px}
.row{display:flex;align-items:center;gap:12px}
.row.between{justify-content:space-between}
.grow{flex:1;min-width:0}
.mono{font-family:var(--mono)}
.dim{color:var(--dim)}
.tag{font-family:var(--mono);font-size:8.5px;padding:3px 7px;border-radius:5px;
  border:1px solid var(--bd);color:var(--mid);background:var(--wash)}
.tag.p{background:var(--wrnsoft);border-color:var(--wrnline);color:#8a5f11}
.tag.a{background:var(--sucsoft);border-color:var(--sucline);color:#0b7a5d}
.tag.r{background:var(--dansoft);border-color:var(--danline);color:#a32a3f}
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def topbar(page: str, role: str) -> str:
    """v18: 브랜드는 상단 네비게이션이 들고 있으므로 본문에서는 그리지 않는다.

    각 페이지가 st.markdown(design.topbar(...)) 를 그대로 호출해도 되도록
    시그니처는 유지하고 빈 문자열을 돌려준다 (페이지 파일 수정 불필요).
    """
    return ""


def page_head(title: str, desc: str) -> str:
    return (f'<div class="phead"><span class="ptitle">{title}</span>'
            f'<span class="pdesc">{desc}</span></div>')


def donut(ratio: float, label: str = "", sub: str = "", size: int = 48) -> str:
    ratio = max(0.0, min(1.0, float(ratio)))
    r = (size - 8) / 2
    c = size / 2
    circ = 2 * math.pi * r
    dash = circ * ratio
    color = "#0d9f7a" if ratio < 0.6 else ("#c98a1a" if ratio < 0.9 else "#e0455f")
    return f'''<div class="donutwrap">
  <div class="dt"><b>{label}</b><span>{sub}</span></div>
  <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
    <circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="#e4e8ee" stroke-width="5"/>
    <circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{color}" stroke-width="5"
      stroke-linecap="round" stroke-dasharray="{dash:.2f} {circ - dash:.2f}"
      transform="rotate(-90 {c} {c})"/>
    <text x="{c}" y="{c + 3.4}" text-anchor="middle" font-size="9.5" font-weight="700"
      font-family="IBM Plex Mono,monospace" fill="#101828">{ratio * 100:.0f}%</text>
  </svg></div>'''


def field_card(f: dict) -> str:
    kind = f.get("kind", "categorical")
    label = f.get("label", f.get("col", ""))
    meta = {"categorical": "cat", "filter": "num", "pattern": "bin"}.get(kind, kind)

    if kind == "filter":
        q = f.get("quartiles") or [None, None, None]
        ticks = "".join('<i style="left:%d%%"></i>' % p for p in (0, 50, 100))
        cells = "".join(f'<span>{n} <b>{_num(v)}</b></span>'
                        for n, v in zip(("Q1", "Q2", "Q3"), q))
        body = f'<div class="faxis"><div class="ftr">{ticks}</div><div class="fql">{cells}</div></div>'
    else:
        chips = "".join(
            f'<span class="vchip{" bin" if kind == "pattern" else ""}">{v.get("t", "")}</span>'
            for v in (f.get("values") or []))
        body = f'<div class="fcv">{chips}</div>'

    n = f.get("n", len(f.get("values") or []))
    return (f'<div class="fcard"><div class="fct"><span class="fcl">{label}</span>'
            f'<span class="fck">{meta} · {n}</span></div>{body}</div>')


def strip(cards: list[str]) -> str:
    return '<div class="strip">' + "".join(cards) + "</div>"


def band(label: str, sub: str, cards: list[str]) -> str:
    return (f'<div class="band"><div class="bandhead"><div class="blab">'
            f'<span class="t">{label}</span><span class="s">{sub}</span></div></div>'
            f'{strip(cards)}</div>')


def bubble_user(text: str, meta: str = "") -> str:
    m = f'<div class="qmeta">{meta}</div>' if meta else ""
    return (f'<div class="msg u"><div class="av">U</div><div class="bub">'
            f'<div class="q">{_esc(text)}</div>{m}</div></div>')


def bubble_agent(code: str | None, answer: str, *, label: str = "결과",
                 eps: float | None = None, note: str = "") -> str:
    inner = ""
    if code:
        inner += f'<div class="anscode">{_hl(code)}</div>'
    if note:
        inner += f'<div class="hintline">{note}</div>'
    if answer:
        unit = f' · ε {eps:.2f}' if eps else ""
        inner += (f'<div class="res"><span class="rk">{label}</span>'
                  f'<span class="rn">{_esc(answer)}</span>'
                  f'<span class="rt">DP 응답{unit}</span></div>')
    return f'<div class="msg a"><div class="av">D</div><div class="bub">{inner}</div></div>'


def warn(text: str) -> str:
    return f'<div class="warn">{_esc(text)}</div>'


def empty(text: str) -> str:
    return f'<div class="empty">{text}</div>'


def line(pairs: list[tuple[str, str]]) -> str:
    out = []
    for i, (k, v) in enumerate(pairs):
        if i:
            out.append('<span class="vl"></span>')
        out.append(f"{k} <b>{v}</b>")
    return '<div class="reqline">' + "".join(out) + "</div>"


def _num(v) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{f:,.0f}" if abs(f) >= 1000 else (f"{f:.1f}".rstrip("0").rstrip("."))


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


_KEYWORDS = ("import", "from", "def", "return", "for", "in", "if", "else",
             "df", "and", "or", "not", "groupby", "round", "median", "mean")


def _hl(code: str) -> str:
    out = []
    for ln in str(code).split("\n"):
        if ln.strip().startswith("#"):
            out.append(f'<span class="cm">{_esc(ln)}</span>')
            continue
        buf = []
        for p in re.split(r"(\b[A-Za-z_]+\b)", ln):
            buf.append(f'<span class="kw">{_esc(p)}</span>' if p in _KEYWORDS else _esc(p))
        out.append("".join(buf))
    return "\n".join(out)