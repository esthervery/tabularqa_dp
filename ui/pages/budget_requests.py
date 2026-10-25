"""예산 신청 (분석가) — 리스크 레벨 상향 요청.

Renders (위→아래):
    1) 페이지 제목
    2) 신청 카드 : 질의 대상(데이터셋 선택) + 현재 정책 도넛/요약
                   → 리스크 상향 레벨(세그먼트) → 사유 → [신청 제출]
    3) 내 신청 이력 카드 (표 형태 + 상태 뱃지)

데이터 경로
    현재 정책 : db.get_effective_policy  (오버라이드 > DB 기본 > 시스템 기본)
    소모 ε    : db.spent_epsilon         (query_log SUM)
    신청      : requests.create          (status='pending')
승인되면 requests.decide 가 user_policy_override 를 만들어
다음 콘솔 진입부터 새 리스크 레벨이 적용된다.
(로직은 demo 브랜치 원본과 동일 — 레이아웃·스타일만 변경)
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


def render() -> None:
    design.inject()
    st.markdown(design.page_hero(
        "예산 신청",
        "더 정밀한 결과가 필요하면 관리자에게 리스크 레벨 상향을 요청합니다."),
        unsafe_allow_html=True)

    user = st.session_state.get("username") or "analyst"
    cur = st.session_state.get("db_name")
    if cur not in ORD:
        cur = ORD[0]

    with st.container(border=True, key="card_request"):
        # ── 질의 대상 + 현재 정책 ──
        left, right = st.columns([1.6, 1], gap="large", vertical_alignment="center")
        with left:
            meas = fields.SPECS[cur]["measure"]
            st.markdown(design.card_head(
                "질의 대상",
                f"측정 대상 · {meas['label']} ({meas['col']}) · {_rows(cur):,}행"),
                unsafe_allow_html=True)
            pick = st.selectbox("데이터셋", ORD, index=ORD.index(cur),
                                format_func=lambda k: f"{TL.get(k, k)}  ·  {k}",
                                key="req_ds", label_visibility="collapsed")
            if pick != cur:
                st.session_state.db_name = pick
                st.rerun()

        pol = db.get_effective_policy(user, pick)
        risk = int(pol["risk_level"])
        total = float(pol["total_epsilon"])
        spent = db.spent_epsilon(user, pick)
        eps = float(st.session_state.get("eps") or EPS)
        remain = max(0, int((total - spent) / eps + 1e-9))
        src = {"override": "개인 승인", "db_default": "데이터셋 기본",
               "system_default": "시스템 기본"}.get(pol.get("source", ""), "")

        with left:
            st.markdown(design.line([
                ("현재 정책", f"Risk {risk}"),
                ("총 ε", f"{total:.2f}"),
                ("정책 출처", src or "-"),
            ]), unsafe_allow_html=True)
        with right:
            st.markdown(design.donut_card(spent, total, sub=f"잔여 {remain}회 질의 가능"),
                        unsafe_allow_html=True)

        st.markdown('<div class="reqdiv"></div>', unsafe_allow_html=True)

        # ── 상향 요청 ──
        options = [r for r in sorted(RISK_EPS) if r > risk]
        if not options:
            st.markdown(design.empty("이미 최고 리스크 레벨(Risk 5)입니다 — 추가 상향이 없습니다"),
                        unsafe_allow_html=True)
        else:
            st.markdown(design.card_head(
                "리스크 상향 요청",
                f"Risk {risk} 보다 높은 단계만 선택할 수 있습니다."),
                unsafe_allow_html=True)

            chosen = st.radio(
                "요청 레벨", options, index=0, horizontal=True,
                format_func=lambda r: f"Risk {r} · 총 ε {RISK_EPS[r]:.0f}",
                label_visibility="collapsed", key="req_level",
            )
            reason = st.text_area(
                "신청 사유", placeholder=(
                    f"예: {fields.SPECS[pick]['measure']['label']} 상위 구간의 중앙값을 "
                    f"더 좁은 신뢰구간으로 확인해야 합니다"),
                height=90, key="req_reason",
            )

            if st.button("신청 제출", type="primary", key="req_submit",
                         use_container_width=True):
                if not reason.strip():
                    st.warning("신청 사유를 입력하세요. 관리자 승인 판단에 쓰입니다.")
                else:
                    try:
                        rid = requests.create(user, pick, risk, int(chosen), reason)
                        st.success(f"신청 #{rid} 을 접수했습니다 — Risk {risk} → {chosen}. "
                                   f"관리자 승인 후 콘솔에 반영됩니다.")
                        state.log("request", f"{pick} Risk {risk}→{chosen} 신청 #{rid}")
                    except Exception as e:
                        st.error(f"신청을 접수하지 못했습니다 ({type(e).__name__}: {e})")

    _history(user)


# ── 내 신청 이력 ────────────────────────────────────────

def _history(user: str) -> None:
    rows = requests.list_by_user(user)
    with st.container(border=True, key="card_myreq"):
        st.markdown(design.card_head("내 신청 이력", f"최근 {min(len(rows), 12)}건"),
                    unsafe_allow_html=True)
        if not rows:
            st.markdown(design.empty("아직 신청한 이력이 없습니다"), unsafe_allow_html=True)
            return
        grid = "grid-template-columns:96px 130px 120px 1fr 70px"
        out = [f'<div class="trow head" style="{grid}"><span>신청</span><span>데이터셋</span>'
               '<span>레벨</span><span>사유</span><span class="r">상태</span></div>']
        for r in rows[:12]:
            out.append(
                f'<div class="trow" style="{grid}">'
                f'<span class="t">{_t(r.get("created_at"))}</span>'
                f'<span class="m">{r.get("db_name")}</span>'
                f'<span class="m">Risk {r.get("current_level")} → {r.get("requested_level")}</span>'
                f'<span class="x">{_esc(r.get("reason") or "")}</span>'
                f'<span class="r">{design.status_pill(r.get("status"))}</span></div>'
            )
        st.markdown("".join(out), unsafe_allow_html=True)


def _rows(name: str) -> int:
    """카탈로그(parquet 메타)에서 행 수만 읽는다 — parquet 전체를 로드하지 않는다."""
    from ui import catalog
    try:
        return int(catalog.meta(name).get("n_rows", 0))
    except Exception:
        return 0


def _t(v) -> str:
    if not v:
        return "-"
    return str(v).replace("T", " ")[5:16]


def _esc(s) -> str:
    return str(s).replace("<", "&lt;").replace(">", "&gt;")


# Streamlit 은 페이지 파일을 '스크립트'로 실행한다 — render() 를 직접 호출해야 한다.
render()