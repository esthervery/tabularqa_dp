"""프라이버시 분석 (관리자) — 리스크 레벨별 신뢰구간 수렴.

화면: 관리자가 데이터셋 × 리스크 레벨의 DP 보장 수준을 비교하고,
      데이터셋별 기본 정책을 [확정] 하는 곳.

계산은 ui/dp_sim.py 의 simulate() 를 그대로 쓴다 (라플라스 노이즈 시뮬레이션).
값 노출 규칙 — 이 화면에도 원본 값은 올리지 않는다.
    표시  : 리스크별 최종 95% CI 폭, 필요 라운드 수 k, 민감도 Δ
    금지  : 참 평균·최소·최대·개별 응답 (원본 통계 노출 경로가 된다)

SIM_TARGET 주의
    dp_sim.SIM_TARGET 에는 원래 000_CardBase/047_Bank 만 등록돼 있다.
    데모 4종을 쓰기 위해 이 페이지에서 스펙의 측정 대상 컬럼으로 채워 넣는다.
    (ui/dp_sim.py 를 고치지 않아도 되고, 스펙과 어긋나지 않는다.)
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
    if dp_sim is None:
        st.markdown(design.topbar("프라이버시 분석", "Admin"), unsafe_allow_html=True)
        st.markdown(design.warn("시뮬레이터를 불러오지 못했습니다 — scipy 설치가 필요합니다 "
                                f"({_SIM_ERR})"), unsafe_allow_html=True)
        return
    _ensure_targets()
    st.markdown(design.topbar("프라이버시 분석", "Admin"), unsafe_allow_html=True)
    st.markdown(design.page_head(
        "프라이버시 분석",
        "리스크 레벨별 95% 신뢰구간 폭 — 낮을수록 프라이버시가 강하고 결과가 거칠다"),
        unsafe_allow_html=True)

    rows = []
    errors = []
    for name, spec in fields.SPECS.items():
        if not spec.get("enabled"):
            continue
        widths, k = {}, None
        for r in RISKS:
            try:
                res = dp_sim.simulate(name, r)
                widths[r] = float(res.stop_ci_hi - res.stop_ci_lo)
                k = int(res.k)
            except Exception as e:
                errors.append(f"{name} · Risk {r}: {type(e).__name__}: {e}")
        if widths:
            rows.append({"name": name, "title": spec["title"], "widths": widths,
                         "k": k, "measure": spec["measure"]})

    if errors:
        st.markdown(design.warn("일부 시뮬레이션을 계산하지 못했습니다 — " + "; ".join(errors[:3])),
                    unsafe_allow_html=True)

    if not rows:
        st.markdown(design.empty("시뮬레이션할 데이터셋이 없습니다"), unsafe_allow_html=True)
        return

    _matrix(rows)
    st.write("")
    _confirm(rows)


# ── 매트릭스 ────────────────────────────────────────────

def _matrix(rows: list[dict]) -> None:
    """데이터셋(행) × 리스크(열) CI 폭 표. 셀은 막대로도 보여준다."""
    all_w = [w for r in rows for w in r["widths"].values()]
    wmax = max(all_w) if all_w else 1.0

    head = ('<div style="display:grid;grid-template-columns:1.5fr repeat(5,1fr) 74px;'
            'gap:8px;padding:6px 10px;border-bottom:1px solid #e4e8ee">'
            '<span class="mono dim" style="font-size:7.5px;letter-spacing:.08em">DATASET</span>')
    head += "".join(f'<span class="mono dim" style="font-size:7.5px;text-align:right">RISK {r}</span>'
                    for r in RISKS)
    head += '<span class="mono dim" style="font-size:7.5px;text-align:right">Δ축소</span></div>'

    body = []
    for r in rows:
        w = r["widths"]
        cells = "".join(_cell(w.get(k), wmax) for k in RISKS)
        first, last = w.get(1), w.get(5)
        delta = f"{first / last:.1f}×" if first and last else "-"
        body.append(
            '<div style="display:grid;grid-template-columns:1.5fr repeat(5,1fr) 74px;'
            'gap:8px;padding:8px 10px;border-bottom:1px solid #eef1f5;align-items:center">'
            f'<span><span style="font-size:10px;font-weight:600;color:#101828">{r["title"]}</span>'
            f'<span class="mono dim" style="font-size:7.5px;display:block">{r["name"]}'
            f' · k={r["k"]}</span></span>' + cells +
            f'<span class="mono" style="font-size:9.5px;text-align:right;color:#0d9f7a">{delta}</span>'
            "</div>"
        )

    st.markdown('<div class="card" style="padding:6px 4px 0"><div class="rh" '
                'style="padding:0 6px 2px">리스크별 최종 95% CI 폭</div>'
                '<div class="dim" style="font-size:8.5px;padding:0 6px 8px">'
                '각 셀 = 시뮬레이션 마지막 라운드의 신뢰구간 폭 (작을수록 정밀)</div>'
                + head + "".join(body) + "</div>", unsafe_allow_html=True)


def _cell(v: float | None, wmax: float) -> str:
    if v is None:
        return '<span class="mono dim" style="font-size:9px;text-align:right">—</span>'
    pct = max(6.0, min(100.0, v / wmax * 100))
    return ('<span style="display:flex;flex-direction:column;gap:2px">'
            f'<span class="mono" style="font-size:9px;text-align:right;color:#333f52">{v:,.1f}</span>'
            '<span style="height:3px;border-radius:9px;background:#eef1f5;overflow:hidden">'
            f'<span style="display:block;height:100%;width:{pct:.0f}%;'
            'background:linear-gradient(90deg,#cdd2fb,#5457e0)"></span></span></span>')


# ── 정책 확정 ───────────────────────────────────────────

def _confirm(rows: list[dict]) -> None:
    admin = st.session_state.get("username") or "admin"
    names = [r["name"] for r in rows]
    st.markdown('<div class="card"><div class="rh">데이터셋 기본 정책 확정</div>'
                '<div class="dim" style="font-size:9px;margin-bottom:8px">'
                '확정된 정책은 개인 오버라이드가 없는 모든 분석가에게 적용됩니다</div>',
                unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1.4, 1.1, 1.6, 0.8], vertical_alignment="bottom")
    with c1:
        ds = st.selectbox("데이터셋", names, key="pol_ds",
                          format_func=lambda k: f"{next(r['title'] for r in rows if r['name'] == k)} · {k}")
    with c2:
        lv = st.selectbox("리스크", RISKS, index=2, key="pol_lv",
                          format_func=lambda x: f"Risk {x} ({db.RISK_TO_EPSILON[x]:.1f} ε)")
    with c3:
        note = st.text_input("메모", key="pol_note", placeholder="확정 근거 (선택)")
    with c4:
        if st.button("확정", type="primary", key="pol_ok", use_container_width=True):
            try:
                db.confirm_policy(admin, ds, int(lv), note or None)
                st.success(f"{ds} 기본 정책을 Risk {lv} 로 확정했습니다.")
            except Exception as e:
                st.error(f"확정하지 못했습니다 ({type(e).__name__}: {e})")

    hist = db.policy_history(limit=8)
    if hist:
        st.markdown('<div class="reqdiv"></div>', unsafe_allow_html=True)
        out = []
        for h in hist:
            out.append(
                '<div style="display:grid;grid-template-columns:76px 1fr 60px 1fr;gap:8px;'
                'align-items:center;border-bottom:1px solid #eef1f5;padding:5px 0;font-size:9px">'
                f'<span class="mono dim" style="font-size:8px">{_t(h.get("confirmed_at"))}</span>'
                f'<span class="mono" style="font-size:9px">{h["db_name"]}</span>'
                f'<span class="mono" style="font-size:9px">Risk {h["risk_level"]}</span>'
                f'<span class="dim">{_esc(h.get("note") or "-")}</span></div>'
            )
        st.markdown("".join(out), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _t(v) -> str:
    if not v:
        return "-"
    return str(v).replace("T", " ")[5:16]


def _esc(s) -> str:
    return str(s).replace("<", "&lt;").replace(">", "&gt;")