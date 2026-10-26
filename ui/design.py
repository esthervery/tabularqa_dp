"""디자인 레이어 — Streamlit 위에 얹는 시각 스타일 (demo 브랜치 · 원래 시안 복원판).

원래 시안(v3)의 톤앤매너를 demo 브랜치 구조에 다시 입힌다.
    · 팔레트 : Indigo #6366f1 (primary) / Emerald #10b981 / Rose #f43f5e / Amber #f59e0b
    · 브랜드 : ε 그라디언트 마크 (Indigo → Violet)
    · 카드   : 흰 배경 + #e2e8f0 테두리 + 12px 라운드 + 얕은 그림자
    · 타이포 : Pretendard (한글 가독성) + IBM Plex Mono (수치·코드)

지키는 원칙 (demo 브랜치에서 이어받음)
    1) 오버레이 금지 — position:fixed/absolute 로 띄우는 요소를 만들지 않는다.
    2) 간격은 넉넉하게 — Streamlit 기본 gap 유지, 카드 안쪽 여백으로 위계를 만든다.

다른 페이지(budget_request · history · budget_admin · privacy_analysis)가 쓰는
함수 이름과 시그니처는 모두 그대로 유지한다.

주요 API
    inject()                       전역 CSS 주입 (모든 페이지 상단에서 1회)
    page_hero(title, desc, right)  페이지 제목 블록 (콘솔용, 큰 제목)
    page_head(title, desc)         작은 페이지 제목 (기존 페이지 호환)
    card_head(title, sub)          카드 안쪽 제목 줄
    login_hero()                   로그인 좌측 소개 카드 HTML
    donut_card(...)                큰 도넛 KPI 카드 (콘솔 ε 예산)
    donut(...)                     작은 인라인 도넛 (기존 페이지 호환)
    pill(label, tone)              색상 뱃지
    field_card / strip / band      필드 힌트 카드 스트립
    bubble_user / bubble_agent     대화 말풍선
    warn / empty / line            보조 블록
"""
from __future__ import annotations

import math
import re
import html as _h

import streamlit as st

TOKEN = {
    "pri": "#6366f1", "pri2": "#4338ca", "prisoft": "#eef2ff", "priline": "#c7d2fe",
    "suc": "#10b981", "suc2": "#047857", "sucsoft": "#ecfdf5", "sucline": "#a7f3d0",
    "dan": "#f43f5e", "dan2": "#be123c", "dansoft": "#fff1f2", "danline": "#fecdd3",
    "wrn": "#f59e0b", "wrn2": "#b45309", "wrnsoft": "#fffbeb", "wrnline": "#fde68a",
    "ink": "#0f172a", "ink2": "#334155", "mid": "#64748b", "dim": "#94a3b8",
    "bd": "#e2e8f0", "bd2": "#f1f5f9", "wash": "#f8fafc",
}


_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root{
  --pri:#6366f1; --pri2:#4338ca; --prisoft:#eef2ff; --priline:#c7d2fe;
  --suc:#10b981; --suc2:#047857; --sucsoft:#ecfdf5; --sucline:#a7f3d0;
  --dan:#f43f5e; --dan2:#be123c; --dansoft:#fff1f2; --danline:#fecdd3;
  --wrn:#f59e0b; --wrn2:#b45309; --wrnsoft:#fffbeb; --wrnline:#fde68a;
  --ink:#0f172a; --ink2:#334155; --mid:#64748b; --dim:#94a3b8;
  --bd:#e2e8f0; --bd2:#f1f5f9; --wash:#f8fafc;
  --sans:'Pretendard Variable',Pretendard,-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
  --mono:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
  --shadow:0 1px 2px rgba(15,23,42,.04);
}

/* ══ 골격 ═══════════════════════════════════════════════ */
html,body,[class*="st-"],.stApp,button,input,textarea,select{
  font-family:var(--sans) !important; -webkit-font-smoothing:antialiased;
}
.stApp{background:#fff}
p,li,span,div,label{color:var(--ink2)}
strong,b{color:var(--ink);font-weight:600}
code{font-family:var(--mono) !important;font-size:.88em;background:var(--wash);
  border:1px solid var(--bd2);padding:1px 6px;border-radius:5px;color:var(--ink2)}

/* 네이티브 사이드바·툴바는 쓰지 않는다 */
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"]{display:none !important}
[data-testid="stHeader"]{background:transparent}
[data-testid="stToolbar"],[data-testid="stAppDeployButton"],
[data-testid="stDecoration"],[data-testid="stStatusWidget"],#MainMenu,footer{
  display:none !important;
}
[data-testid="stMainBlockContainer"],.block-container{
  padding:.55rem 2.4rem 1rem !important; max-width:1440px !important;
}

/* ══ 타이포 ═════════════════════════════════════════════ */
h1,h2,h3,h4{color:var(--ink) !important;letter-spacing:-.02em;font-weight:700}
h1{font-size:1.5rem !important} h2{font-size:1.15rem !important}
h3{font-size:1rem !important}   h4{font-size:.9rem !important}
[data-testid="stMarkdownContainer"] p{font-size:13.5px;line-height:1.65;letter-spacing:-.005em}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p{
  font-size:12px !important;color:var(--mid) !important
}

/* ══ 상단 네비게이션 ═══════════════════════════════════ */
.navbrand{display:flex;align-items:center;gap:10px;padding:0}
.navbrand .mark{width:34px;height:34px;border-radius:9px;
  background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:#fff;
  display:flex;align-items:center;justify-content:center;
  font-family:"Times New Roman",Georgia,serif;font-style:italic;font-size:18px;font-weight:700;
  flex:0 0 34px;box-shadow:0 6px 16px -6px rgba(99,102,241,.55)}
.navbrand .who{display:flex;flex-direction:column;line-height:1.2}
.navbrand .who b{font-size:15px;font-weight:700;color:var(--ink);letter-spacing:-.02em}
.navbrand .who span{font-size:10.5px;letter-spacing:.04em;color:var(--mid);margin-top:2px}

/* 탭 — 텍스트 링크. 선택 = 볼드 + indigo 글자색 (밑줄 없음).
   탭·로그아웃을 모두 같은 36px 상자 + flex 중앙 정렬로 맞춰 글씨 높이를 통일한다.
   div 를 붙여 뒤쪽의 공통 버튼 규칙보다 우선순위를 높인다. */
