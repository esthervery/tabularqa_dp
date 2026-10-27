"""예산 신청 (분석가) — Utility 레벨 상향 요청.

Renders (위→아래):
    1) 신청 카드 : 신청 대상(왼쪽) + 도넛 카드(오른쪽, 콘솔과 같은 budget_meter)
                   → Utility 레벨 선택(고정 폭 버튼) → 사유 → [신청 제출]
    2) 내 신청 이력 (상단 바에서 고른 데이터셋만)

데이터 경로
    현재 정책 : db.get_effective_policy  (오버라이드 > DB 기본 > 시스템 기본)
    소모 ε    : db.spent_epsilon         (query_log SUM)
    신청      : requests.create          (status='pending')
"""
from __future__ import annotations

import streamlit as st

from ui import db, design, fields, requests, state

EPS = 0.1
try:
    from ui import dp_sim
    EPS = float(dp_sim.EPS_PER_QUERY)
except Exception:         # noqa: BLE001
    dp_sim = None

ORD = [k for k, v in fields.SPECS.items() if v.get("enabled")]
TL = {k: fields.SPECS[k]["title"] for k in ORD}
RISK_EPS = db.RISK_TO_EPSILON
HIST_MAX = 12
FLASH_KEY = "req_flash"   # 제출 후 rerun 너머로 알림 문구를 넘기는 세션 키
LV_WIDTH = 112            # 레벨 버튼 고정 폭(px)


def render() -> None:
    design.inject()

    # 제출 직후 rerun 에서 한 번만 띄우고 지운다 → 4초 뒤 자동으로 사라짐
    flash = st.session_state.pop(FLASH_KEY, None)
    if flash:
        st.toast(flash, duration="short")

    user = st.session_state.get("username") or "analyst"
    pick = st.session_state.get("db_name")
    if pick not in ORD:
        pick = ORD[0]

    pol = db.get_effective_policy(user, pick)
    risk = int(pol["risk_level"])
    total = float(pol["total_epsilon"])
    spent = db.spent_epsilon(user, pick)
    eps = float(st.session_state.get("eps") or EPS)
    remain = max(0, int((total - spent) / eps + 1e-9))
    src = {"override": "개인 승인", "db_default": "데이터셋 기본",
           "system_default": "시스템 기본"}.get(pol.get("source", ""), "-")
    meas = fields.SPECS[pick]["measure"]

    with st.container(border=True, key="card_request"):
        # 왼쪽·오른쪽 1:1 → 구분선(rqform 왼쪽 테두리)이 정가운데
        with st.container(horizontal=True, vertical_alignment="top",
                          gap="small", wrap=False, key="rqtop"):
            # ── 왼쪽: [신청 대상 + 도넛] / 신청 이력 ──
            with st.container(key="rqleft", width="stretch"):
                with st.container(horizontal=True, vertical_alignment="top",
                                  gap="small", wrap=False, key="rqhead"):
                    with st.container(key="rqinfo", width="content"):
                        st.markdown(design.card_head(
                            "신청 대상", f"{TL[pick]} · 통계 대상 {meas['label']}"),
                            unsafe_allow_html=True)
                        st.markdown(design.line([
                            ("현재 정책", f"Utility {risk}"),
                            ("ε 예산", f"{total:.2f}"),
                            ("정책 출처", src),
                        ]), unsafe_allow_html=True)
                    with st.container(key="cbring", border=False, width="content"):
                        st.markdown(design.budget_meter(spent, total, remain, size=84),
                                    unsafe_allow_html=True, width="stretch")
                _history(user, pick)

            # ── 오른쪽: 레벨 선택 + 사유 + 제출 ──
            with st.container(key="rqform", width="stretch"):
                _levels(user, pick, risk)


