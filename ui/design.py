"""v14 시안을 Streamlit 위에 재현하는 렌더 모듈.

화면 요소(토큰·CSS·카드·게이지)만 담당한다. 데이터는 각 페이지가 넘긴다.
시안(design/platform_v14.html)의 팔레트·타이포·치수를 그대로 옮겼다.

주요 API
    inject()                 전역 CSS 주입 (페이지당 1회)
    topbar(page, role)       상단 바 (브랜드 + 브레드크럼)
    page_head(title, desc)   페이지 제목 줄 (콘솔이 아닌 화면)
    donut(ratio, ...)        ε 예산 도넛 (SVG)
    field_card(f)            필드 힌트 카드 1장 (190×96)
    strip(cards)             필드 힌트 가로 스트립
    bubble_user(text)        사용자 말풍선
    bubble_agent(code, ans)  에이전트 말풍선 (코드 + 결과)
    band_line(label, value)  한 줄짜리 라벨/값 (정책 띠)
"""
from __future__ import annotations

import math

import streamlit as st

# ── 디자인 토큰 (platform_v14.html 과 동일) ──────────────
TOKEN = {
    "pri":      "#5457e0",
    "pri2":     "#3f42b8",
    "prisoft":  "#eef0fe",
    "priline":  "#cdd2fb",
    "suc":      "#0d9f7a",
    "sucsoft":  "#e8f8f2",
    "sucline":  "#a8e5d0",
    "dan":      "#e0455f",
    "dansoft":  "#fdeef0",
    "danline":  "#f7c6cf",
    "wrn":      "#c98a1a",
    "wrnsoft":  "#fdf6e7",
    "wrnline":  "#f3dfae",
    "ink":      "#101828",
    "ink2":     "#333f52",
    "mid":      "#5a6779",
    "dim":      "#8896a8",
    "bd":       "#e4e8ee",
    "bd2":      "#eef1f5",
    "wash":     "#f7f9fc",
}


_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+KR:wght@300;400;500;600;700&display=swap');

:root{
  --pri:#5457e0; --pri2:#3f42b8; --prisoft:#eef0fe; --priline:#cdd2fb;
  --suc:#0d9f7a; --sucsoft:#e8f8f2; --sucline:#a8e5d0;
  --dan:#e0455f; --dansoft:#fdeef0; --danline:#f7c6cf;
  --wrn:#c98a1a; --wrnsoft:#fdf6e7; --wrnline:#f3dfae;
  --ink:#101828; --ink2:#333f52; --mid:#5a6779; --dim:#8896a8;
  --bd:#e4e8ee; --bd2:#eef1f5; --wash:#f7f9fc;
  --sans:'IBM Plex Sans KR',-apple-system,system-ui,sans-serif;
  --mono:'IBM Plex Mono',ui-monospace,SFMono-Regular,monospace;
}

