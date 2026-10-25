"""예산 신청 (분석가) — 리스크 레벨 상향 요청.

화면: platform_v14.html 의 '예산 신청'. 카드 1장 안에서
      질의 대상 → 현재 정책 → 상향 요청 순으로 흐른다 (섹션 분리 없음).

데이터 경로
    현재 정책 : db.get_effective_policy  (오버라이드 > DB 기본 > 시스템 기본)
    소모 ε    : db.spent_epsilon         (query_log SUM)
    신청      : requests.create          (status='pending')
승인되면 requests.decide 가 user_policy_override 를 만들어
다음 콘솔 진입부터 새 리스크 레벨이 적용된다.
"""
from __future__ import annotations

import streamlit as st

from ui import db, design, fields, requests, state

# 질의당 ε. dp_sim 은 scipy 를 요구하므로, 없어도 화면이 뜨도록 기본값을 먼저 확정한다.
EPS = 0.1
try:
    # dp_sim 은 scipy 가 필요하다 — 없어도 신청 화면은 떠야 한다
    from ui import dp_sim
    EPS = float(dp_sim.EPS_PER_QUERY)
except Exception:         # noqa: BLE001
    dp_sim = None

ORD = [k for k, v in fields.SPECS.items() if v.get("enabled")]
TL = {k: fields.SPECS[k]["title"] for k in ORD}
RISK_EPS = db.RISK_TO_EPSILON


def render() -> None:
    design.inject()
    is_admin = bool(st.session_state.get("is_admin"))
    st.markdown(design.topbar("예산 신청", "Admin" if is_admin else "Workspace"),
                unsafe_allow_html=True)
    st.markdown(design.page_head("예산 신청",
                                 "더 정밀한 결과가 필요하면 관리자에게 리스크 레벨 상향을 요청합니다"),
                unsafe_allow_html=True)

    user = st.session_state.get("username") or "analyst"
    cur = st.session_state.get("db_name")
    if cur not in ORD:
        cur = ORD[0]

    # ── 질의 대상 ──
    head_l, head_r = st.columns([2.4, 1.3], vertical_alignment="center")
    with head_l:
        meas = fields.SPECS[cur]["measure"]
        st.markdown(
            '<div class="row"><span class="rh" style="margin:0;font-size:11px;font-weight:700">'
            '질의 대상</span>'
            f'<span class="mono dim" style="font-size:8px">{meas["label"]} ({meas["col"]})'
            f' · {_rows(cur):,}행</span></div>', unsafe_allow_html=True)
    with head_r:
        pick = st.selectbox("데이터셋", ORD, index=ORD.index(cur),
                            format_func=lambda k: f"{TL.get(k, k)}  ·  {k}", key="req_ds")
        if pick != cur:
            st.session_state.db_name = pick
            st.rerun()

    # ── 현재 정책 ──
    pol = db.get_effective_policy(user, pick)
    risk = int(pol["risk_level"])
    total = float(pol["total_epsilon"])
    spent = db.spent_epsilon(user, pick)
    eps = float(st.session_state.get("eps") or EPS)
    remain = max(0, int((total - spent) / eps + 1e-9))

    st.markdown(design.line([
        ("현재 정책", f"Risk {risk}"),
        ("총 ε", f"{total:.2f}"),
        ("사용", f"{spent:.2f}"),
        ("잔여", f"{remain}회"),
    ]), unsafe_allow_html=True)

    src = {"override": "개인 승인", "db_default": "데이터셋 기본",
           "system_default": "시스템 기본"}.get(pol.get("source", ""), "")
    if src:
        st.markdown(f'<div class="dim" style="font-size:8.5px;margin:5px 0 2px">'
                    f'정책 출처 · {src}</div>', unsafe_allow_html=True)

    st.markdown('<div class="reqdiv"></div>', unsafe_allow_html=True)

    # ── 상향 요청 ──
    options = [r for r in sorted(RISK_EPS) if r > risk]
    if not options:
        st.markdown(design.empty("이미 최고 리스크 레벨(Risk 5)입니다 — 추가 상향이 없습니다"),
                    unsafe_allow_html=True)
        _history(user)
        return

    lab_l, lab_r = st.columns([1.2, 1.8], vertical_alignment="bottom")
    with lab_l:
        st.markdown('<div style="font-size:10.5px;font-weight:700;color:#101828">'
                    '리스크 상향 요청</div>', unsafe_allow_html=True)
    with lab_r:
        st.markdown(f'<div style="font-size:9px;color:#8896a8;text-align:right">'
                    f'Risk {risk} 보다 높은 단계만 선택할 수 있습니다</div>',
                    unsafe_allow_html=True)

    chosen = st.radio(
        "요청 레벨", options, index=0, horizontal=True,
        format_func=lambda r: f"Risk {r} · 총 ε {RISK_EPS[r]:.1f}",
        label_visibility="collapsed", key="req_level",
    )
    reason = st.text_area(
        "신청 사유", placeholder=(
            f"예: {fields.SPECS[pick]['measure']['label']} 상위 구간의 중앙값을 "
            f"더 좁은 신뢰구간으로 확인해야 합니다"),
        height=70, key="req_reason",
    )

    if st.button("신청 제출", type="primary", key="req_submit"):
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
    st.markdown('<div class="card"><div class="rh">내 신청 이력</div>', unsafe_allow_html=True)
    if not rows:
        st.markdown('<div class="dim" style="font-size:9.5px">아직 신청한 이력이 없습니다</div>',
                    unsafe_allow_html=True)
    else:
        cls = {"pending": "p", "approved": "a", "partial": "a", "rejected": "r"}
        name = {"pending": "대기", "approved": "승인", "partial": "조정", "rejected": "거절"}
        out = []
        for r in rows[:12]:
            out.append(
                '<div class="mylog" style="display:grid;grid-template-columns:70px 96px 1fr 54px;'
                'gap:8px;align-items:center;border-bottom:1px solid #eef1f5;padding:6px 0;font-size:10px">'
                f'<span class="mono dim" style="font-size:8px">{_t(r.get("created_at"))}</span>'
                f'<span class="mono" style="font-size:9px">{r.get("db_name")}</span>'
                f'<span style="color:#5a6779">Risk {r.get("current_level")} → {r.get("requested_level")}'
                f' · {_esc((r.get("reason") or "")[:40])}</span>'
                f'<span class="tag {cls.get(r.get("status"), "")}" style="text-align:center">'
                f'{name.get(r.get("status"), r.get("status"))}</span></div>'
            )
        st.markdown("".join(out), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


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
