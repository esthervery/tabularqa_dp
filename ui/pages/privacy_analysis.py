"""프라이버시 분석 (관리자) — 리스크 레벨별 신뢰구간 수렴.

관리자가 데이터셋 × 리스크 레벨의 DP 보장 수준을 비교하고,
데이터셋별 기본 정책을 [확정] 하는 곳.

Renders (위→아래):
    1) 페이지 제목
    2) 매트릭스 카드 : 데이터셋(행) × Risk 1~5(열) 최종 95% CI 폭 + 막대 + 축소 배율
    3) 정책 확정 카드 : 데이터셋 · 리스크 · 메모 · [확정] + 최근 확정 이력 표

계산은 ui/dp_sim.py 의 simulate() 를 그대로 쓴다 (라플라스 노이즈 시뮬레이션).
값 노출 규칙 — 이 화면에도 원본 값은 올리지 않는다.
    표시  : 리스크별 최종 95% CI 폭, 필요 라운드 수 k
    금지  : 참 평균·최소·최대·개별 응답
(로직은 demo 브랜치 원본과 동일 — 레이아웃·스타일만 변경)
"""
from __future__ import annotations

import streamlit as st

from ui import db, design, fields

try:
    from ui import dp_sim
    _SIM_ERR = None
except Exception as _e:   # scipy 미설치 등 — 화면은 뜨고 안내만 남긴다
    dp_sim = None
    _SIM_ERR = f"{type(_e).__name__}: {_e}"

RISKS = [1, 2, 3, 4, 5]


def _ensure_targets() -> None:
    for name, spec in fields.SPECS.items():
        if spec.get("enabled"):
            dp_sim.SIM_TARGET.setdefault(name, spec["measure"]["col"])


def render() -> None:
    design.inject()
    # st.markdown(design.page_hero(
    #     "프라이버시 분석",
    #     "리스크 레벨별 95% 신뢰구간 폭 — 낮은 레벨일수록 프라이버시가 강하고 결과가 거칩니다."),
    #     unsafe_allow_html=True)

    if dp_sim is None:
        st.markdown(design.warn("시뮬레이터를 불러오지 못했습니다 — scipy 설치가 필요합니다 "
                                f"({_SIM_ERR})"), unsafe_allow_html=True)
        return
    _ensure_targets()

    # 분석 대상 = 상단 바에서 고른 데이터셋 하나 ('전체' 없음)
    name = st.session_state.get("db_name")
    spec = fields.SPECS.get(name) or {}
    if not spec.get("enabled"):
        st.markdown(design.empty("분석할 데이터셋을 상단에서 선택하세요"), unsafe_allow_html=True)
        return

    widths, k, errors = {}, None, []
    for r in RISKS:
        try:
            res = dp_sim.simulate(name, r)
            widths[r] = float(res.stop_ci_hi - res.stop_ci_lo)
            k = int(res.k)
        except Exception as e:
            errors.append(f"Utility {r}: {type(e).__name__}: {e}")

    if errors:
        st.markdown(design.warn("일부 시뮬레이션을 계산하지 못했습니다 — " + "; ".join(errors[:3])),
                    unsafe_allow_html=True)

    if not widths:
        st.markdown(design.empty("이 데이터셋의 시뮬레이션 결과가 없습니다"), unsafe_allow_html=True)
        return

    row = {"name": name, "title": spec["title"], "widths": widths,
           "k": k, "measure": spec["measure"]}
    _matrix([row])      # 표 함수는 그대로 — 행이 1개만 들어간다
    _confirm(row)


# ── 매트릭스 ────────────────────────────────────────────