# ── Utility 레벨 선택 ──────────────────────────────────
def _levels(user: str, pick: str, risk: int) -> None:
    top = max(RISK_EPS)
    maxed = risk >= top
    note = ('<span class="rqnote">이미 최고 Utility 레벨에 도달했습니다</span>'
            if maxed else "")
    st.html(f'<div class="rqtitle">Utility 레벨 선택{note}</div>')

    sk = f"req_pick_{pick}"                       # 데이터셋별 선택 기억
    if not maxed and (st.session_state.get(sk) or 0) <= risk:
        st.session_state[sk] = risk + 1
    chosen = st.session_state.get(sk)

    with st.container(horizontal=True, gap="small", wrap=False, key="lvrow"):
        for r in sorted(RISK_EPS):
            e = f"ε {RISK_EPS[r]:.0f}"
            if r <= risk:                         # 현재·하위 레벨: 점선 + 클릭 불가
                is_cur = r == risk
                st.button(f"Utility {r}\n\n{'현재 · ' if is_cur else ''}{e}",
                          key=f"lvl_cur_{r}" if is_cur else f"lvl_off_{r}",
                          disabled=True, width="stretch", wrap=True)
            else:
                on = r == chosen
                if st.button(f"Utility {r}\n\n{e}",
                             key=f"lvl_on_{r}" if on else f"lvl_go_{r}",
                             width="stretch", wrap=True):
                    st.session_state[sk] = r
                    st.rerun()

    if maxed:
        return

    rk = f"req_reason_{pick}"
    st.html('<div class="rqhtitle rqrtitle">신청 사유</div>')   # "신청 이력"과 같은 제목 스타일
    reason = st.text_area(
        "신청 사유", placeholder=(
            f"예: {fields.SPECS[pick]['measure']['label']} 상위 구간의 중앙값을 "
            f"더 좁은 신뢰구간으로 확인해야 합니다"),
        height=84, key=rk, label_visibility="collapsed",
    )

    with st.container(horizontal=True, horizontal_alignment="right", key="rqsubmit"):
        submitted = st.button("신청 제출", type="primary", key="req_submit", width=140)
    if submitted:
        if not reason.strip():
            st.toast("신청 사유를 입력하세요. 관리자 승인 판단에 쓰입니다.")
            return
        try:
            rid = requests.create(user, pick, risk, int(chosen), reason)
            state.log("request", f"{pick} Utility {risk}→{chosen} 신청 #{rid}")
        except Exception as e:
            st.error(f"신청을 접수하지 못했습니다 ({type(e).__name__}: {e})")
            return
        # 알림은 rerun 뒤에 띄운다 → 왼쪽 이력 표에도 방금 신청이 바로 보임
        st.session_state[FLASH_KEY] = (f"Utility {risk} → {chosen} 신청을 접수했습니다. "
                                       f"관리자 승인 후 콘솔에 반영됩니다.")
        st.session_state.pop(rk, None)            # 사유 입력칸 비우기
        st.rerun()


# ── 신청 이력 (카드 안 왼쪽 아래 · 선택한 데이터셋만) ─────────
def _history(user: str, pick: str) -> None:
    rows = [r for r in requests.list_by_user(user)
            if r.get("db_name") == pick][:HIST_MAX]
    head = f'<div class="rqhtitle">신청 이력<span>{len(rows)}건</span></div>'
    if not rows:
        st.html(head + '<div class="pa-empty rqempty">아직 신청 이력이 없습니다</div>')
        return

    grid = "grid-template-columns:84px 108px minmax(0,1fr) 60px"
    out = [f'<div class="trow head" style="{grid}"><span>신청</span>'
           '<span>레벨</span><span>사유</span><span class="r">상태</span></div>']
    for r in rows:
        why = _esc(r.get("reason") or "")
        out.append(
            f'<div class="trow" style="{grid}">'
            f'<span class="t">{_t(r.get("created_at"))}</span>'
            f'<span class="m">Utility {r.get("current_level")} → {r.get("requested_level")}</span>'
            f'<span class="x" title="{why}">{why}</span>'
            f'<span class="r">{design.status_pill(r.get("status"))}</span></div>'
        )
    st.html(head + '<div class="rqhist">' + "".join(out) + "</div>")


def _t(v) -> str:
    if not v:
        return "-"
    return str(v).replace("T", " ")[5:16]


def _esc(s) -> str:
    return str(s).replace("<", "&lt;").replace(">", "&gt;")


# Streamlit 은 페이지 파일을 '스크립트'로 실행한다 — render() 를 직접 호출해야 한다.
render()