/* ── Streamlit 크롬 정리 ── */
[data-testid="stHeader"]{background:transparent;height:0}
[data-testid="stToolbar"]{display:none}
[data-testid="stDecoration"]{display:none}
#MainMenu{visibility:hidden}
footer{display:none}
[data-testid="stAppViewContainer"]{background:#fff}
[data-testid="stMainBlockContainer"],.block-container{
  padding:0 20px 22px !important; max-width:100% !important}
[data-testid="stSidebar"]{
  background:#fff; border-right:1px solid var(--bd); min-width:206px; max-width:206px}
[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding-top:0}
[data-testid="stSidebarCollapsedControl"]{color:var(--ink)}
html,body,p,span,div,label,button,input,textarea,select{font-family:var(--sans)}
p,li{color:var(--ink2)}
*{-webkit-font-smoothing:antialiased}

/* ── 상단 바 ── */
.topbar{display:flex;align-items:center;gap:9px;height:52px;
  border-bottom:1px solid var(--bd);margin-bottom:0}
.topbar .mark{width:23px;height:23px;border-radius:6px;background:var(--pri);
  color:#fff;display:flex;align-items:center;justify-content:center;
  font-size:11.5px;font-weight:700;font-family:var(--mono)}
.topbar .who{display:flex;flex-direction:column;line-height:1.15}
.topbar .who b{font-size:11.5px;font-weight:700;color:var(--ink);letter-spacing:.01em}
.topbar .who span{font-family:var(--mono);font-size:7.5px;letter-spacing:.11em;color:var(--dim)}
.topbar .dv{width:1px;height:14px;background:var(--bd);margin:0 4px}
.topbar .crumb{font-size:9.5px;color:var(--dim)}
.topbar .crumb i{font-style:normal;font-family:var(--mono);font-size:8.5px;letter-spacing:.05em}
.topbar .crumb b{color:var(--ink2);font-weight:600}

/* ── 페이지 제목 ── */
.phead{display:flex;align-items:baseline;gap:9px;margin:16px 0 12px}
.phead .ptitle{font-size:15px;font-weight:700;color:var(--ink);letter-spacing:-.01em}
.phead .pdesc{font-size:9.5px;color:var(--dim)}

/* ── 카드 ── */
.card{background:#fff;border:1px solid var(--bd);border-radius:9px;padding:12px 14px;margin-bottom:9px}
.card .rh{font-size:11px;font-weight:700;color:var(--ink);margin-bottom:8px}
.card .rsub{font-size:9.5px;color:var(--dim)}

/* ── 필드 힌트 밴드 ── */
.band{border:1px solid var(--bd);border-radius:9px;background:var(--wash);
  padding:9px 10px;margin-bottom:10px}
.bandhead{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.blab{min-width:84px;display:flex;flex-direction:column;gap:1px}
.blab .t{font-size:10px;font-weight:700;color:var(--ink);letter-spacing:.01em}
.blab .s{font-family:var(--mono);font-size:7.5px;color:var(--dim)}
.strip{display:flex;gap:7px;overflow-x:auto;padding-bottom:6px;scrollbar-width:thin}
.strip::-webkit-scrollbar{height:4px}
.strip::-webkit-scrollbar-thumb{background:#d5dbe4;border-radius:9px}
.fcard{flex:0 0 190px;width:190px;height:96px;border:1px solid var(--bd);
  border-radius:8px;background:#fff;padding:7px 9px;display:flex;flex-direction:column;
  overflow:hidden;box-sizing:border-box}
.fcard .fct{display:flex;align-items:baseline;justify-content:space-between;gap:6px;
  padding-bottom:5px;border-bottom:1px solid var(--bd2)}
.fcard .fcl{font-size:9.5px;font-weight:600;color:var(--ink);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.fcard .fck{font-family:var(--mono);font-size:7px;color:var(--dim);white-space:nowrap}
.fcard .fcv{display:flex;flex-wrap:wrap;gap:4px;align-content:flex-start;
  margin-top:6px;overflow-y:auto;flex:1}
.fcard .fcv::-webkit-scrollbar{width:4px}
.fcard .fcv::-webkit-scrollbar-thumb{background:#dde2ea;border-radius:9px}
.vchip{font-family:var(--mono);font-size:8px;color:var(--ink2);background:var(--wash);
  border:1px solid var(--bd2);border-radius:4px;padding:2px 5px;white-space:nowrap}
.vchip.bin{background:var(--prisoft);border-color:var(--priline);color:var(--pri2)}
.faxis{margin-top:9px;flex:1;display:flex;flex-direction:column;justify-content:center;gap:7px}
.faxis .ftr{height:3px;border-radius:9px;background:linear-gradient(90deg,#d9ddf1,#eceefb,#d9ddf1);
  position:relative}
.faxis .ftr i{position:absolute;top:-2.5px;width:1px;height:8px;background:var(--priline)}
.faxis .fql{display:flex;justify-content:space-between;font-family:var(--mono);
  font-size:7.5px;color:var(--mid)}
.faxis .fql b{color:var(--ink2);font-weight:600}

/* ── 도넛 ── */
.donutwrap{display:flex;align-items:center;gap:8px;justify-content:flex-end}
.donutwrap .dt{display:flex;flex-direction:column;line-height:1.25;text-align:right}
.donutwrap .dt b{font-family:var(--mono);font-size:10px;color:var(--ink)}
.donutwrap .dt span{font-size:8px;color:var(--dim)}

/* ── 대화 ── */
.thread{display:flex;flex-direction:column;gap:9px}
.msg{display:flex;gap:8px;align-items:flex-start}
.msg .av{width:19px;height:19px;border-radius:5px;flex:0 0 19px;display:flex;
  align-items:center;justify-content:center;font-family:var(--mono);font-size:8px;font-weight:600}
.msg.u .av{background:var(--wash);border:1px solid var(--bd);color:var(--mid)}
.msg.a .av{background:var(--pri);color:#fff}
.bub{flex:1;min-width:0}
.bub .q{font-size:11.5px;color:var(--ink);line-height:1.55;word-break:break-word}
.bub .qmeta{font-family:var(--mono);font-size:7.5px;color:var(--dim);margin-top:3px}
.anscode{background:#0f1729;border-radius:7px;padding:9px 11px;margin-top:6px;
  font-family:var(--mono);font-size:9px;line-height:1.6;color:#c8d2e4;
  white-space:pre-wrap;word-break:break-word;overflow-x:auto}
.anscode .cm{color:#6b7891}
.anscode .kw{color:#a5b4fc}
.res{display:flex;align-items:baseline;gap:8px;margin-top:6px;padding:7px 10px;
  border:1px solid var(--sucline);background:var(--sucsoft);border-radius:7px}
.res .rk{font-size:9px;color:var(--mid)}
.res .rn{font-family:var(--mono);font-size:14px;font-weight:600;color:var(--suc)}
.res .rt{margin-left:auto;font-family:var(--mono);font-size:7.5px;color:var(--dim)}
.warn{border:1px solid var(--danline);background:var(--dansoft);color:#a32a3f;
  border-radius:7px;padding:8px 10px;font-size:10px;margin-top:6px}
.hintline{border:1px solid var(--wrnline);background:var(--wrnsoft);color:#8a5f11;
  border-radius:7px;padding:7px 10px;font-size:9.5px;margin-top:6px}
.empty{border:1px dashed var(--bd);border-radius:9px;padding:26px 14px;text-align:center;
  color:var(--dim);font-size:10px;background:var(--wash)}

/* ── 정책 띠 ── */
.reqline{display:flex;align-items:center;gap:7px;font-size:9.5px;color:var(--dim);
  border:1px solid var(--bd2);background:var(--wash);border-radius:6px;padding:6px 10px}
.reqline b{font-family:var(--mono);font-size:10px;font-weight:600;color:var(--ink2)}
.reqline .vl{width:1px;height:8px;background:var(--bd);margin:0 2px}
.reqdiv{height:1px;background:var(--bd2);margin:12px 0 10px}
.row{display:flex;align-items:center;gap:10px}
.row.between{justify-content:space-between}
.grow{flex:1;min-width:0}
.mono{font-family:var(--mono)}
.dim{color:var(--dim)}
.tag{font-family:var(--mono);font-size:7.5px;padding:2px 6px;border-radius:4px;
  border:1px solid var(--bd);color:var(--mid);background:var(--wash)}
.tag.p{background:var(--wrnsoft);border-color:var(--wrnline);color:#8a5f11}
.tag.a{background:var(--sucsoft);border-color:var(--sucline);color:#0b7a5d}
.tag.r{background:var(--dansoft);border-color:var(--danline);color:#a32a3f}

/* ── Streamlit 위젯을 시안 톤으로 ── */
[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] p{
  font-family:var(--mono) !important;font-size:8px !important;letter-spacing:.1em;
  color:var(--dim) !important;text-transform:uppercase}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]{border-radius:6px}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p{font-size:11px}
[data-testid="stSidebar"] a[aria-current="page"]{background:var(--prisoft)}
[data-testid="stSidebar"] a[aria-current="page"] p{color:var(--pri2) !important;font-weight:600}
.stButton>button{border-radius:6px;border:1px solid var(--bd);background:#fff;
  color:var(--ink2);font-size:10.5px;font-weight:500;padding:5px 12px;min-height:30px}
.stButton>button:hover{border-color:var(--priline);color:var(--pri2);background:var(--prisoft)}
.stButton>button[kind="primary"]{background:var(--pri);border-color:var(--pri);color:#fff}
.stButton>button[kind="primary"]:hover{background:var(--pri2);border-color:var(--pri2);color:#fff}
[data-testid="stSelectbox"] div[data-baseweb="select"]>div{
  border-radius:7px;border-color:var(--bd);min-height:30px;font-size:11.5px;font-weight:600;
  color:var(--ink)}
[data-testid="stSelectbox"] label,[data-testid="stRadio"] label,[data-testid="stTextArea"] label,
[data-testid="stTextInput"] label{font-size:9.5px !important;color:var(--dim) !important}
[data-testid="stTextArea"] textarea{border-radius:6px;border-color:var(--bd);
  font-size:11px;background:#fcfdff;color:var(--mid)}
[data-testid="stChatInput"]{border-radius:9px}
[data-testid="stChatInput"] textarea{font-size:11.5px}
[data-testid="stChatInputContainer"]{border-color:var(--bd);border-radius:9px}
div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:9px}
</style>
"""


def inject() -> None:
    """전역 CSS 1회 주입."""
    st.markdown(_CSS, unsafe_allow_html=True)


def topbar(page: str, role: str) -> str:
    """상단 바. role 은 'Workspace' 또는 'Admin'."""
    return (
        '<div class="topbar"><div class="mark">D</div>'
        '<div class="who"><b>DPilot</b><span>DIFFERENTIAL PRIVACY WORKSPACE</span></div>'
        '<div class="dv"></div>'
        f'<div class="crumb"><i>{role}</i> / <b>{page}</b></div></div>'
    )


def page_head(title: str, desc: str) -> str:
    return f'<div class="phead"><span class="ptitle">{title}</span><span class="pdesc">{desc}</span></div>'


def donut(ratio: float, label: str = "", sub: str = "", size: int = 44) -> str:
    """ε 예산 소진율 도넛(SVG)."""
    ratio = max(0.0, min(1.0, float(ratio)))
    r = (size - 7) / 2
    c = size / 2
    circ = 2 * math.pi * r
    dash = circ * ratio
    color = "#0d9f7a" if ratio < 0.6 else ("#c98a1a" if ratio < 0.9 else "#e0455f")
    return f'''
<div class="donutwrap">
  <div class="dt"><b>{label}</b><span>{sub}</span></div>
  <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
    <circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="#e4e8ee" stroke-width="5"/>
    <circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{color}" stroke-width="5"
      stroke-linecap="round" stroke-dasharray="{dash:.2f} {circ - dash:.2f}"
      transform="rotate(-90 {c} {c})"/>
    <text x="{c}" y="{c + 3.2}" text-anchor="middle" font-size="9" font-weight="700"
      font-family="IBM Plex Mono,monospace" fill="#101828">{ratio * 100:.0f}%</text>
  </svg>
</div>'''


def field_card(f: dict) -> str:
    """필드 힌트 카드 1장.

    kind: categorical(값 종류) / filter(Q1·Q2·Q3) / pattern(이진 결과 2종)
    금지: 건수·비율·최소·최대·평균 — payload 에 애초에 담지 않는다.
    """
    kind = f.get("kind", "categorical")
    label = f.get("label", f.get("col", ""))
    meta = {"categorical": "cat", "filter": "num", "pattern": "bin"}.get(kind, kind)

    if kind == "filter":
        q = f.get("quartiles") or [None, None, None]
        ticks = "".join('<i style="left:%d%%"></i>' % p for p in (0, 50, 100))
        cells = "".join(
            f'<span>{n} <b>{_num(v)}</b></span>'
            for n, v in zip(("Q1", "Q2", "Q3"), q)
        )
        body = (f'<div class="faxis"><div class="ftr">{ticks}</div>'
                f'<div class="fql">{cells}</div></div>')
    else:
        vals = f.get("values") or []
        chips = "".join(
            f'<span class="vchip{" bin" if kind == "pattern" else ""}">{v.get("t", "")}</span>'
            for v in vals
        )
        body = f'<div class="fcv">{chips}</div>'

    return (f'<div class="fcard"><div class="fct">'
            f'<span class="fcl">{label}</span><span class="fck">{meta} · {f.get("n", len(f.get("values") or []))}</span>'
            f'</div>{body}</div>')


def strip(cards: list[str]) -> str:
    return '<div class="strip">' + "".join(cards) + "</div>"


def band(label: str, sub: str, cards: list[str]) -> str:
    """필드 힌트 밴드 (라벨 + 가로 스트립)."""
    return (f'<div class="band"><div class="bandhead">'
            f'<div class="blab"><span class="t">{label}</span>'
            f'<span class="s">{sub}</span></div></div>'
            f'{strip(cards)}</div>')


def bubble_user(text: str, meta: str = "") -> str:
    m = f'<div class="qmeta">{meta}</div>' if meta else ""
    return (f'<div class="msg u"><div class="av">U</div><div class="bub">'
            f'<div class="q">{_esc(text)}</div>{m}</div></div>')


def bubble_agent(code: str | None, answer: str, *, label: str = "결과",
                 eps: float | None = None, note: str = "") -> str:
    """에이전트 응답 말풍선. code 는 하이라이트된 <pre> 로, answer 는 결과 띠로."""
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
    """`리스크 레벨 3 | 총 ε 6.00 | …` 형태의 한 줄 띠."""
    out = []
    for i, (k, v) in enumerate(pairs):
        if i:
            out.append('<span class="vl"></span>')
        out.append(f'{k} <b>{v}</b>')
    return '<div class="reqline">' + "".join(out) + "</div>"


# ── 내부 유틸 ───────────────────────────────────────────

def _num(v) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{f:,.0f}" if abs(f) >= 1000 else (f"{f:.1f}".rstrip("0").rstrip("."))


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


_KEYWORDS = ("import", "from", "def", "return", "for", "in", "if", "else",
             "df", "and", "or", "not", "groupby", "round", "median", "mean")


def _hl(code: str) -> str:
    """가벼운 코드 하이라이트 — 주석/문자열 없이 키워드만 색을 준다."""
    import re
    out = []
    for ln in str(code).split("\n"):
        if ln.strip().startswith("#"):
            out.append(f'<span class="cm">{_esc(ln)}</span>')
            continue
        parts = re.split(r"(\b[A-Za-z_]+\b)", ln)
        buf = []
        for p in parts:
            if p in _KEYWORDS:
                buf.append(f'<span class="kw">{_esc(p)}</span>')
            else:
                buf.append(_esc(p))
        out.append("".join(buf))
    return "\n".join(out)
