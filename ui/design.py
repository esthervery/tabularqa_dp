"""디자인 레이어 — Streamlit 위에 얹는 시각 스타일 (demo 브랜치 · 원래 시안 복원판).

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

/* ════════════════════════════════════════════════════════════════
   목차
      0. 디자인 토큰
      1. 공통 · 골격 / 타이포
      2. 공통 · Streamlit 위젯 (버튼 · 입력 · 라디오 · 탭 · 알림 · 카드 컨테이너)
      3. 공통 · 컴포넌트 (제목 · 뱃지 · 안내 블록 · 보조 줄 · 표 · 유틸)
      4. [app.py]                상단 네비게이션
      5. [auth.py]               로그인
      6. [console.py]            질의 콘솔
      7. [console · history]     에이전트 응답 카드 (공용)
      8. [history.py]            채팅 히스토리
      9. [budget_request.py]     예산 신청
     10. [budget_admin.py]       예산 관리
     11. [privacy_analysis.py]   프라이버시 분석
     12. 호환용 — 현재 화면에서 쓰지 않는 함수의 스타일
   ════════════════════════════════════════════════════════════════ */


/* ════════════════════════════════════════════════════════════════
   0. 디자인 토큰
   ════════════════════════════════════════════════════════════════ */
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


/* ════════════════════════════════════════════════════════════════
   1. 공통 · 골격 / 타이포
   ════════════════════════════════════════════════════════════════ */
html,body,[class*="st-"]:not([data-testid="stIconMaterial"]),.stApp,button,input,textarea,select{
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
[data-testid="stToolbar"],[data-testid="stAppDeployButton"],
[data-testid="stDecoration"],[data-testid="stStatusWidget"],#MainMenu,footer{
  display:none !important;
}
/* Streamlit 기본 헤더 — 투명해도 상단 60px 클릭을 가로챈다(로그아웃 먹통 원인) → 완전히 제거 */
.stApp [data-testid="stHeader"]{ display:none !important; }

/* 본문 폭·여백 */
[data-testid="stMainBlockContainer"],.block-container{
  padding:.55rem 2.4rem 1rem !important; max-width:1440px !important;
}

/* 타이포 */
h1,h2,h3,h4{color:var(--ink) !important;letter-spacing:-.02em;font-weight:700}
h1{font-size:1.5rem !important} h2{font-size:1.15rem !important}
h3{font-size:1rem !important}   h4{font-size:.9rem !important}
[data-testid="stMarkdownContainer"] p{font-size:13.5px;line-height:1.65;letter-spacing:-.005em}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p{
  font-size:12px !important;color:var(--mid) !important
}


/* ════════════════════════════════════════════════════════════════
   2. 공통 · Streamlit 위젯
   ════════════════════════════════════════════════════════════════ */

/* ── 버튼 (기본 / primary) ── */
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

/* ── 입력 · 선택 ── */
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

/* ── 라디오 → 세그먼트 카드 (예산 관리 상태 필터 · 예산 신청 레벨) ── */
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

/* ── 탭 (로그인 / 회원가입) ── */
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--bd)}
.stTabs [data-baseweb="tab"]{padding:8px 14px;border-radius:8px 8px 0 0;
  color:var(--mid);font-weight:500}
.stTabs [aria-selected="true"]{color:var(--pri2) !important;background:var(--prisoft);font-weight:600}
.stTabs [data-baseweb="tab-highlight"]{background-color:var(--pri) !important}

/* ── 알림 · 폼 · 테두리 컨테이너 ── */
[data-testid="stAlert"]{border-radius:10px !important;padding:0.75rem 0.95rem !important}
[data-testid="stAlert"] p{font-size:12.5px !important;line-height:1.6}
[data-testid="stForm"]{border:none !important;padding:0 !important}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:12px !important;
  border-color:var(--bd) !important;background:#fff}

/* ── 카드 컨테이너 st.container(border=True, key="card_…")
      card_request · card_myreq · card_queue · card_done · card_matrix · card_confirm ── */
[class*="st-key-card_"]{padding:18px 20px !important;border-radius:14px !important;
  box-shadow:0 1px 3px rgba(15,23,42,.04)}


/* ════════════════════════════════════════════════════════════════
   3. 공통 · 컴포넌트
   ════════════════════════════════════════════════════════════════ */

/* ── 페이지 제목: page_hero() / page_head() ── */
.phero{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin:0 0 18px}
.phero .t{font-size:26px;font-weight:700;color:var(--ink);letter-spacing:-.025em;line-height:1.2}
.phero .d{font-size:13.5px;color:var(--mid);margin-top:5px}
.phero .r{text-align:right}

.phead{display:flex;align-items:baseline;gap:10px;margin:0 0 18px}
.phead .ptitle{font-size:22px;font-weight:700;color:var(--ink);letter-spacing:-.025em}
.phead .pdesc{font-size:13px;color:var(--mid)}

/* ── 카드 안쪽 제목 줄: card_head() ── */
.chead{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin:0 0 12px}
.chead .t{font-size:15px;font-weight:700;color:var(--ink);letter-spacing:-.015em}
.chead .s{font-size:12px;color:var(--mid);margin-top:3px}

/* ── 뱃지: pill() / status_pill() ── */
.pill{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;
  font-size:11.5px;font-weight:600;border:1px solid transparent;white-space:nowrap}
.pill::before{content:"";width:6px;height:6px;border-radius:999px;background:currentColor}
.pill.primary{background:var(--prisoft);color:var(--pri2);border-color:var(--priline)}
.pill.success{background:var(--sucsoft);color:var(--suc2);border-color:var(--sucline)}
.pill.danger {background:var(--dansoft);color:var(--dan2);border-color:var(--danline)}
.pill.warning{background:var(--wrnsoft);color:var(--wrn2);border-color:var(--wrnline)}
.pill.muted  {background:var(--bd2);color:var(--mid);border-color:var(--bd)}

/* ── 안내 블록: warn() / empty() ── */
.warn{border:1px solid var(--danline);background:var(--dansoft);color:var(--dan2);
  border-radius:10px;padding:12px 14px;font-size:13px;line-height:1.6}
.empty{border:1px dashed var(--bd);border-radius:12px;padding:40px 18px;text-align:center;
  color:var(--mid);font-size:13px;background:var(--wash);margin-bottom:12px}

/* ── 보조 줄: line() / 구분선 reqdiv ── */
.reqline{display:flex;align-items:center;flex-wrap:wrap;gap:8px;font-size:12px;color:var(--mid);
  border:1px solid var(--bd2);background:var(--wash);border-radius:9px;padding:9px 13px;
  margin:10px 0 0}
.reqline b{font-family:var(--mono);font-size:12.5px;font-weight:600;color:var(--ink)}
.reqline .vl{width:1px;height:11px;background:var(--bd);margin:0 4px}
.reqdiv{height:1px;background:var(--bd);margin:14px 0 14px}

/* ── HTML 표 trow (예산 신청 이력 · 예산 관리 처리 완료 · 프라이버시 분석 매트릭스/이력) ── */
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

/* ── 유틸 ── */
.grow{flex:1;min-width:0}
.mono{font-family:var(--mono)}
.dim{color:var(--dim)}


/* ════════════════════════════════════════════════════════════════
   4. [app.py] 상단 네비게이션
      왼쪽 navleft: 브랜드 | 탭  /  오른쪽 navbar: 데이터셋 선택 | 계정 · 로그아웃
      모든 요소를 36px 기준선에 맞춘다.
   ════════════════════════════════════════════════════════════════ */

/* ── 브랜드 ── */
.stApp div.navbrand{display:flex;align-items:center;gap:10px;padding:0;
  min-height:36px !important;margin:0 !important}
.navbrand .mark{width:34px;height:34px;border-radius:9px;
  background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:#fff;
  display:flex;align-items:center;justify-content:center;
  font-family:"Times New Roman",Georgia,serif;font-style:italic;font-size:18px;font-weight:700;
  flex:0 0 34px;box-shadow:0 6px 16px -6px rgba(99,102,241,.55)}
.navbrand .who{display:flex;flex-direction:column;line-height:1.2}
.navbrand .who b{font-size:15px;font-weight:700;color:var(--ink);letter-spacing:-.02em}
.navbrand .who span{font-size:10.5px;letter-spacing:.04em;color:var(--mid);margin-top:2px}

/* ── 탭 (key=nav_{i} / 현재 페이지 nav_on_{i}) — 텍스트 링크, 선택 = 볼드 + indigo ── */
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
.stApp div[class*="st-key-nav_on_"] button,
.stApp div[class*="st-key-nav_on_"] button:hover{
  color:var(--pri2) !important; font-weight:700 !important;
}

/* ── 로그아웃 (key=nav_logout) — 탭과 달리 윤곽선이 있는 작은 버튼 ── */
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

/* ── 계정 ── */
.stApp .navuser{display:flex;align-items:center;gap:8px;padding:0 2px 0 6px;
  height:36px;margin:0 !important}
.navuser .av{width:28px;height:28px;border-radius:8px;background:var(--prisoft);
  border:1px solid var(--priline);color:var(--pri2);display:flex;align-items:center;
  justify-content:center;font-family:var(--mono);font-size:10px;font-weight:600;flex:0 0 28px}
.navuser .u{display:flex;flex-direction:column;line-height:1.25;min-width:0}
.navuser .u b{font-size:13px;font-weight:600;color:var(--ink)}
.navuser .u span{font-size:10.5px;color:var(--mid)}

/* ── 세로 구분자 (브랜드|탭, 선택칸|계정) ── */
.stApp .navsep{width:1px;height:18px;background:var(--bd);flex:0 0 1px;
  margin:0 6px !important;align-self:center}

/* ── 상단 바 아래 가로 구분선 — Streamlit 기본 gap(1rem)을 일부 상쇄 ── */
.stApp .navrule{height:1px;background:var(--bd);margin:-6px 0 -8px !important}

/* ── 한 줄 고정 · 반응형 축소 (navtop) ── */
.stApp .st-key-navtop{
  flex-wrap:nowrap !important;
  overflow-x:auto; overflow-y:hidden;      /* 아주 좁을 때만 가로 스크롤 */
  scrollbar-width:none;
}
.stApp .st-key-navtop::-webkit-scrollbar{ display:none; }

/* 왼쪽은 줄어들지 않음, 오른쪽이 남은 폭을 차지하며 줄어듦 */
.stApp .st-key-navleft{ flex:0 0 auto !important; flex-wrap:nowrap !important; }
.stApp .st-key-navbar{ flex:1 1 auto !important; min-width:0 !important; flex-wrap:nowrap !important; }
.stApp .st-key-navbar > *{ flex-shrink:0; }

/* 데이터셋 선택칸 — 150px ~ 340px 사이에서 늘고 줄어듦 */
.stApp .st-key-navbar [data-testid="stElementContainer"]:has([data-baseweb="select"]){
  flex:1 1 340px !important;
  max-width:340px !important;
  min-width:150px !important;
}
.stApp .st-key-navbar div[data-baseweb="select"] > div > div:first-child{
  overflow:hidden; white-space:nowrap; text-overflow:ellipsis;   /* 긴 이름은 … 처리 */
}

/* 단계별 축소 */
@media (max-width:1180px){
  .navbrand .who span{ display:none; }                           /* 부제 숨김 */
  .stApp div[class*="st-key-nav_"] button{ padding:0 6px !important; }
}
@media (max-width:1020px){
  .navuser .u{ display:none; }                                   /* 계정명 숨김, 아바타만 */
  .stApp .navsep{ margin:0 2px !important; }
}

/* ── 페이지 파일 누락 경고 ── */
.navwarn{border:1px solid var(--danline);background:var(--dansoft);color:var(--dan2);
  border-radius:10px;padding:10px 13px;font-size:12px;line-height:1.55;margin-top:8px}


/* ════════════════════════════════════════════════════════════════
   5. [auth.py] 로그인
   ════════════════════════════════════════════════════════════════ */

/* ── 로그인 폼 카드 (key=login_card) ── */
.st-key-login_card{padding:24px 26px !important;border-radius:16px !important;
  box-shadow:0 1px 3px rgba(15,23,42,.04)}

/* ── 좌측 소개 카드: login_hero() ── */
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


/* ════════════════════════════════════════════════════════════════
   6. [console.py] 질의 콘솔
      _band() 구조
        cband (바깥, 테두리 없음)
        └ cbrow (가로 컨테이너)
           ├ cbright (왼쪽, 폭 250)
           │  ├ cbhead  : 통계 대상 ↔ 예산 링크(to_budget)
           │  └ cbring  : 도넛 묶음 카드 (border=True)
           └ cbhint (오른쪽) : 필드 힌트 .band
   ════════════════════════════════════════════════════════════════ */

/* ── 6-1. 밴드 바깥 · 행 높이 ── */
.stApp .st-key-cband{
  margin:-15px 0 0 !important;          /* 아래 여백 14px → 0 */
  padding-bottom:10px !important;       /* (a) 카드 밑선 ↔ 그림자 경계 사이 간격 */
  position:relative; z-index:2;         /* 그림자가 대화 카드에 가려지지 않게 위로 올림 */
  background:#fff;
  box-shadow:0 8px 12px -10px rgba(15,23,42,.18);   /* (b) 아래쪽에만 생기는 옅은 그림자 */
}

/* 대화 스크롤 영역 (key=convo) — 기본 간격 상쇄 + 첫 말풍선 여유 */
.stApp .st-key-convo{
  margin-top:-1rem !important;          /* 기본 간격(1rem)을 정확히 상쇄 → 잘리는 선 = 그림자 경계 */
  padding-top:12px !important;          /* 그림자 경계 ↔ 첫 말풍선 간격 */
}

.stApp .st-key-cband [data-testid="stHorizontalBlock"]{ align-items:stretch !important; }

/* 넘침·스크롤 방지 */
.stApp .st-key-cband,
.stApp .st-key-cbrow,
.stApp .st-key-cbright,
.stApp .st-key-cbhint,
.stApp .st-key-cbring{
  overflow:visible !important;
}

/* ── 6-2. 왼쪽 cbright — 제목 줄은 제 높이, 도넛 카드가 나머지를 채움 ── */
.stApp .st-key-cbright{
  display:flex !important; flex-direction:column !important;
  padding:8px 2px 0 4px !important;    /* 첫 값 = 제목 줄 위 여백 · 셋째 값(아래)은 0 유지 */
  gap:10px !important;                 /* 제목 줄 ↔ 도넛 카드 */
}
.stApp .st-key-cbright > [data-testid="stElementContainer"]{ margin-bottom:0 !important; }
.stApp .st-key-cbright > [data-testid="stVerticalBlock"]{
  background:transparent !important; border:none !important;   /* 테두리는 cbring 에만 */
}
.stApp .st-key-cbright div:has(.st-key-cbring){
  display:flex !important; flex-direction:column !important;
  flex:1 1 auto !important; min-height:0 !important;
}

/* 제목 줄 cbhead — 두 요소 모두 22px 한 줄 상자 */
.stApp .st-key-cbhead{ min-height:22px !important; align-items:center !important; gap:8px !important; }
.stApp .st-key-cbhead .mtarget{
  width:100%; box-sizing:border-box; padding:0 2px;
  margin:0 !important; line-height:22px !important;
  font-size:14px; color:var(--dim); white-space:nowrap;
}
.stApp .st-key-cbhead .mtarget b{ margin-left:5px; font-size:16px; font-weight:700; color:var(--ink); }

/* 예산 신청/관리 텍스트 링크 (key=to_budget) */
.stApp .st-key-to_budget,
.stApp .st-key-to_budget .stButton{ margin:0 !important; display:flex; align-items:center; }
.stApp .st-key-to_budget button{
  height:22px !important; min-height:22px !important; padding:0 !important;
  line-height:22px !important; display:flex !important; align-items:center !important;
  border:none !important; background:transparent !important; box-shadow:none !important;
}
.stApp .st-key-to_budget button p{
  margin:0 !important; line-height:22px !important;
  font-size:13px !important; font-weight:600 !important; color:var(--pri) !important;
  white-space:nowrap;
}
.stApp .st-key-to_budget button:hover p{ color:var(--pri2) !important; text-decoration:underline; }
.stApp .st-key-to_budget button:disabled p{ color:var(--dim) !important; text-decoration:none; }

/* ── 6-3. 도넛 묶음 카드 cbring + budget_meter() ── */
.stApp .st-key-cband .st-key-cbring{
  flex:1 1 auto !important; height:auto !important; box-sizing:border-box !important;
  justify-content:center !important;   /* 카드 안 세로 가운데 */
  align-items:stretch !important;
  background:#fff !important;
  border:1px solid var(--bd) !important;
  border-radius:14px !important;       /* .band 와 같은 반경 */
  box-shadow:none !important;
  padding:14px 16px !important;
}
/* markdown 이 만드는 중간 상자 여백 제거 — 아래로 밀리는 원인 차단 */
.stApp .st-key-cbring [data-testid="stElementContainer"],
.stApp .st-key-cbring [data-testid="stMarkdown"],
.stApp .st-key-cbring [data-testid="stMarkdownContainer"],
.stApp .st-key-cbring [data-testid="stMarkdownContainer"] > div{
  margin:0 !important; padding:0 !important;
}
/* 배치: [도넛] [수치·잔여(왼쪽 정렬)] — 텍스트 밑줄을 도넛 아래쪽에 맞춤 */
.stApp .st-key-cbring .bmeter{
  display:flex !important; width:100%;
  justify-content:center !important;   /* 묶음 전체를 카드 가로 가운데 */
  align-items:flex-end !important;
  gap:16px !important;                 /* 도넛 ↔ 텍스트 간격 */
  margin:0 !important; padding:0 !important;
}
.stApp .st-key-cbring .bm-ring{ order:1 !important; display:grid; place-items:center; flex:0 0 auto; }
.bm-ring > *{grid-area:1 / 1}
.bm-pct{font-size:12px;font-weight:700;color:var(--ink2)}
.stApp .st-key-cbring .bm-txt{
  order:2 !important; display:flex; flex-direction:column;
  align-items:flex-start !important; text-align:left !important;
  margin:0 !important;
  padding-bottom:6px !important;       /* 텍스트 높이 (클수록 위로) */
}
.stApp .st-key-cbring .bm-val{
  font-size:16px !important; font-weight:700; color:var(--ink); line-height:1.2;
  font-variant-numeric:tabular-nums; letter-spacing:-.01em; white-space:nowrap;
}
.bm-eps{font-weight:600;color:var(--mid);margin-left:4px}
.stApp .st-key-cbring .bm-sub{
  font-size:11px !important; color:var(--dim); line-height:1.4; margin-top:2px; white-space:nowrap;
}

/* ── 6-4. 오른쪽 cbhint — 필드 힌트 카드 band() ── */
.stApp .st-key-cbhint{ display:flex !important; flex-direction:column !important; }
/* st.markdown 의 음수 아래 여백 제거 → 카드 실제 높이로 행 높이 계산 (밑선 일치의 핵심) */
.stApp .st-key-cbhint [data-testid="stElementContainer"],
.stApp .st-key-cbhint [data-testid="stMarkdown"],
.stApp .st-key-cbhint [data-testid="stMarkdownContainer"],
.stApp .st-key-cbhint [data-testid="stMarkdownContainer"] > div{
  margin:0 !important;
}
.stApp .st-key-cbhint div:has(.band){
  display:flex !important; flex-direction:column !important;
  flex:1 1 auto !important; min-height:auto !important;
}
.stApp .st-key-cbhint .band{ flex:1 1 auto !important; box-sizing:border-box !important; }

.stApp .band{border:1px solid var(--bd);border-radius:14px;background:var(--wash);
  padding:10px 14px 4px !important;margin:0 !important}
.stApp .bandhead{display:flex;align-items:center;justify-content:space-between;gap:12px;
  margin-bottom:8px !important}
.blab{display:flex;align-items:baseline;gap:10px}
.stApp .blab .t{font-size:14px !important;font-weight:700;color:var(--ink);letter-spacing:-.015em}
.blab .s{font-size:12px;color:var(--mid)}
.bsafe{font-size:11px;font-weight:600;color:var(--suc2);background:var(--sucsoft);
  border:1px solid var(--sucline);border-radius:999px;padding:3px 10px;white-space:nowrap}

.stApp .strip{display:flex;gap:8px !important;overflow-x:auto;padding-bottom:6px !important;
  scrollbar-width:thin}
.strip::-webkit-scrollbar{height:6px}
.strip::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:9px}

/* 필드 카드 field_card() */
.stApp .fcard{flex:0 0 190px !important;width:190px !important;height:94px !important;
  padding:8px 11px !important;border:1px solid var(--bd);border-radius:12px;background:#fff;
  display:flex;flex-direction:column;overflow:hidden;box-sizing:border-box;
  box-shadow:var(--shadow);transition:border-color .15s,box-shadow .15s}
.fcard:hover{border-color:var(--priline);box-shadow:0 6px 16px -10px rgba(99,102,241,.45)}
.stApp .fcard .fct{display:flex;align-items:baseline;justify-content:space-between;gap:6px;
  padding-bottom:6px !important;border-bottom:1px solid var(--bd2)}
.stApp .fcard .fcl{font-size:12.5px !important;font-weight:600;color:var(--ink);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.fcard .fck{font-family:var(--mono);font-size:10px;color:var(--dim);white-space:nowrap}
.stApp .fcard .fcv{display:flex;flex-wrap:wrap;gap:4px !important;align-content:flex-start;
  margin-top:6px !important;overflow-y:auto;flex:1}
.fcard .fcv::-webkit-scrollbar{width:4px}
.fcard .fcv::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:9px}
.stApp .vchip{font-size:10.5px !important;padding:2px 7px !important;color:var(--ink2);
  background:var(--wash);border:1px solid var(--bd);border-radius:6px;white-space:nowrap}
.vchip.bin{background:var(--prisoft);border-color:var(--priline);color:var(--pri2)}
.stApp .faxis{margin-top:8px !important;gap:7px !important;flex:1;display:flex;
  flex-direction:column;justify-content:center}
.faxis .ftr{height:5px;border-radius:9px;position:relative;
  background:linear-gradient(90deg,#c7d2fe,#eef2ff,#c7d2fe)}
.faxis .ftr i{position:absolute;top:-3px;width:1px;height:11px;background:var(--pri)}
.faxis .fql{display:flex;justify-content:space-between;font-family:var(--mono);
  font-size:10px;color:var(--mid)}
.faxis .fql b{color:var(--ink);font-weight:600}

/* ── 6-5. 대화 말풍선: bubble_user() / agent_error() 의 틀 ── */
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

/* ── 6-6. 하단 고정 질의창 (st.bottom) ── */
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


/* ════════════════════════════════════════════════════════════════
   7. [console · history] 에이전트 응답 카드 (공용)
      agent_card() · agent_pending() · history_card() 가 함께 쓴다.
      구성: 단계 줄 / 코드(어두운 배경 + 라인 번호) / 결과(밝은 배경) + ε 배지
   ════════════════════════════════════════════════════════════════ */
.agcard{border:1px solid var(--bd);border-radius:12px;background:#fff;overflow:hidden;
  box-shadow:var(--shadow)}

/* 단계 줄 (콘솔만) */
.steps{display:flex;flex-wrap:wrap;gap:18px;padding:9px 16px;
  border-bottom:1px solid var(--bd2);background:var(--wash)}
.steps span{font-size:11.5px;color:var(--dim);font-weight:500}
.steps span.on{color:var(--suc2);font-weight:600}
.steps span.now{color:var(--pri2);font-weight:600}

/* 코드 블록 code_block() */
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

/* 결과 영역 + ε 배지 */
.ares{padding:14px 18px 16px}
.ares .rk{font-size:12px;color:var(--mid);font-weight:600}
.ares .rrow{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-top:4px}
.ares .rv{font-family:var(--mono);font-size:30px;font-weight:600;color:var(--ink);
  letter-spacing:-.02em;line-height:1.15;word-break:break-all}
.ares .rv.multi{font-size:14px;font-weight:500;white-space:pre-wrap;line-height:1.6}
.epsb{font-family:var(--mono);font-size:11.5px;font-weight:600;color:var(--pri2);
  background:var(--prisoft);border:1px solid var(--priline);border-radius:7px;
  padding:3px 9px;white-space:nowrap}


/* ════════════════════════════════════════════════════════════════
   8. [history.py] 채팅 히스토리
   ════════════════════════════════════════════════════════════════ */

/* ── 8-1. 표 (htable > hhead / hrow_{id}) ── */
.stApp .st-key-htable{
  gap:0 !important;                    /* 행 사이 기본 gap 제거 */
  border:1px solid var(--bd) !important;
  border-radius:12px !important;
  overflow:hidden !important;
  background:#fff !important;
}
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

/* '자세히 보기' (key=det_{id}) — 콘솔 '예산 신청/관리' 링크(to_budget)와 같은 텍스트 링크 */
.stApp div[class*="st-key-det_"],
.stApp div[class*="st-key-det_"] .stButton{
  display:flex; justify-content:flex-start; align-items:center; margin:0 !important;
}
.stApp div[class*="st-key-det_"] button{
  height:22px !important; min-height:22px !important; padding:0 !important;
  line-height:22px !important; display:flex !important; align-items:center !important;
  border:none !important; background:transparent !important; box-shadow:none !important;
}
.stApp div[class*="st-key-det_"] button p{
  margin:0 !important; line-height:22px !important;
  font-size:13px !important; font-weight:600 !important; color:var(--pri) !important;
  white-space:nowrap;
}
.stApp div[class*="st-key-det_"] button:hover p{ color:var(--pri2) !important; text-decoration:underline; }

/* ── 8-2. 상세 대화상자 + history_card() ── */
div[role="dialog"] .codeblk{ white-space:pre-wrap !important; word-break:break-all; }

.hcard{border:1px solid var(--bd);border-radius:12px;background:#fff;padding:14px 16px;
  margin-bottom:10px;box-shadow:var(--shadow)}
.hcard .hhead{display:flex;justify-content:space-between;align-items:center;min-height:20px}
.hcard .ht{font-family:var(--mono);font-size:11px;color:var(--dim)}
.hcard .hbad{font-size:11px;font-weight:600;color:var(--dan2);background:var(--dansoft);
  border:1px solid var(--danline);border-radius:7px;padding:2px 8px}
.hcard .hq{margin:8px 0 10px;font-size:14px;font-weight:600;color:var(--ink);line-height:1.55}
.hmsg{padding:12px 16px;background:var(--dansoft);color:var(--dan2);
  font-size:12.5px;line-height:1.65;white-space:pre-wrap}


/* ════════════════════════════════════════════════════════════════
   9. [budget_request.py] 예산 신청 — 현재 정책 도넛 KPI 카드 donut_card()
   ════════════════════════════════════════════════════════════════ */
.kpi{display:flex;align-items:center;gap:16px;padding:16px 18px;border:1px solid var(--bd);
  border-radius:14px;background:#fff;box-shadow:0 1px 3px rgba(15,23,42,.04);margin-bottom:10px}
.kpi .m .l{font-size:11px;color:var(--mid);text-transform:uppercase;letter-spacing:.06em;font-weight:700}
.kpi .m .v{font-family:var(--mono);font-size:22px;font-weight:600;color:var(--ink);margin-top:3px}
.kpi .m .v span{font-size:13px;color:var(--mid);font-weight:500}
.kpi .m .s{font-size:12px;color:var(--mid);margin-top:3px}


/* ════════════════════════════════════════════════════════════════
   10. [budget_admin.py] 예산 관리
   ════════════════════════════════════════════════════════════════ */

/* ── 상태별 통계 카드 stat() ── */
.stat{border:1px solid var(--bd);border-radius:12px;background:#fff;padding:14px 16px;
  box-shadow:var(--shadow);margin-bottom:10px}
.stat .l{font-size:11px;color:var(--mid);text-transform:uppercase;letter-spacing:.06em;font-weight:700}
.stat .v{font-family:var(--mono);font-size:24px;font-weight:600;color:var(--ink);margin-top:4px}
.stat.p .v{color:var(--wrn2)} .stat.a .v{color:var(--suc2)}
.stat.c .v{color:var(--pri2)} .stat.r .v{color:var(--dan2)}

/* ── 대기 큐 결재 항목 ── */
.decide{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;
  padding-top:4px}
.decide .h{font-size:14px;font-weight:600;color:var(--ink)}
.decide .h code{font-size:12px}
.decide .why{font-size:13px;color:var(--ink2);background:var(--wash);border:1px solid var(--bd2);
  border-radius:9px;padding:9px 12px;margin-top:8px;line-height:1.55}
.decide .id{font-family:var(--mono);font-size:11px;color:var(--dim);white-space:nowrap}


/* ════════════════════════════════════════════════════════════════
   11. [privacy_analysis.py] 프라이버시 분석 — 매트릭스 셀 막대
   ════════════════════════════════════════════════════════════════ */
.cellbar{height:5px;border-radius:9px;background:var(--bd2);overflow:hidden;margin-top:5px}
.cellbar span{display:block;height:100%;border-radius:9px;
  background:linear-gradient(90deg,#c7d2fe,#6366f1)}

  /* ══ 11-x. 프라이버시 분석 — Utility 버튼 · 시뮬레이션 · 적용 정책 표 ══ */
.pa-h{ font-size:11.5px; font-weight:600; color:var(--mid); }
.pa-h.r{ text-align:right; }
.pa-ds .tt{ display:block; font-size:13.5px; font-weight:600; color:var(--ink); }
.pa-ds .ts{ display:block; font-size:11.5px; color:var(--dim); font-family:var(--mono); }
.pa-cell{ text-align:right; }
.pa-cell .v{ font-family:var(--mono); font-size:13px; font-weight:500; color:var(--ink2); }
.pa-cell .bar{ height:6px; border-radius:99px; background:var(--bd2); margin:6px 0 4px; overflow:hidden; }
.pa-cell .bar span{ display:block; height:100%; border-radius:99px; background:var(--priline); }
.pa-cell.on .bar span{ background:var(--pri); }
.pa-cell.on .v{ color:var(--pri2); font-weight:700; }
.pa-cell .k{ font-size:10.5px; color:var(--dim); }

/* Utility 버튼 (열 제목) — 기본 연회색 · hover 보라 테두리 · 선택 보라 바탕 */
.stApp [class*="st-key-pa_ut_"] button,
.stApp [class*="st-key-pa_uton_"] button{
  height:34px !important; min-height:34px !important; border-radius:9px !important;
  border:1px solid var(--bd) !important; background:var(--wash) !important;
  color:var(--ink2) !important; box-shadow:none !important; transition:all .15s ease;
}
.stApp [class*="st-key-pa_ut_"] button p,
.stApp [class*="st-key-pa_uton_"] button p{
  color:inherit !important; font-size:12.5px !important; font-weight:700 !important; letter-spacing:.02em;
}
.stApp [class*="st-key-pa_ut_"] button:hover{
  background:#fff !important; border-color:var(--pri) !important; color:var(--pri2) !important;
}
.stApp [class*="st-key-pa_uton_"] button{
  background:var(--pri) !important; border-color:var(--pri) !important; color:#fff !important;
  box-shadow:0 2px 6px rgba(99,102,241,.28) !important;
}
.stApp .st-key-pa_head{ margin-bottom:-10px !important; }   /* 버튼 줄 ↔ 숫자 줄 간격 */

/* 시뮬레이션 영역 */
.pa-div{ height:1px; background:var(--bd2); margin:6px 0 10px; }
.pa-empty{ height:120px; display:flex; align-items:center; justify-content:center;
  border:1.5px dashed var(--bd); border-radius:12px; background:var(--wash);
  font-size:13px; color:var(--mid); }
.pa-simhead{ display:flex; align-items:baseline; gap:10px; }
.pa-simhead b{ font-size:14px; color:var(--pri2); }
.pa-simhead span{ font-size:12px; color:var(--mid); }
.pa-res{ display:flex; flex-wrap:wrap; gap:6px 22px; padding:10px 14px; border-radius:10px;
  background:var(--wash); font-size:12.5px; color:var(--mid); }
.pa-res b{ margin-left:6px; font-family:var(--mono); font-weight:600; color:var(--ink); }
.pa-res .w b{ color:var(--pri2); }

/* 다시 재생 — 텍스트 링크 */
.stApp .st-key-pa_replay button{
  border:none !important; background:transparent !important; box-shadow:none !important;
  height:auto !important; min-height:0 !important; padding:2px 0 !important; justify-content:flex-end !important;
}
.stApp .st-key-pa_replay button p{ color:var(--pri) !important; font-size:12.5px !important; font-weight:600 !important; }
.stApp .st-key-pa_replay button:hover p{ color:var(--pri2) !important; text-decoration:underline; }

/* 적용 정책 표 */
.trow.on{ background:var(--prisoft); }
.pmode{ display:inline-block; padding:2px 8px; border-radius:99px; font-size:11px; font-weight:600; }
.pmode.m{ background:var(--prisoft); color:var(--pri2); border:1px solid var(--priline); }
.pmode.a{ background:var(--bd2); color:var(--mid); border:1px solid var(--bd); }


/* ════════════════════════════════════════════════════════════════
   12. 호환용 — 현재 화면에서 호출하지 않는 함수의 스타일
       (함수를 지울 때 함께 지워도 된다)
   ════════════════════════════════════════════════════════════════ */
/* budget_ring() — 예전 콘솔 도넛 (지금은 budget_meter() 사용) */
.stApp .bring{
  display:flex !important; align-items:center !important;
  justify-content:space-between !important; width:100% !important;
  box-sizing:border-box !important; margin:0 0 10px 0 !important;
  padding:0 2px !important; gap:10px !important;
}
.stApp .bring svg{flex:0 0 auto}
.bring .bt{ text-align:right; line-height:1.35; }
.bring .bt b{ display:block; font-family:var(--mono); font-size:17px; font-weight:600; color:var(--ink); }
.bring .bt span{ font-size:12px; color:var(--dim); }
.bring svg text{ font-family:var(--mono); font-size:13px; font-weight:600; fill:#1e293b; }

/* donut() — 작은 인라인 도넛 */
.donutwrap{display:flex;align-items:center;gap:10px;justify-content:flex-end}
.donutwrap .dt{display:flex;flex-direction:column;line-height:1.35;text-align:right}
.donutwrap .dt b{font-family:var(--mono);font-size:13px;color:var(--ink);font-weight:600}
.donutwrap .dt span{font-size:11px;color:var(--mid)}

/* bubble_agent() — 예전 응답 말풍선 (지금은 agent_card() 사용) */
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
.hintline{border:1px solid var(--wrnline);background:var(--wrnsoft);color:var(--wrn2);
  border-radius:10px;padding:10px 13px;font-size:12px;margin-top:10px}

/* 이전 버전 레이아웃 조각 */
.thread{display:flex;flex-direction:column;gap:18px;padding:6px 0 10px}
.row{display:flex;align-items:center;gap:12px}
.row.between{justify-content:space-between}
.tag{font-family:var(--mono);font-size:10px;padding:3px 8px;border-radius:999px;
  border:1px solid var(--bd);color:var(--mid);background:var(--wash)}
.tag.p{background:var(--wrnsoft);border-color:var(--wrnline);color:var(--wrn2)}
.tag.a{background:var(--sucsoft);border-color:var(--sucline);color:var(--suc2)}
.tag.r{background:var(--dansoft);border-color:var(--danline);color:var(--dan2)}
.topbar{display:none}
.card{background:#fff;border:1px solid var(--bd);border-radius:12px;padding:18px 20px;
  margin:0 0 12px;box-shadow:var(--shadow)}
.card .rh{font-size:15px;font-weight:700;color:var(--ink);margin-bottom:12px}
.card .rsub{font-size:12px;color:var(--mid)}

/* ════════════════════════════════════════════════════════════════
   10-2. [budget_admin.py] 예산 관리 — 요약 줄 · 표 보조 · 상세 대화상자
         + [history · budget_admin] 페이지 번호 줄
   ════════════════════════════════════════════════════════════════ */
/* 요약 줄 (대기 · 승인 · 거절 · 전체) */
.asum{display:flex;align-items:center;gap:18px;flex-wrap:wrap;
  border:1px solid var(--bd);border-radius:12px;background:var(--wash);
  padding:12px 18px;margin:0 0 4px}
.asum .it{display:flex;align-items:baseline;gap:8px}
.asum .k{font-size:12.5px;font-weight:600;color:var(--mid)}
.asum b{font-size:20px;font-weight:700;color:var(--ink);letter-spacing:-.02em;
  font-variant-numeric:tabular-nums}
.asum .it.p b{color:var(--wrn2)}
.asum .s{font-size:11.5px;color:var(--dim)}
.asum .vl{width:1px;height:18px;background:var(--bd)}

/* 상세 대화상자 — 카드 없이 정의 목록 + 스크롤 표 */
.rqtop{display:flex;align-items:center;gap:10px;margin:0 0 10px}
.rqtop .tm{margin-left:auto;font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.rqdl{display:grid;grid-template-columns:84px 1fr;column-gap:16px;margin:0;
  background:var(--wash);border-radius:10px;padding:4px 16px}
.rqdl dt,.rqdl dd{margin:0;padding:10px 0;border-bottom:1px solid var(--bd2)}
.rqdl dt:nth-last-of-type(1),.rqdl dd:last-of-type{border-bottom:none}
.rqdl dt{font-size:12px;font-weight:600;color:var(--mid)}
.rqdl dd{display:flex;align-items:baseline;flex-wrap:wrap;gap:6px;font-size:14px;color:var(--ink)}
.rqdl dd b{font-weight:700}
.rqdl dd b.up{color:var(--pri2)}
.rqdl .arr{color:var(--dim);margin:0 2px}
.rqdl .dot{color:var(--dim)}
.rqdl .mono{font-family:var(--mono);font-size:13px}
.rqdl .sub{margin-left:8px;font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.rqdl dd.why{display:block;line-height:1.7;white-space:pre-wrap}

/* 질의 기록 — 제목 줄 + 고정 높이 스크롤 표 */
.rqsec{display:flex;align-items:baseline;gap:8px;margin:14px 0 2px;
  font-size:13px;font-weight:700;color:var(--ink)}
.rqsec span{font-size:11.5px;font-weight:500;color:var(--dim)}
.rqnone{font-size:12.5px;color:var(--dim);padding:10px 0}
.stApp .st-key-rqlog{padding:0 !important;border-radius:10px !important}
.rqtbl{width:100%;border-collapse:collapse;font-size:12.5px}
.rqtbl thead th{position:sticky;top:0;z-index:1;background:#f8fafc;text-align:left;
  font-size:11.5px;font-weight:600;color:var(--mid);padding:8px 12px;
  border-bottom:1px solid var(--bd)}
.rqtbl td{padding:8px 12px;border-bottom:1px solid #eef0f4;color:var(--ink2);vertical-align:middle}
.rqtbl tr:last-child td{border-bottom:none}
.rqtbl td.tm{font-family:var(--mono);font-size:11.5px;color:var(--dim);white-space:nowrap}
.rqtbl td.q{max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rqtbl td.mono{font-family:var(--mono);white-space:nowrap}

/* ① 대화상자 제목 크게 */
.stApp [data-testid="stDialog"] h2,
div[role="dialog"] h2{font-size:20px !important;font-weight:700 !important;letter-spacing:-.02em}

/* ⑥ primary 버튼 글자 흰색 — 전역 p{color} 규칙이 버튼 안 <p> 를 덮던 문제 */
.stApp [data-testid="stBaseButton-primary"],
.stApp [data-testid="stBaseButton-primary"] p,
.stApp [data-testid="stBaseButtonPrimary"] p{color:#fff !important}

/* 상세 대화상자 */
.rqhead{display:flex;align-items:center;gap:10px;margin:0 0 14px}
.rqhead .id{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--mid)}
.rqhead .tm{margin-left:auto;font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.rqgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:0 0 14px}
.rqgrid>div{border:1px solid var(--bd);border-radius:10px;background:#fff;padding:10px 12px;
  display:flex;flex-direction:column;gap:3px}
.rqgrid .k,.rqbox .k{font-size:11px;font-weight:600;color:var(--mid);letter-spacing:.02em}
.rqgrid b{font-size:15px;font-weight:700;color:var(--ink)}
.rqgrid b.up{color:var(--pri2)}
.rqgrid .s{font-family:var(--mono);font-size:11px;color:var(--dim)}
.rqbox{border:1px solid var(--bd2);background:var(--wash);border-radius:10px;
  padding:12px 14px;margin:0 0 10px}
.rqbox p{margin:6px 0 0;font-size:13.5px;line-height:1.7;color:var(--ink);white-space:pre-wrap}

/* 페이지 번호 줄 */
.stApp .st-key-hist_page_wrap,.stApp .st-key-adm_page_wrap{margin-top:12px}


/* ════════════════════════════════════════════════════════════════
   11-2. [budget_request.py] 예산 신청 — ε 도넛 카드 · Utility 레벨 카드 버튼
   ════════════════════════════════════════════════════════════════ */
.stApp .st-key-rqhead{ align-items:flex-start !important; }

/* 왼쪽: 신청 대상 — 정책 줄은 글자 길이만큼만 */
.stApp .st-key-rqinfo{ padding-top:2px; }                       /* ① */
.stApp .st-key-rqinfo .reqline{
  display:inline-flex !important; width:auto !important; white-space:nowrap; }
.stApp .st-key-rqinfo .reqline b{
  font-family:var(--sans) !important; letter-spacing:0 !important; font-weight:700 !important; }

/* 도넛 카드 (콘솔 cbring 재사용, 이 페이지에서만 여백 축소) */
.stApp .st-key-card_request .st-key-cbring{
  padding:12px 14px !important; border-radius:14px !important;
  background:#fff !important; box-shadow:none !important; }

/* 넣을 블록 — 1:1 분할 + 양쪽 같은 여백 → 구분선 정가운데 */
.stApp .st-key-rqtop{ gap:0 !important; align-items:stretch !important; }
.stApp .st-key-rqtop .st-key-rqleft,
.stApp .st-key-rqtop .st-key-rqform{ flex:1 1 0 !important; min-width:0 !important; }
.stApp .st-key-rqleft{ padding-right:24px !important; }                /* ② 왼쪽 여백 */
.stApp .st-key-rqform{ padding-left:24px !important;                   /* ② 오른쪽 여백(왼쪽과 같게) */
  border-left:1px solid var(--bd2); }

/* 신청 이력 (카드 안) */
.rqhtitle{ display:flex; align-items:baseline; gap:8px; margin:14px 0 6px;  /* ③ 도넛과 간격 */
  font-size:13px; font-weight:700; color:var(--ink) !important; }
.rqhtitle span{ font-size:11.5px; font-weight:500; color:var(--dim) !important; }
.rqhempty{ font-size:12.5px; color:var(--dim) !important; padding:10px 2px; }
.rqhist{ max-height:168px; overflow-y:auto; }                              /* ④ 스크롤 시작 높이 */
.rqhist .trow.head{ position:sticky; top:0; background:#fff; z-index:1; }
.rqhist .trow .x{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }

/* 제목 + 최고 레벨 안내 배지 */
.rqtitle{ display:flex; align-items:center; gap:10px; margin:0 0 8px;
  font-size:15px; font-weight:700; color:var(--ink) !important; }
.rqtitle .rqnote{ font-size:12px; font-weight:600; padding:2px 10px; border-radius:999px;
  color:var(--wrn2) !important; background:var(--wrnsoft); border:1px solid var(--wrnline); }

/* 레벨 버튼 — 폭: 남은 폭을 5등분하되 최대 ③ */
.stApp .st-key-lvrow div[class*="st-key-lvl_"]{ max-width:132px; }           /* ③ */
.stApp div[class*="st-key-lvl_"] button{
  height:auto !important; min-height:0 !important;
  padding:8px 6px 7px !important;                                            /* ④ */
  border:1px solid var(--bd) !important; border-radius:10px !important;
  background:linear-gradient(180deg,#fff, var(--wash)) !important;
  box-shadow:0 1px 2px rgba(15,23,42,.04) !important;
  transition:border-color .12s, background .12s, box-shadow .12s, transform .12s; }
.stApp div[class*="st-key-lvl_"] button [data-testid="stMarkdownContainer"]{
  display:flex !important; flex-direction:column !important; align-items:center !important;
  gap:1px !important; }                                                       /* ⑤ */
.stApp div[class*="st-key-lvl_"] button p{
  margin:0 !important; line-height:1.2 !important; white-space:nowrap; }
.stApp div[class*="st-key-lvl_"] button p:first-of-type{
  font-size:13.5px !important; font-weight:700 !important; color:var(--ink) !important; }  /* ⑥ */
.stApp div[class*="st-key-lvl_"] button p:last-of-type{
  font-size:11px !important; font-weight:500 !important; color:var(--mid) !important;
  font-family:var(--mono) !important; }

/* 선택 가능 — hover */
.stApp div[class*="st-key-lvl_go_"] button:hover{
  border-color:var(--priline) !important; background:#fff !important;
  box-shadow:0 2px 6px rgba(99,102,241,.12) !important; transform:translateY(-1px); }

/* 선택됨 */
.stApp div[class*="st-key-lvl_on_"] button{
  background:var(--prisoft) !important; border-color:var(--pri) !important;
  box-shadow:inset 0 0 0 1px var(--pri), 0 2px 6px rgba(99,102,241,.15) !important; }
.stApp div[class*="st-key-lvl_on_"] button p:first-of-type{ color:var(--pri2) !important; }
.stApp div[class*="st-key-lvl_on_"] button p:last-of-type{ color:var(--pri) !important; }

/* 현재·하위 레벨 — 점선 + 클릭 불가 */
.stApp div[class*="st-key-lvl_cur_"] button,
.stApp div[class*="st-key-lvl_off_"] button{
  background:transparent !important; border:1px dashed #cbd5e1 !important;
  box-shadow:none !important; opacity:1 !important; cursor:not-allowed !important; }
.stApp div[class*="st-key-lvl_cur_"] button p,
.stApp div[class*="st-key-lvl_off_"] button p{ color:var(--dim) !important; }


/* ── 10-1. 예산 관리 · 상태 필터 탭 (segmented_control key="adm_tab") ── */
.stApp .st-key-adm_tab{ margin:2px 0 12px; }                                     /* ① */
.stApp .st-key-adm_tab button{
  min-height:0 !important; padding:8px 18px !important;                          /* ② */
  background:#fff !important; color:var(--mid) !important; }
.stApp .st-key-adm_tab button p{
  font-size:13.5px !important; font-weight:600 !important; color:inherit !important; }  /* ③ */
.stApp .st-key-adm_tab button:hover{ color:var(--ink) !important; background:var(--wash) !important; }

/* 선택된 탭 — 상태별 색 (탭 순서: 대기 · 승인됨 · 거절됨 · 전체) */
.stApp .st-key-adm_tab button[data-testid$="Active"]{
  --tone:var(--pri); --soft:var(--prisoft);
  background:var(--soft) !important; color:var(--tone) !important;
  border-color:var(--tone) !important; position:relative; z-index:1; }
.stApp .st-key-adm_tab button[data-testid$="Active"] p{ font-weight:700 !important; }
.stApp .st-key-adm_tab button:nth-of-type(1)[data-testid$="Active"]{ --tone:var(--wrn2); --soft:var(--wrnsoft); }
.stApp .st-key-adm_tab button:nth-of-type(2)[data-testid$="Active"]{ --tone:var(--suc2); --soft:var(--sucsoft); }
.stApp .st-key-adm_tab button:nth-of-type(3)[data-testid$="Active"]{ --tone:var(--dan2); --soft:var(--dansoft); }


/* ══ 11-x. 프라이버시 분석 — 1027 수정 ══ */
/* Utility 1~5 (열 제목) — 테두리 있는 작은 버튼 · 오른쪽 정렬 · 선택 = 보라 바탕 */
.stApp div[class*="st-key-pa_ut"] .stButton{ display:flex !important; justify-content:flex-end !important; }
.stApp div[class*="st-key-pa_ut"] .stButton>button{
  width:auto !important; height:26px !important; min-height:26px !important;
  padding:0 10px !important; border-radius:8px !important;
  border:1px solid var(--priline) !important; background:#fff !important;
  box-shadow:none !important; transition:all .15s ease;
}
.stApp div[class*="st-key-pa_ut"] .stButton>button p{
  font-size:12px !important; font-weight:600 !important; color:var(--pri) !important;
}
.stApp div[class*="st-key-pa_ut_"] .stButton>button:hover{
  border-color:var(--pri) !important; background:var(--prisoft) !important;
}
.stApp div[class*="st-key-pa_uton_"] .stButton>button{
  background:var(--pri) !important; border-color:var(--pri) !important;
  box-shadow:0 2px 6px rgba(99,102,241,.25) !important;
}
.stApp div[class*="st-key-pa_uton_"] .stButton>button p{ color:#fff !important; }

/* 막대 — 선택 여부와 관계없이 모두 진하게 */
.stApp .pa-cell, .stApp .pa-cell .bar, .stApp .pa-cell .bar span{ opacity:1 !important; }
.stApp .pa-cell .bar span{ background:var(--pri) !important; }

/* 시뮬레이션 수치 패널 (dp_viz.stats_html) */
.dpstat{ display:flex; flex-direction:column; gap:9px; padding:4px 0 4px 18px;
  border-left:1px solid var(--bd); }
.dpstat .r{ display:flex; justify-content:space-between; align-items:baseline; gap:12px; }
.dpstat .k{ font-size:12px; color:var(--mid); }
.dpstat b{ font-size:13.5px; font-weight:600; color:var(--ink); font-variant-numeric:tabular-nums; }

/* LLM 해설 말풍선 (privacy_analysis._llm_html) */
.pa-llm{ display:flex; gap:10px; align-items:flex-start; margin-top:14px; }
.pa-llm .av{ flex:0 0 28px; height:28px; border-radius:50%; background:var(--pri); color:#fff;
  display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; font-style:italic; }
.pa-llm .tx{ flex:1; padding:10px 14px; border-radius:4px 14px 14px 14px;
  background:var(--prisoft); border:1px solid var(--priline);
  font-size:12.5px; line-height:1.65; color:var(--ink2); word-break:keep-all; }
.pa-llm .ld{ color:var(--mid); }
.pa-llm .er{ color:var(--dan2); }

/* ══ 11-x. 데이터셋 별 정책 현황 — 얇은 행 ══ */
.stApp .st-key-card_policies .trow{
  padding-top:6px !important; padding-bottom:6px !important;
  min-height:0 !important; align-items:center !important;
}
/* 데이터셋 이름 + 코드 한 줄로 */
.stApp .st-key-card_policies .trow .tt{ display:inline !important; font-size:13px !important; }
.stApp .st-key-card_policies .trow .ts{ display:inline !important; margin-left:8px; font-size:11px !important; }
/* Utility 배지 · 자동/수동 배지 작게 */
.stApp .st-key-card_policies .trow [class*="pill"]{
  padding:1px 8px !important; font-size:11px !important; line-height:1.5 !important;
}
.stApp .st-key-card_policies .pmode{ padding:1px 7px !important; font-size:10.5px !important; }

/* 11-x. 프라이버시 분석 — LLM 해설 로딩 (도는 링 + 세미 볼드) */
.stApp .pa-llm .ld{
  display:inline-flex !important; align-items:center; gap:8px;
  font-weight:600 !important; color:var(--ink2) !important;
}
.stApp .pa-llm .ld .spin{
  flex:0 0 auto; width:14px; height:14px; border-radius:50%;
  border:2px solid var(--priline);
  border-top-color:var(--pri);
  animation:pa-spin .8s linear infinite;
}
@keyframes pa-spin{ to{ transform:rotate(360deg); } }

/* 11-x. 프라이버시 분석 — 시뮬레이션 닫기 · 다시 재생 위치 */
.stApp .st-key-pa_closewrap{ justify-content:flex-end !important; }
.stApp .st-key-pa_close button{
  width:30px !important; height:30px !important; min-height:30px !important;
  padding:0 !important; border-radius:8px !important;
  border:1px solid transparent !important; background:transparent !important;
  color:var(--mid) !important; box-shadow:none !important;
}
.stApp .st-key-pa_close button:hover{
  background:var(--prisoft) !important; border-color:var(--priline) !important;
  color:var(--pri2) !important;
}
.stApp .st-key-pa_close [data-testid="stIconMaterial"]{ font-size:18px !important; }

.stApp .st-key-pa_replay{
  display:flex !important; justify-content:center !important;   /* 그래프 가운데 아래 */
  margin-top:-6px !important;
}

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
  <p class="lead">분석가는 원본 데이터에 직접 접근하지 않고, 에이전트가 실행한
  코드의 결과만 차분 프라이버시 보호 아래 받아봅니다.</p>
  <div class="bl"><div class="n">1</div><div class="t"><b>자연어 질의</b>
    <span>프라이버시적으로 안전한 필드 정보를 통해 통계량을 질문합니다.</span></div></div>
  <div class="bl"><div class="n">2</div><div class="t"><b>ε 예산 관리</b>
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


def budget_meter(spent: float, total: float, remain: int, *, size: int = 64) -> str:
    """콘솔 오른쪽 ε 예산 — [수치 · 잔여(오른쪽 정렬, 도넛 아랫선 기준)] [도넛]."""
    total = max(float(total), 1e-9)
    ratio = max(0.0, min(1.0, float(spent) / total))
    color = "#f43f5e" if ratio >= 0.8 else "#6366f1"
    sw = 7
    h = size / 2
    r = (size - sw) / 2
    c = 2 * math.pi * r
    arc = (f'<circle cx="{h}" cy="{h}" r="{r}" fill="none" stroke="{color}" stroke-width="{sw}" '
           f'stroke-linecap="round" stroke-dasharray="{c * ratio:.2f} {c:.2f}" '
           f'transform="rotate(-90 {h} {h})"/>') if ratio > 0 else ""
    return (
        '<div class="bmeter">'
        '<div class="bm-txt">'
        f'<div class="bm-val">{float(spent):.2f} / {total:.2f}<span class="bm-eps">ε</span></div>'
        f'<div class="bm-sub">잔여 {int(remain)}회</div>'
        '</div>'
        f'<div class="bm-ring"><svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'<circle cx="{h}" cy="{h}" r="{r}" fill="none" stroke="#e2e8f0" stroke-width="{sw}"/>'
        f'{arc}</svg><span class="bm-pct">{ratio * 100:.0f}%</span></div>'
        '</div>'
    )


# ── 표 페이지 나누기 (history · budget_admin 공용) ───────────
def pager(total: int, size: int, key: str, reset_on=None) -> tuple[int, int]:
    """(start, end) 슬라이스 범위를 돌려준다.

    번호 버튼은 호출한 자리에 그려지므로, 표는 미리 잡아 둔 자리(slot)에 나중에 그린다.
    reset_on (데이터셋·필터 등) 값이 바뀌면 1페이지로 돌아간다. 1페이지뿐이면 버튼을 숨긴다.
    """
    pages = max(1, math.ceil(total / size))
    sig = f"_{key}_sig"
    if st.session_state.get(sig) != reset_on:          # 범위가 바뀌면 1페이지로
        st.session_state[sig] = reset_on
        st.session_state.pop(key, None)
    cur = st.session_state.get(key)
    if isinstance(cur, int) and cur > pages:           # 지워져서 페이지 수가 줄어든 경우
        st.session_state[key] = pages

    page = 1
    if pages > 1:
        with st.container(horizontal=True, horizontal_alignment="center", key=f"{key}_wrap"):
            if hasattr(st, "pagination"):
                page = st.pagination(pages, max_visible_pages=7, key=key)
            else:
                st.caption("페이지 버튼은 최신 Streamlit 에서 표시됩니다 — pip install -U streamlit")
    start = (page - 1) * size
    return start, min(start + size, total)