.stApp div[class*="st-key-nav_"] button{
  height:36px !important; min-height:36px !important;
  padding:0 10px !important; margin:0 !important;
  border:none !important; background:transparent !important;
  box-shadow:none !important; border-radius:8px !important;
  display:inline-flex !important; align-items:center !important; justify-content:center !important;
  color:var(--mid) !important; font-size:14px !important; font-weight:500 !important;
  line-height:1 !important; white-space:nowrap; letter-spacing:-.012em;
  transition:color .15s;
}
.stApp div[class*="st-key-nav_"] button p,
.stApp div[class*="st-key-nav_"] button div{
  margin:0 !important; line-height:1 !important; color:inherit !important;
  font-size:inherit !important; font-weight:inherit !important;
}
.stApp div[class*="st-key-nav_"] button:hover,
.stApp div[class*="st-key-nav_"] button:focus,
.stApp div[class*="st-key-nav_"] button:active{
  color:var(--ink) !important; background:transparent !important; box-shadow:none !important;
}
/* 현재 페이지 */
.stApp div[class*="st-key-nav_on_"] button,
.stApp div[class*="st-key-nav_on_"] button:hover{
  color:var(--pri2) !important; font-weight:700 !important;
}
/* 로그아웃 — 탭과 달리 윤곽선이 있는 작은 버튼 */
.stApp div.st-key-nav_logout.st-key-nav_logout button{
  border:1px solid var(--bd) !important;
  border-radius:8px !important;
  background:#fff !important;
  min-height:32px !important; height:32px !important;
  padding:0 14px !important;
  color:var(--ink2) !important;
  box-shadow:none !important;
}
.stApp div.st-key-nav_logout.st-key-nav_logout button:hover{
  border-color:var(--dan2) !important;
  color:var(--dan2) !important;
  background:#fff !important;
}

/* 상단 바 안의 HTML 블록도 같은 36px 기준선 */
.stApp div.st-key-navbar div.navuser{
  height:36px; display:flex; align-items:center; gap:8px; margin:0 !important;
}
.stApp div.st-key-navbar div.navsep{ height:18px; margin:0 6px !important; align-self:center; }
.stApp div.navbrand{ min-height:44px; display:flex; align-items:center; margin:0 !important; }

/* 구분선 — 위아래 여백 축소 */
.stApp div.navrule{ margin:2px 0 0 !important; }

/* 콘솔 ε 예산 링 (큰 도넛) */
.stApp div.bring{ display:flex; align-items:center; gap:12px; }
.bring .bt{ text-align:right; line-height:1.35; }
.bring .bt b{ display:block; font-family:var(--mono); font-size:17px; font-weight:600; color:var(--ink); }
.bring .bt span{ font-size:12px; color:var(--dim); }
.bring svg text{ font-family:var(--mono); font-size:13px; font-weight:600; fill:#1e293b; }

/* 계정 (우측) */
.navuser{display:flex;align-items:center;gap:8px;padding:0 2px 0 6px}
.navuser .av{width:28px;height:28px;border-radius:8px;background:var(--prisoft);
  border:1px solid var(--priline);color:var(--pri2);display:flex;align-items:center;
  justify-content:center;font-family:var(--mono);font-size:10px;font-weight:600;flex:0 0 28px}
.navuser .u{display:flex;flex-direction:column;line-height:1.25;min-width:0}
.navuser .u b{font-size:13px;font-weight:600;color:var(--ink)}
.navuser .u span{font-size:10.5px;color:var(--mid)}

.navwarn{border:1px solid var(--danline);background:var(--dansoft);color:var(--dan2);
  border-radius:10px;padding:10px 13px;font-size:12px;line-height:1.55;margin-top:8px}
.navsep{width:1px;height:20px;background:var(--bd);margin:0 8px;flex:0 0 1px}
.navrule{height:1px;background:var(--bd);margin:14px 0 22px}

/* ══ 버튼 ═══════════════════════════════════════════════ */
.stButton>button,.stFormSubmitButton>button{
  border-radius:9px !important;border:1px solid var(--bd) !important;
  background:#fff !important;color:var(--ink2) !important;
  font-size:13px !important;font-weight:500 !important;
  padding:0.5rem 1rem !important;min-height:38px !important;
  box-shadow:var(--shadow);letter-spacing:-.01em;
  transition:border-color .15s,background .15s,color .15s,box-shadow .15s;
}
.stButton>button:hover,.stFormSubmitButton>button:hover{
  border-color:var(--pri) !important;color:var(--pri) !important;background:#fff !important;
}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{
  background:var(--pri) !important;border-color:var(--pri) !important;color:#fff !important;
  font-weight:600 !important;box-shadow:0 4px 12px -4px rgba(99,102,241,.5);
}
.stButton>button[kind="primary"]:hover,.stFormSubmitButton>button[kind="primary"]:hover{
  background:var(--pri2) !important;border-color:var(--pri2) !important;color:#fff !important;
}




/* ══ 입력 ═══════════════════════════════════════════════ */
[data-testid="stWidgetLabel"] p{font-size:12px !important;font-weight:600 !important;
  color:var(--ink2) !important}
div[data-baseweb="select"]>div{
  border-radius:9px !important;border:1px solid var(--bd) !important;background:#fff !important;
  min-height:42px !important;font-size:14px !important;font-weight:600 !important;
  color:var(--ink) !important;box-shadow:var(--shadow);
}
div[data-baseweb="select"]>div:focus-within{border-color:var(--pri) !important;
  box-shadow:0 0 0 3px rgba(99,102,241,.12) !important}
.stTextInput input,.stTextArea textarea{
  border-radius:9px !important;border:1px solid var(--bd) !important;
  background:#fff !important;font-size:14px !important;color:var(--ink) !important;
}
.stTextInput input:focus,.stTextArea textarea:focus{
  border-color:var(--pri) !important;
  box-shadow:0 0 0 3px rgba(99,102,241,.12) !important;
}
.stTextArea textarea{line-height:1.65 !important;padding:0.65rem 0.8rem !important}

/* 라디오 → 세그먼트 카드 */
[data-testid="stRadio"] [role="radiogroup"]{display:flex !important;flex-wrap:wrap;gap:8px}
[data-testid="stRadio"] [role="radiogroup"]>label{
  flex:1 1 0;min-width:120px;margin:0 !important;display:flex !important;
  align-items:center;justify-content:center;padding:11px 14px !important;
  border:1px solid var(--bd);border-radius:10px;background:#fff;cursor:pointer;
  box-shadow:var(--shadow);transition:border-color .15s,background .15s,box-shadow .15s;
}
[data-testid="stRadio"] [role="radiogroup"]>label:hover{border-color:var(--priline);background:var(--prisoft)}
[data-testid="stRadio"] [role="radiogroup"]>label>div:first-child{display:none !important}
[data-testid="stRadio"] [role="radiogroup"]>label p{
  font-size:13px !important;font-weight:600 !important;color:var(--ink2) !important;margin:0 !important
}
[data-testid="stRadio"] [role="radiogroup"]>label:has(input:checked){
  border-color:var(--pri);background:var(--prisoft);
  box-shadow:inset 0 0 0 1px var(--pri),0 4px 12px -5px rgba(99,102,241,.5);
}
[data-testid="stRadio"] [role="radiogroup"]>label:has(input:checked) p{color:var(--pri2) !important}

/* ══ 탭 (로그인 폼 등) ══════════════════════════════════ */
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--bd)}
.stTabs [data-baseweb="tab"]{padding:8px 14px;border-radius:8px 8px 0 0;
  color:var(--mid);font-weight:500}