def _matrix(rows: list[dict]) -> None:
    """데이터셋(행) × 리스크(열) CI 폭 표. 셀은 막대로도 보여준다."""
    all_w = [w for r in rows for w in r["widths"].values()]
    wmax = max(all_w) if all_w else 1.0
    grid = "grid-template-columns:1.6fr repeat(5,1fr) 80px"

    head = (f'<div class="trow head" style="{grid}"><span>데이터셋</span>'
            + "".join(f'<span class="r">Utility {r}</span>' # · ε{db.RISK_TO_EPSILON[r]:.0f}</span>'
                      for r in RISKS)
            + '<span class="r">축소</span></div>')

    body = []
    for r in rows:
        w = r["widths"]
        cells = "".join(_cell(w.get(k), wmax) for k in RISKS)
        first, last = w.get(1), w.get(5)
        delta = f"{first / last:.1f}×" if first and last else "-"
        body.append(
            f'<div class="trow" style="{grid}">'
            f'<span><span class="tt">{r["title"]}</span>'
            f'<span class="ts">{r["name"]} · {r["measure"]["label"]}</span></span>'
            + cells +
            f'<span class="r m" style="color:var(--suc2);font-weight:600">{delta}</span></div>'
        )

    with st.container(border=True, key="card_matrix"):
        st.markdown(design.card_head(
            # "Utility별 최종 95% CI 폭",
            "프라이버시 리스크 분석",
            #"각 셀 = 시뮬레이션 마지막 라운드의 신뢰구간 폭 (작을수록 정밀) · "
            "신뢰구간 상대폭 기반 유틸리티 정책 별 위험도 분석"),
            #"축소 = Utility 1 대비 Utility 5 의 폭 축소 배율"),
            unsafe_allow_html=True)
        st.markdown(head + "".join(body), unsafe_allow_html=True)


def _cell(v: float | None, wmax: float) -> str:
    if v is None:
        return '<span class="r t">—</span>'
    pct = max(6.0, min(100.0, v / wmax * 100))
    return (f'<span class="r"><span class="m">{v:,.1f}</span>'
            f'<div class="cellbar"><span style="width:{pct:.0f}%"></span></div></span>')


# ── 정책 확정 ───────────────────────────────────────────
def _confirm(row: dict) -> None:
    admin = st.session_state.get("username") or "admin"
    ds = row["name"]

    with st.container(border=True, key="card_confirm"):
        st.markdown(design.card_head(
            "데이터셋 기본 정책 설정",
            f"대상: {row['title']}"), # · {ds} — 확정된 정책은 개인 오버라이드가 없는 모든 분석가에게 적용됩니다."),
            unsafe_allow_html=True)

        c1, c2, c3 = st.columns([1.1, 2.2, 0.8], vertical_alignment="bottom")
        with c1:
            lv = st.selectbox("Utility", RISKS, index=2, key="pol_lv",
                              format_func=lambda x: f"Utility {x} ({db.RISK_TO_EPSILON[x]:.0f} ε)")
        with c2:
            note = st.text_input("메모", key="pol_note", placeholder="확정 근거 (선택)")
        with c3:
            if st.button("확정", type="primary", key="pol_ok", use_container_width=True):
                try:
                    db.confirm_policy(admin, ds, int(lv), note or None)
                    st.success(f"{ds} 기본 정책을 Utility {lv} 로 확정했습니다.")
                except Exception as e:
                    st.error(f"확정하지 못했습니다 ({type(e).__name__}: {e})")

        # 이 데이터셋의 확정 이력만 (최근 8건)
        hist = [h for h in db.policy_history(limit=50) if h.get("db_name") == ds][:8]
        st.markdown('<div class="reqdiv"></div>', unsafe_allow_html=True)
        if not hist:
            st.markdown(design.empty("이 데이터셋의 확정 이력이 없습니다"), unsafe_allow_html=True)
            return
        grid = "grid-template-columns:100px 120px 1fr"
        out = [f'<div class="trow head" style="{grid}"><span>확정</span>'
               '<span>Utility</span><span>메모</span></div>']
        for h in hist:
            risk_badge = design.pill("Utility " + str(h["risk_level"]), "primary")
            out.append(
                f'<div class="trow" style="{grid}">'
                f'<span class="t">{_t(h.get("confirmed_at"))}</span>'
                f'<span>{risk_badge}</span>'
                f'<span class="x">{_esc(h.get("note") or "-")}</span></div>'
            )
        st.markdown("".join(out), unsafe_allow_html=True)


def _t(v) -> str:
    if not v:
        return "-"
    return str(v).replace("T", " ")[5:16]


def _esc(s) -> str:
    return str(s).replace("<", "&lt;").replace(">", "&gt;")


# Streamlit 은 페이지 파일을 '스크립트'로 실행한다 — render() 를 직접 호출해야 한다.
render()