.stTabs [aria-selected="true"]{color:var(--pri2) !important;background:var(--prisoft);font-weight:600}
.stTabs [data-baseweb="tab-highlight"]{background-color:var(--pri) !important}

/* ══ 알림 / 컨테이너 ════════════════════════════════════ */
[data-testid="stAlert"]{border-radius:10px !important;padding:0.75rem 0.95rem !important}
[data-testid="stAlert"] p{font-size:12.5px !important;line-height:1.6}
[data-testid="stForm"]{border:none !important;padding:0 !important}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:12px !important;
  border-color:var(--bd) !important;background:#fff}

/* 키를 준 카드 컨테이너 — 안쪽 여백을 넉넉히 */
.st-key-login_card,.st-key-target_card,.st-key-convo{
  border-radius:14px !important;box-shadow:0 1px 3px rgba(15,23,42,.04);
}
.st-key-login_card{padding:24px 26px !important;border-radius:16px !important}
.st-key-target_card{padding:18px 20px !important}
.st-key-convo{padding:18px 20px 14px !important}

/* ══ 로그인 hero ════════════════════════════════════════ */
.lhero{background:linear-gradient(150deg,#eef2ff 0%,#f8fafc 55%,#ecfdf5 120%);
  border:1px solid var(--bd);border-radius:16px;padding:34px 32px}
.lhero .brand{display:flex;align-items:center;gap:10px}
.lhero .brand .mark{width:40px;height:40px;border-radius:10px;
  background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:#fff;
  display:flex;align-items:center;justify-content:center;
  font-family:"Times New Roman",Georgia,serif;font-style:italic;font-size:20px;font-weight:700;
  box-shadow:0 6px 16px -6px rgba(99,102,241,.55)}
.lhero .brand b{display:block;font-size:16px;color:var(--ink)}
.lhero .brand span{display:block;font-size:11px;color:var(--mid);letter-spacing:.03em;margin-top:2px}
.lhero h2{font-size:26px !important;line-height:1.32;margin:22px 0 10px !important;color:var(--ink) !important}
.lhero p.lead{font-size:14px;color:var(--mid);line-height:1.65;margin:0}
.lhero .bl{display:flex;gap:11px;margin-top:16px;align-items:flex-start}
.lhero .bl .n{flex:0 0 24px;width:24px;height:24px;border-radius:7px;background:#fff;
  border:1px solid var(--bd);display:flex;align-items:center;justify-content:center;
  font-size:12px;color:var(--pri);font-weight:700}
.lhero .bl .t{font-size:13.5px;line-height:1.55;color:var(--ink)}
.lhero .bl .t b{display:block;font-weight:600}
.lhero .bl .t span{color:var(--mid)}
.lfoot{text-align:center;color:var(--dim);font-size:12px;margin-top:28px}

/* ══ 페이지 제목 ════════════════════════════════════════ */
.phero{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin:0 0 18px}
.phero .t{font-size:26px;font-weight:700;color:var(--ink);letter-spacing:-.025em;line-height:1.2}
.phero .d{font-size:13.5px;color:var(--mid);margin-top:5px}
.phero .r{text-align:right}

.phead{display:flex;align-items:baseline;gap:10px;margin:0 0 18px}
.phead .ptitle{font-size:22px;font-weight:700;color:var(--ink);letter-spacing:-.025em}
.phead .pdesc{font-size:13px;color:var(--mid)}

.chead{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin:0 0 12px}
.chead .t{font-size:15px;font-weight:700;color:var(--ink);letter-spacing:-.015em}
.chead .s{font-size:12px;color:var(--mid);margin-top:3px}

/* ══ 뱃지 ═══════════════════════════════════════════════ */
.pill{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;
  font-size:11.5px;font-weight:600;border:1px solid transparent;white-space:nowrap}
.pill::before{content:"";width:6px;height:6px;border-radius:999px;background:currentColor}
.pill.primary{background:var(--prisoft);color:var(--pri2);border-color:var(--priline)}
.pill.success{background:var(--sucsoft);color:var(--suc2);border-color:var(--sucline)}
.pill.danger {background:var(--dansoft);color:var(--dan2);border-color:var(--danline)}
.pill.warning{background:var(--wrnsoft);color:var(--wrn2);border-color:var(--wrnline)}
.pill.muted  {background:var(--bd2);color:var(--mid);border-color:var(--bd)}

/* ══ KPI 도넛 카드 ═════════════════════════════════════ */
.kpi{display:flex;align-items:center;gap:16px;padding:16px 18px;border:1px solid var(--bd);
  border-radius:14px;background:#fff;box-shadow:0 1px 3px rgba(15,23,42,.04);margin-bottom:10px}
.kpi .m .l{font-size:11px;color:var(--mid);text-transform:uppercase;letter-spacing:.06em;font-weight:700}
.kpi .m .v{font-family:var(--mono);font-size:22px;font-weight:600;color:var(--ink);margin-top:3px}
.kpi .m .v span{font-size:13px;color:var(--mid);font-weight:500}
.kpi .m .s{font-size:12px;color:var(--mid);margin-top:3px}

/* 작은 인라인 도넛 (기존 페이지 호환) */
.donutwrap{display:flex;align-items:center;gap:10px;justify-content:flex-end}
.donutwrap .dt{display:flex;flex-direction:column;line-height:1.35;text-align:right}
.donutwrap .dt b{font-family:var(--mono);font-size:13px;color:var(--ink);font-weight:600}
.donutwrap .dt span{font-size:11px;color:var(--mid)}

/* ══ 필드 힌트 밴드 ═════════════════════════════════════ */
.band{border:1px solid var(--bd);border-radius:14px;background:var(--wash);
  padding:16px 18px 10px;margin:4px 0 18px}
.bandhead{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
.blab{display:flex;align-items:baseline;gap:10px}
.blab .t{font-size:15px;font-weight:700;color:var(--ink);letter-spacing:-.015em}
.blab .s{font-size:12px;color:var(--mid)}
.bsafe{font-size:11px;font-weight:600;color:var(--suc2);background:var(--sucsoft);
  border:1px solid var(--sucline);border-radius:999px;padding:3px 10px;white-space:nowrap}
.strip{display:flex;gap:10px;overflow-x:auto;padding-bottom:8px;scrollbar-width:thin}
.strip::-webkit-scrollbar{height:6px}
.strip::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:9px}
.fcard{flex:0 0 210px;width:210px;height:118px;border:1px solid var(--bd);border-radius:12px;
  background:#fff;padding:11px 13px;display:flex;flex-direction:column;overflow:hidden;
  box-sizing:border-box;box-shadow:var(--shadow);transition:border-color .15s,box-shadow .15s}
.fcard:hover{border-color:var(--priline);box-shadow:0 6px 16px -10px rgba(99,102,241,.45)}
.fcard .fct{display:flex;align-items:baseline;justify-content:space-between;gap:6px;
  padding-bottom:8px;border-bottom:1px solid var(--bd2)}
.fcard .fcl{font-size:13px;font-weight:600;color:var(--ink);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.fcard .fck{font-family:var(--mono);font-size:10px;color:var(--dim);white-space:nowrap}
.fcard .fcv{display:flex;flex-wrap:wrap;gap:5px;align-content:flex-start;margin-top:9px;
  overflow-y:auto;flex:1}
.fcard .fcv::-webkit-scrollbar{width:4px}
.fcard .fcv::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:9px}
.vchip{font-size:11px;color:var(--ink2);background:var(--wash);
  border:1px solid var(--bd);border-radius:6px;padding:3px 8px;white-space:nowrap}
.vchip.bin{background:var(--prisoft);border-color:var(--priline);color:var(--pri2)}
.faxis{margin-top:12px;flex:1;display:flex;flex-direction:column;justify-content:center;gap:10px}
.faxis .ftr{height:5px;border-radius:9px;position:relative;
  background:linear-gradient(90deg,#c7d2fe,#eef2ff,#c7d2fe)}
.faxis .ftr i{position:absolute;top:-3px;width:1px;height:11px;background:var(--pri)}
.faxis .fql{display:flex;justify-content:space-between;font-family:var(--mono);
  font-size:10px;color:var(--mid)}
.faxis .fql b{color:var(--ink);font-weight:600}

/* ══ 대화 ═══════════════════════════════════════════════ */
.thread{display:flex;flex-direction:column;gap:18px;padding:6px 0 10px}
.msg{display:flex;gap:12px;align-items:flex-start}
.msg .av{width:30px;height:30px;border-radius:9px;flex:0 0 30px;display:flex;
  align-items:center;justify-content:center;font-size:12px;font-weight:700}
.msg.u .av{background:var(--wash);border:1px solid var(--bd);color:var(--mid);font-family:var(--mono)}
.msg.a .av{background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:#fff;
  font-family:"Times New Roman",Georgia,serif;font-style:italic;font-size:15px;
  box-shadow:0 4px 12px -4px rgba(99,102,241,.55)}
.bub{flex:1;min-width:0}
.msg.u .bub .q{display:inline-block;background:var(--prisoft);border:1px solid var(--priline);
  border-radius:4px 12px 12px 12px;padding:9px 13px}
.bub .q{font-size:14px;color:var(--ink);line-height:1.6;word-break:break-word;letter-spacing:-.01em}
.bub .qmeta{font-family:var(--mono);font-size:10px;color:var(--dim);margin-top:5px}
.anscode{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:14px 16px;
  font-family:var(--mono);font-size:12px;line-height:1.7;color:#e2e8f0;
  white-space:pre-wrap;word-break:break-word;overflow-x:auto}
.anscode .cm{color:#64748b}
.anscode .kw{color:#c4b5fd}
.res{display:flex;align-items:baseline;gap:12px;margin-top:10px;padding:12px 16px;
  border:1px solid var(--sucline);background:var(--sucsoft);border-radius:10px}
.res .rk{font-size:12px;color:var(--suc2);font-weight:600}
.res .rn{font-family:var(--mono);font-size:20px;font-weight:600;color:var(--ink)}
.res .rt{margin-left:auto;font-family:var(--mono);font-size:10px;color:var(--suc2)}

/* ── 에이전트 응답 카드 (콘솔) — 단계 줄 / 코드(어두운 배경) / 결과(밝은 배경) ── */
.agcard{border:1px solid var(--bd);border-radius:12px;background:#fff;overflow:hidden;
  box-shadow:var(--shadow)}
.steps{display:flex;flex-wrap:wrap;gap:18px;padding:9px 16px;
  border-bottom:1px solid var(--bd2);background:var(--wash)}
.steps span{font-size:11.5px;color:var(--dim);font-weight:500}
.steps span.on{color:var(--suc2);font-weight:600}
.steps span.now{color:var(--pri2);font-weight:600}
.codeblk{background:#0f172a;padding:12px 0;font-family:var(--mono);font-size:12.5px;
  line-height:1.75;overflow-x:auto}
.codeblk .cl{display:flex;min-width:max-content}
.codeblk .ln{flex:0 0 40px;padding-right:14px;text-align:right;color:#475569;user-select:none}
.codeblk .cc{white-space:pre;color:#e2e8f0;padding-right:18px}
.codeblk .cm{color:#64748b;font-style:italic}
.codeblk .kw{color:#c4b5fd}
.codeblk .str{color:#86efac}
.codeblk .nu{color:#fcd34d}
.codeblk .caret{display:inline-block;width:7px;height:1.05em;margin-left:1px;
  vertical-align:-2px;background:#a5b4fc;animation:dpblink 1s steps(1) infinite}
.codeblk.pend{padding:14px 18px;color:#94a3b8;font-size:12px}
@keyframes dpblink{50%{opacity:0}}
.ares{padding:14px 18px 16px}
.ares .rk{font-size:12px;color:var(--mid);font-weight:600}
.ares .rrow{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-top:4px}
.ares .rv{font-family:var(--mono);font-size:30px;font-weight:600;color:var(--ink);
  letter-spacing:-.02em;line-height:1.15;word-break:break-all}
.ares .rv.multi{font-size:14px;font-weight:500;white-space:pre-wrap;line-height:1.6}
.epsb{font-family:var(--mono);font-size:11.5px;font-weight:600;color:var(--pri2);
  background:var(--prisoft);border:1px solid var(--priline);border-radius:7px;
  padding:3px 9px;white-space:nowrap}

/* ── 채팅 히스토리 카드 ── */
.hcard{border:1px solid var(--bd);border-radius:12px;background:#fff;
  padding:14px 16px 16px;margin-bottom:12px;box-shadow:var(--shadow)}
.hcard .hhead{display:flex;justify-content:space-between;align-items:center;min-height:20px}
.hcard .ht{font-family:var(--mono);font-size:11px;color:var(--dim)}
.hcard .hbad{font-size:11px;font-weight:600;color:var(--dan2);background:var(--dansoft);
  border:1px solid var(--danline);border-radius:7px;padding:2px 8px}
.hcard .hq{margin:6px 0 10px;font-size:14px;font-weight:600;color:var(--ink);line-height:1.5}
.hmsg{padding:12px 16px;background:var(--dansoft);color:var(--dan2);
  font-size:12.5px;line-height:1.65;white-space:pre-wrap}

.warn{border:1px solid var(--danline);background:var(--dansoft);color:var(--dan2);
  border-radius:10px;padding:12px 14px;font-size:13px;line-height:1.6}
.hintline{border:1px solid var(--wrnline);background:var(--wrnsoft);color:var(--wrn2);
  border-radius:10px;padding:10px 13px;font-size:12px;margin-top:10px}
.empty{border:1px dashed var(--bd);border-radius:12px;padding:40px 18px;text-align:center;
  color:var(--mid);font-size:13px;background:var(--wash);margin-bottom:12px}

/* ══ 보조 ═══════════════════════════════════════════════ */
.reqline{display:flex;align-items:center;flex-wrap:wrap;gap:8px;font-size:12px;color:var(--mid);
  border:1px solid var(--bd2);background:var(--wash);border-radius:9px;padding:9px 13px;
  margin:10px 0 0}
.reqline b{font-family:var(--mono);font-size:12.5px;font-weight:600;color:var(--ink)}
.reqline .vl{width:1px;height:11px;background:var(--bd);margin:0 4px}
.reqdiv{height:1px;background:var(--bd);margin:14px 0 14px}
.row{display:flex;align-items:center;gap:12px}
.row.between{justify-content:space-between}
.grow{flex:1;min-width:0}
.mono{font-family:var(--mono)}
.dim{color:var(--dim)}
.tag{font-family:var(--mono);font-size:10px;padding:3px 8px;border-radius:999px;
  border:1px solid var(--bd);color:var(--mid);background:var(--wash)}
.tag.p{background:var(--wrnsoft);border-color:var(--wrnline);color:var(--wrn2)}
.tag.a{background:var(--sucsoft);border-color:var(--sucline);color:var(--suc2)}
.tag.r{background:var(--dansoft);border-color:var(--danline);color:var(--dan2)}

/* ══ 카드 컨테이너 (st.container(border=True, key="card_…")) ══ */
[class*="st-key-card_"]{padding:18px 20px !important;border-radius:14px !important;
  box-shadow:0 1px 3px rgba(15,23,42,.04)}

/* ══ 통계 카드 ══════════════════════════════════════════ */
.stat{border:1px solid var(--bd);border-radius:12px;background:#fff;padding:14px 16px;
  box-shadow:var(--shadow);margin-bottom:10px}
.stat .l{font-size:11px;color:var(--mid);text-transform:uppercase;letter-spacing:.06em;font-weight:700}
.stat .v{font-family:var(--mono);font-size:24px;font-weight:600;color:var(--ink);margin-top:4px}
.stat.p .v{color:var(--wrn2)} .stat.a .v{color:var(--suc2)}
.stat.c .v{color:var(--pri2)} .stat.r .v{color:var(--dan2)}

/* ══ 표 형태 목록 ═══════════════════════════════════════ */
.trow{display:grid;gap:12px;align-items:center;border-bottom:1px solid var(--bd2);
  padding:10px 4px;font-size:12.5px;color:var(--ink2)}
.trow:last-child{border-bottom:none}
.trow.head{font-size:10.5px;color:var(--mid);text-transform:uppercase;letter-spacing:.06em;
  font-weight:700;border-bottom:1px solid var(--bd);padding:4px 4px 8px}
.trow .t{font-family:var(--mono);font-size:11px;color:var(--dim)}
.trow .m{font-family:var(--mono);font-size:12px;color:var(--ink)}
.trow .x{color:var(--mid);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.trow .tt{font-size:13px;font-weight:600;color:var(--ink)}
.trow .ts{font-family:var(--mono);font-size:10.5px;color:var(--dim);display:block;margin-top:2px}
.trow .r{text-align:right}
.cellbar{height:5px;border-radius:9px;background:var(--bd2);overflow:hidden;margin-top:5px}
.cellbar span{display:block;height:100%;border-radius:9px;
  background:linear-gradient(90deg,#c7d2fe,#6366f1)}

/* 콘솔 오른쪽 — 도넛 블록을 버튼과 같은 폭으로: 글자는 왼쪽 끝, 도넛은 오른쪽 끝 */
.stApp .bring{
  display:flex !important;
  align-items:center !important;
  justify-content:space-between !important;
  width:100% !important;
  box-sizing:border-box !important;
  margin:0 0 10px 0 !important;
  padding:0 2px !important;
  gap:10px !important;
}
.stApp .bring svg{flex:0 0 auto}
  

/* ══ 히스토리 카드 ══════════════════════════════════════ */
.hcard{border:1px solid var(--bd);border-radius:12px;background:#fff;padding:14px 16px;
  margin-bottom:10px;box-shadow:var(--shadow)}
.hcard .top{display:flex;justify-content:space-between;align-items:center;gap:10px}
.hcard .tm{font-family:var(--mono);font-size:11px;color:var(--dim)}
.hcard .hq{font-size:14px;font-weight:600;color:var(--ink);margin-top:8px;line-height:1.55}
.hcard .ha{font-size:13px;color:var(--mid);margin-top:6px;line-height:1.6}
.hcard .anscode{margin-top:10px}

/* ── 채팅 히스토리 표 ───────────────────────────── */
/* 표 전체: 테두리 + 둥근 모서리, 행 사이 기본 gap 제거 */
.stApp .st-key-htable{
  gap:0 !important;
  border:1px solid var(--bd) !important;
  border-radius:12px !important;
  overflow:hidden !important;
  background:#fff !important;
}
/* 헤더 줄: 옅은 회색 배경 + 아래 진한 선 */
.stApp .st-key-hhead{
  background:#f8fafc !important;
  border-bottom:1px solid var(--bd) !important;
  padding:10px 16px !important;
}
.stApp .st-key-hhead .hcol{
  font-size:12px !important; font-weight:700 !important;
  color:var(--ink2) !important; letter-spacing:.02em;
}
.stApp .st-key-hhead .hcol.r{ text-align:right; }
/* 데이터 행: 얇은 구분선 + hover 강조 */
.stApp div[class*="st-key-hrow_"]{
  padding:6px 16px !important;
  border-bottom:1px solid #eef0f4 !important;
  transition:background .12s;
}
.stApp div[class*="st-key-hrow_"]:last-child{ border-bottom:none !important; }
.stApp div[class*="st-key-hrow_"]:hover{ background:#fafbff !important; }
/* 셀 텍스트 */
.stApp .hcell{ font-size:13px; color:var(--ink2); }
.stApp .hcell.tm{ font-size:12px; color:var(--dim); font-variant-numeric:tabular-nums; }
.stApp .hcell.q{ font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.stApp .hcell.mono{ font-family:"IBM Plex Mono",monospace; font-size:12px; }
.stApp .hcell.ans{ font-family:"IBM Plex Mono",monospace; font-size:12.5px; }
/* '자세히 보기' 버튼은 오른쪽 끝 정렬 */
.stApp div[class*="st-key-det_"]{ display:flex; justify-content:flex-end; }

/* ══ 콘솔 공간 확보 ═══════════════════════════════════ */
/* 상단 바 — 브랜드·선택칸을 탭과 같은 36px 기준으로 */
.stApp div.navbrand{ min-height:36px !important; }
.stApp .st-key-navleft div[data-baseweb="select"]>div{
  min-height:36px !important; font-size:13.5px !important;
}
/* 상단 바 ↔ 구분선 ↔ 본문 사이: Streamlit 기본 gap(1rem)을 일부 상쇄 */
.stApp div.navrule{ margin:-6px 0 -8px !important; }

/* 필드 힌트 밴드 — 전체적으로 압축 */
.stApp .band{ padding:10px 14px 4px !important; margin:0 0 4px !important; }
.stApp .bandhead{ margin-bottom:8px !important; }
.stApp .blab .t{ font-size:14px !important; }
.stApp .strip{ gap:8px !important; padding-bottom:6px !important; }
.stApp .fcard{ flex:0 0 190px !important; width:190px !important; height:94px !important;
  padding:8px 11px !important; }
.stApp .fcard .fct{ padding-bottom:6px !important; }
.stApp .fcard .fcl{ font-size:12.5px !important; }
.stApp .fcard .fcv{ margin-top:6px !important; gap:4px !important; }
.stApp .vchip{ padding:2px 7px !important; font-size:10.5px !important; }
.stApp .faxis{ margin-top:8px !important; gap:7px !important; }

/* 도넛 위 '통계 대상' 라벨 — 도넛·버튼과 같은 폭, 왼쪽 정렬 */
.stApp .mtarget{ width:100%; box-sizing:border-box; padding:0 2px; margin:0 0 -4px;
  font-size:12px; color:var(--mid); }
.stApp .mtarget b{ margin-left:4px; font-size:13px; font-weight:700; color:var(--ink); }

/* ── 상단 바 왼쪽(브랜드 | 탭) 구분자 ── */
.stApp div.st-key-navleft div.navsep{ height:18px; margin:0 6px !important; align-self:center; }

/* ── 콘솔: 구분선↔필드 힌트(②) 좁게 / 필드 힌트↔대화(③) 넓게 ── */
.stApp .st-key-cband{ margin:-10px 0 14px !important; }
.stApp .st-key-cband .band{ margin:0 !important; }

/* ── 하단 고정 질의창(④): 배경·윗선·그림자로 '고정된 바' 느낌, 아래 여백 축소 ── */
.stApp [data-testid="stBottom"]{
  border-top:1px solid var(--bd);
  box-shadow:0 -8px 18px -14px rgba(15,23,42,.25);
}
.stApp [data-testid="stBottom"] > div,
.stApp [data-testid="stBottomBlockContainer"]{
  background:var(--wash) !important;
}
.stApp [data-testid="stBottomBlockContainer"]{
  padding:12px 2.4rem 14px !important;
  max-width:1440px !important;
}

/* ── 상세 대화상자: 코드가 길면 가로 스크롤 대신 줄바꿈 ─────── */
div[role="dialog"] .codeblk{ white-space:pre-wrap !important; word-break:break-all; }

/* ══ 결재 항목 ══════════════════════════════════════════ */
.decide{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;
  padding-top:4px}
.decide .h{font-size:14px;font-weight:600;color:var(--ink)}
.decide .h code{font-size:12px}
.decide .why{font-size:13px;color:var(--ink2);background:var(--wash);border:1px solid var(--bd2);
  border-radius:9px;padding:9px 12px;margin-top:8px;line-height:1.55}
.decide .id{font-family:var(--mono);font-size:11px;color:var(--dim);white-space:nowrap}

/* 이전 버전 호환용 (본문 topbar 는 더 이상 그리지 않음) */
.topbar{display:none}
.card{background:#fff;border:1px solid var(--bd);border-radius:12px;padding:18px 20px;
  margin:0 0 12px;box-shadow:var(--shadow)}
.card .rh{font-size:15px;font-weight:700;color:var(--ink);margin-bottom:12px}
.card .rsub{font-size:12px;color:var(--mid)}
</style>


"""


def inject() -> None:
    """전역 CSS 주입. 모든 페이지 상단에서 한 번 호출."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ── 제목 블록 ────────────────────────────────────────────

def topbar(page: str, role: str) -> str:
    """(호환용) 브랜드는 상단 네비게이션이 들고 있으므로 빈 문자열."""
    return ""


def page_hero(title: str, desc: str, right_html: str = "") -> str:
    """큰 페이지 제목 블록 (좌: 제목/설명, 우: 보조 정보)."""
    return (f'<div class="phero"><div><div class="t">{title}</div>'
            f'<div class="d">{desc}</div></div>'
            f'<div class="r">{right_html}</div></div>')


def page_head(title: str, desc: str) -> str:
    """작은 페이지 제목 (기존 페이지 호환)."""
    return (f'<div class="phead"><span class="ptitle">{title}</span>'
            f'<span class="pdesc">{desc}</span></div>')


def card_head(title: str, sub: str = "", right_html: str = "") -> str:
    """카드 안쪽 제목 줄."""
    s = f'<div class="s">{sub}</div>' if sub else ""
    return f'<div class="chead"><div><div class="t">{title}</div>{s}</div>{right_html}</div>'


def pill(label: str, tone: str = "muted") -> str:
    """색상 뱃지. tone: primary|success|danger|warning|muted"""
    return f'<span class="pill {tone}">{label}</span>'


def stat(label: str, value, tone: str = "") -> str:
    """작은 통계 카드. tone: p(대기)|a(승인)|c(조정)|r(거절)|''"""
    return f'<div class="stat {tone}"><div class="l">{label}</div><div class="v">{value}</div></div>'


STATUS_PILL = {
    "pending":  ("대기", "warning"),
    "approved": ("승인", "success"),
    "partial":  ("조정", "primary"),
    "rejected": ("거절", "danger"),
}


def status_pill(status: str) -> str:
    """결재 상태 → 색상 뱃지."""
    label, tone = STATUS_PILL.get(status, (status, "muted"))
    return pill(label, tone)


# ── 로그인 hero ──────────────────────────────────────────

def login_hero() -> str:
    """로그인 좌측 소개 카드."""
    return """
<div class="lhero">
  <div class="brand">
    <div class="mark">ε</div>
    <div><b>DPilot</b><span>Differential Privacy Workspace</span></div>
  </div>
  <h2>안전한 경계 안에서<br/>데이터에게 질문하기</h2>
  <p class="lead">분석가는 원본 데이터에 직접 접근하지 않고, LLM 에이전트가 작성·실행한
  코드의 결과만 차분 프라이버시 보호 아래 받아봅니다.</p>
  <div class="bl"><div class="n">1</div><div class="t"><b>자연어 질의</b>
    <span>프라이버시상 안전한 필드 힌트만 보고 통계량을 질문합니다.</span></div></div>
  <div class="bl"><div class="n">2</div><div class="t"><b>ε 예산 원장</b>
    <span>질의마다 소비된 ε 을 데이터셋별 리스크 정책과 함께 추적합니다.</span></div></div>
  <div class="bl"><div class="n">3</div><div class="t"><b>관리자 결재</b>
    <span>예산이 부족하면 사유와 함께 리스크 레벨 상향을 요청합니다.</span></div></div>
</div>
"""


# ── 도넛 ────────────────────────────────────────────────

def _tone_color(ratio: float) -> str:
    return TOKEN["suc"] if ratio < 0.6 else (TOKEN["wrn"] if ratio < 0.9 else TOKEN["dan"])


def donut_card(spent: float, total: float, sub: str = "",
               label: str = "ε 누적 소모", size: int = 84) -> str:
    """큰 도넛 KPI 카드 (콘솔 상단)."""
    total = max(float(total), 1e-9)
    ratio = max(0.0, min(1.0, float(spent) / total))
    r = (size - 12) / 2
    c = size / 2
    circ = 2 * math.pi * r
    dash = circ * ratio
    return f'''<div class="kpi">
  <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
    <circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="#e2e8f0" stroke-width="9"/>
    <circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{_tone_color(ratio)}" stroke-width="9"
      stroke-linecap="round" stroke-dasharray="{dash:.2f} {circ - dash:.2f}"
      transform="rotate(-90 {c} {c})"/>
    <text x="{c}" y="{c + 5}" text-anchor="middle" font-size="16" font-weight="700"
      font-family="IBM Plex Mono,monospace" fill="#0f172a">{ratio * 100:.0f}%</text>
  </svg>
  <div class="m">
    <div class="l">{label}</div>
    <div class="v">{float(spent):.2f} <span>/ {total:.2f} ε</span></div>
    <div class="s">{sub}</div>
  </div></div>'''


def donut(ratio: float, label: str = "", sub: str = "", size: int = 48) -> str:
    """작은 인라인 도넛 (기존 페이지 호환)."""
    ratio = max(0.0, min(1.0, float(ratio)))
    r = (size - 8) / 2
    c = size / 2
    circ = 2 * math.pi * r
    dash = circ * ratio
    return f'''<div class="donutwrap">
  <div class="dt"><b>{label}</b><span>{sub}</span></div>
  <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
    <circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="#e2e8f0" stroke-width="5"/>
    <circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{_tone_color(ratio)}" stroke-width="5"
      stroke-linecap="round" stroke-dasharray="{dash:.2f} {circ - dash:.2f}"
      transform="rotate(-90 {c} {c})"/>
    <text x="{c}" y="{c + 3.4}" text-anchor="middle" font-size="10" font-weight="700"
      font-family="IBM Plex Mono,monospace" fill="#0f172a">{ratio * 100:.0f}%</text>
  </svg></div>'''


# ── 필드 힌트 ────────────────────────────────────────────

def field_card(f: dict) -> str:
    """필드 1개 카드. kind: categorical(값 칩) / filter(사분위 축) / pattern(이진 칩)."""
    kind = f.get("kind", "categorical")
    label = f.get("label", f.get("col", ""))
    meta = {"categorical": "범주형", "filter": "수치 조건", "pattern": "이진"}.get(kind, kind)

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
    """필드 힌트 밴드 (제목 + 안전 뱃지 + 가로 스크롤 카드)."""
    return (f'<div class="band"><div class="bandhead"><div class="blab">'
            f'<span class="t">{label}</span><span class="s">{sub}</span></div>'
            f'<span class="bsafe">🔒 프라이버시 안전 필드만 노출</span></div>'
            f'{strip(cards)}</div>')


# ── 대화 ────────────────────────────────────────────────

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
    return f'<div class="msg a"><div class="av">ε</div><div class="bub">{inner}</div></div>'


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


# ── 내부 유틸 ────────────────────────────────────────────

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


# ── 에이전트 응답 카드 (콘솔 전용) ─────────────────────────
# st.html 로 렌더링한다 (st.markdown 은 빈 줄에서 HTML 블록이 끊겨 태그가 노출됨).

STEPS = ("① 스키마로 프롬프트 구성", "② 선택한 데이터에 대해 실행", "③ 노이즈 주입 후 반환")

_TOK = re.compile(
    r"(?P<cm>#.*$)"
    r"|(?P<str>'[^'\n]*'|\"[^\"\n]*\")"
    r"|(?P<kw>\b(?:def|return|import|from|as|if|elif|else|for|in|while|and|or|not|is|"
    r"None|True|False|lambda|with|try|except)\b)"
    r"|(?P<nu>\b\d+(?:\.\d+)?\b)"
)


def _hl(line: str) -> str:
    """한 줄을 escape + 간단한 하이라이트."""
    out, pos = [], 0
    for m in _TOK.finditer(line):
        out.append(_h.escape(line[pos:m.start()]))
        out.append(f'<span class="{m.lastgroup}">{_h.escape(m.group())}</span>')
        pos = m.end()
    out.append(_h.escape(line[pos:]))
    return "".join(out)


def code_block(code: str | None, *, caret: bool = False) -> str:
    """어두운 배경 + 라인 번호 코드 블록. caret=True 면 마지막 줄 끝에 깜빡이는 커서."""
    text = code or ""
    if not caret:
        text = text.rstrip("\n")
    lines = text.split("\n")
    rows = []
    for i, ln in enumerate(lines):
        body = _hl(ln)
        if caret and i == len(lines) - 1:
            body += '<span class="caret"></span>'
        rows.append(f'<div class="cl"><span class="ln">{i + 1}</span>'
                    f'<span class="cc">{body or "&#8203;"}</span></div>')
    return '<div class="codeblk">' + "".join(rows) + "</div>"


def _fmt_num(v: float) -> str:
    s = f"{v:,.5f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


_FLOAT = re.compile(r"-?\d+\.\d+(?:[eE][-+]?\d+)?")


def fmt_answer(ans) -> str:
    """응답값 표시용 — 소수점 최대 5자리 (끝자리 0 제거, 천 단위 콤마).
    스칼라가 아니면(Series 출력 등) 문자열 속 실수만 골라 같은 규칙으로 바꾼다."""
    s = str(ans).strip()
    try:
        return _fmt_num(float(s))
    except ValueError:
        return _FLOAT.sub(lambda m: _fmt_num(float(m.group())), s)


def steps(done: int) -> str:
    """done = 완료된 단계 수 (0~3). 완료=on(초록), 진행 중=now(indigo)."""
    parts = []
    for i, t in enumerate(STEPS):
        cls = "on" if i < done else ("now" if i == done else "")
        parts.append(f'<span class="{cls}">{t}</span>')
    return '<div class="steps">' + "".join(parts) + "</div>"


def _agent_wrap(inner: str) -> str:
    return ('<div class="msg a"><div class="av">ε</div><div class="bub">'
            f'<div class="agcard">{inner}</div></div></div>')


def agent_card(code: str | None, ans=None, *, label: str = "결과",
               eps: float | None = None, typing: bool = False) -> str:
    """단계 줄 + 코드 블록 + (타이핑이 끝나면) 결과 영역."""
    body = steps(1 if typing else 3) + code_block(code, caret=typing)
    if not typing and ans not in (None, ""):
        v = fmt_answer(ans)
        multi = " multi" if "\n" in v else ""
        badge = (f'<span class="epsb">ε {float(eps):.2f} 소모</span>'
                 if eps is not None else "")
        body += (f'<div class="ares"><div class="rk">{_h.escape(str(label))}</div>'
                 f'<div class="rrow"><div class="rv{multi}">{_h.escape(v)}</div>{badge}</div></div>')
    return _agent_wrap(body)


def agent_pending() -> str:
    """API 응답을 기다리는 동안의 카드."""
    return _agent_wrap(steps(0) + '<div class="codeblk pend">에이전트가 코드를 작성하고 있습니다'
                       '<span class="caret"></span></div>')


def agent_error(msg: str) -> str:
    """오류/차단 메시지 말풍선."""
    return f'<div class="msg a"><div class="av">ε</div><div class="bub">{warn(msg)}</div></div>'

# ── 채팅 히스토리 카드 ──────────────────────────────────
# 콘솔의 응답 카드와 같은 부품(code_block · fmt_answer · .ares · .epsb)을 재사용한다.

_FAIL_PREFIX = re.compile(r"^\[(?:blocked|error)\]\s*")


def history_card(when: str, question: str, code: str, ans: str, *,
                 ok: bool, eps: float, label: str = "결과") -> str:
    """기록 1건 — 시각/질문 + (코드 블록) + (결과 또는 차단·실패 메시지)."""
    bad = '<span class="hbad">차단·실패</span>' if not ok else ""
    head = (f'<div class="hhead"><span class="ht">{_h.escape(when)}</span>{bad}</div>'
            f'<div class="hq">{_h.escape(question)}</div>')

    inner = code_block(code) if code else ""
    if ok and ans:
        v = fmt_answer(ans)
        multi = " multi" if "\n" in v else ""
        inner += (f'<div class="ares"><div class="rk">{_h.escape(str(label))}</div>'
                  f'<div class="rrow"><div class="rv{multi}">{_h.escape(v)}</div>'
                  f'<span class="epsb">ε {eps:.2f} 소모</span></div></div>')
    elif not ok and ans:
        msg = _FAIL_PREFIX.sub("", ans)[:600]
        inner += f'<div class="hmsg">{_h.escape(msg)}</div>'

    body = f'<div class="agcard">{inner}</div>' if inner else ""
    return '<div class="hcard">' + head + body + "</div>"


# ── 콘솔 ε 예산 링 (큰 도넛) ─────────────────────────────
def budget_ring(spent: float, total: float, remain: int, *, size: int = 72) -> str:
    """'0.00 / 2.00 ε · 잔여 20회' + 사용률 링. 80% 이상 쓰면 rose 로 바뀐다."""
    ratio = max(0.0, min(1.0, spent / total if total else 0.0))
    stroke = 8
    r = (size - stroke) / 2
    c = size / 2
    circ = 2 * math.pi * r
    dash = circ * ratio
    tone = "#f43f5e" if ratio >= 0.8 else "#6366f1"
    return (
        f'<div class="bring">'
        f'<div class="bt"><b>{spent:.2f} / {total:.2f} ε</b><span>잔여 {remain}회</span></div>'
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'<circle cx="{c}" cy="{c}" r="{r:.2f}" fill="none" stroke="#e2e8f0" stroke-width="{stroke}"/>'
        f'<circle cx="{c}" cy="{c}" r="{r:.2f}" fill="none" stroke="{tone}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-dasharray="{dash:.2f} {circ - dash:.2f}" '
        f'transform="rotate(-90 {c} {c})"/>'
        f'<text x="{c}" y="{c + 4.5}" text-anchor="middle">{ratio * 100:.0f}%</text>'
        f'</svg></div>'
    )