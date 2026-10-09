"""시각화 A — 라운드별 신뢰구간 수렴 애니메이션.

### 0928 신규

무엇을 그리는가
    라운드 k 가 늘어날 때 ① 노이즈 응답이 점으로 찍히고, ② 누적평균이 선을 긋고,
    ③ 95% CI 밴드가 좁아지는 과정을 순차 프레임으로 보여준다.

데이터 출처
    에이전트를 호출하지 않는다. 참 평균 + 설정값(총 ε, 질의당 ε, Risk 로 정해진 k)으로
    라플라스 노이즈를 주입한 합성 응답을 쓴다(ui/dp_sim.py 가 이미 계산해 둔다).
    그래서 재생 시간은 '데이터 준비 시간'에 좌우되지 않고 순전히 프레임 배분의 문제다.

임계값 비교를 넣지 않는다
    플랫폼의 총 ε 은 NIST SP 800-226 을 근거로 Risk 레벨에서 이미 확정된다.
    연구 코드의 '상대폭 < 임계값' 정지 규칙은 이 화면에 넣지 않는다.

재생 속도 — 고정 '길이'가 아니라 고정 '간격'
    총 재생 시간을 고정하지 않는다. 프레임 1장당 FRAME_INTERVAL_S 초로 간격을 고정하므로
    총 길이는 프레임 수에 비례한다.
        Risk 1 (k=20,  20프레임) → 약 4.5초
        Risk 3 (k=60,  32프레임) → 약 7.2초
        Risk 5 (k=100, 32프레임) → 약 7.2초
    예전에는 총 길이를 4.5초로 고정했다. 그러면 k 가 큰 Risk 에서 프레임 간격이
    0.14초까지 눌려 '너무 빨리 지나가는' 느낌이 났다. 속도를 그대로 두고 길이를
    늘리는 쪽이 라운드가 쌓이는 과정을 보여주기에 맞다.
    FRAME_INTERVAL_S = 0.225 는 예전 Risk 1 의 실효 간격(4.5초 ÷ 20프레임)을 그대로 쓴 값이다.

프레임당 렌더 비용 (실측, 이 샌드박스)
    figsize(9.0, 4.2), dpi 110, 범례 + 라이브 수치 박스 포함 → 프레임당 약 140ms
    (matplotlib 오버헤드가 지배라 dpi·크기를 올려도 거의 같다).
    FRAME_INTERVAL_S 가 렌더 시간보다 크므로, 매 프레임 '간격 − 실측 렌더' 만큼만 잔다.
    렌더가 간격보다 오래 걸리면 잠들지 않는다(그 이상 늦출 수 없다).

축 레이블을 영어로 쓰는 이유
    matplotlib 기본 폰트에 한글 글리프가 없어 한글 라벨은 두부(□)로 깨진다.
    폰트 의존을 피하려고 그림 안은 영어, 한글 설명은 Streamlit 쪽에 둔다.
"""
import io
import time

import matplotlib
matplotlib.use("Agg")          # 헤드리스에서도 안전. 파일로 저장하지 않고 bytes 로만 쓴다.
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from ui import dp_sim


# ── 재생 파라미터 ──────────────────────────────────
# 재생 '속도'를 조절하려면 FRAME_INTERVAL_S 하나만 바꾸면 된다.
#   작게 → 빠르게, 크게 → 느리게. 총 길이는 (프레임 수 × 이 값) 으로 자동 결정된다.

FRAME_INTERVAL_S = 0.20  # ★ 프레임 1장당 노출 시간(초) = 재생 속도
MAX_FRAMES       = 32     # 프레임 수 상한. k 가 커도 이 이상은 솎아낸다
HEAD_FRAMES      = 0     # 앞부분은 하나씩 찍어 '점이 쌓이는' 느낌을 살린다
RENDER_COST_S    = 0.140  # 프레임 1장 렌더 실측값. 참고용 (페이싱 계산에는 안 쓴다)

# 색 — .streamlit/config.toml 테마와 맞춘다
_C_LINE = "#6366f1"   # primary
_C_DOT  = "#94a3b8"   # slate-400
_C_TRUE = "#10b981"   # success
_C_INK  = "#0f172a"   # text
_C_MUTE = "#64748b"   # slate-500
_C_GRID = "#e2e8f0"   # border


# ── 섹션 스코프 CSS ────────────────────────────────
# 전역이 아니라 .st-key-dpviz_card 안쪽만 지정한다.
# → 나중에 전역 CSS 를 한꺼번에 입힐 때 이 블록만 걷어내면 되고, 다른 화면과 충돌하지 않는다.
_CSS = """
<style>
.st-key-dpviz_card {
  border: 1px solid #e2e8f0; border-radius: 14px; background: #ffffff;
  padding: 16px 18px 10px; box-shadow: 0 1px 3px rgba(15,23,42,.05);
}
.st-key-dpviz_card .dpviz-title {
  font-size: 12px; letter-spacing: .09em; text-transform: uppercase;
  font-weight: 700; color: #64748b; margin: 0 0 2px;
}
.st-key-dpviz_card .dpviz-sub { font-size: 12px; color: #94a3b8; margin: 0 0 6px; }
</style>
"""


def inject_section_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ── 프레임 계획 ────────────────────────────────────

def frame_plan(k: int) -> list[int]:
    """프레임으로 쓸 k 목록을 만든다.

    k 가 작으면 하나씩 전부, 크면 앞 HEAD_FRAMES 개는 하나씩 두고 나머지는 등간격으로
    솎는다. → 초반의 '점이 하나씩 찍히는' 느낌은 유지하면서 프레임 수를 MAX_FRAMES
    이하로 묶는다. (총 재생 길이는 고정하지 않는다 — 프레임 수에 비례한다.)
    """
    if k <= MAX_FRAMES:
        return list(range(1, k + 1))
    head = list(range(1, HEAD_FRAMES + 1))
    tail = np.unique(
        np.linspace(HEAD_FRAMES + 1, k, MAX_FRAMES - HEAD_FRAMES).astype(int)
    ).tolist()
    plan = head + [int(v) for v in tail]
    if plan[-1] != k:
        plan[-1] = k
    return plan


def _ylim(res: dp_sim.SimResult) -> tuple[float, float]:
    """세로축을 전 프레임에 대해 고정한다.

    프레임마다 ylim 을 다시 잡으면 밴드 폭이 줄어도 화면상 똑같아 보인다.
    고정해야 '좁아지는' 것이 실제로 보인다. k=2~4 구간의 극단값에 눌리지 않도록
    분위수로 잘라 쓴다.
    """
    los = res.ci_los[np.isfinite(res.ci_los)]
    his = res.ci_his[np.isfinite(res.ci_his)]
    if len(los) == 0 or len(his) == 0:
        lo = float(min(res.noisy_responses.min(), res.true_mean))
        hi = float(max(res.noisy_responses.max(), res.true_mean))
    else:
        lo = float(min(np.percentile(los, 2), res.true_mean))
        hi = float(max(np.percentile(his, 98), res.true_mean))
    pad = (hi - lo) * 0.08 or 1.0
    ylim = (lo - pad, hi + pad)

    # [0928 수정] 유한성 보증. 여기서 막지 않으면 matplotlib 이
    #   ValueError("Axis limits cannot be NaN or Inf") 로 죽어 화면에 트레이스백이 뜬다.
    #   (원인은 dp_sim 이지만, 시각화 모듈도 자기 입력을 신뢰하면 안 된다.)
    if not all(np.isfinite(ylim)):
        raise ValueError(
            "시각화할 유한한 값이 없습니다 "
            f"(참평균 {res.true_mean!r}, Δ {res.sensitivity!r}). "
            "대상 컬럼에 결측이 섞여 있지 않은지 확인하세요."
        )
    return ylim


# ── 프레임 렌더 ────────────────────────────────────

def build_frame(res: dp_sim.SimResult, upto: int,
                ylim: tuple[float, float]) -> bytes:
    """k=upto 시점까지의 궤적을 한 장으로 그려 PNG bytes 로 돌려준다."""
    fig, ax = plt.subplots(figsize=(9.0, 4.2), dpi=110)
    fig.patch.set_facecolor("white")

    ks = res.ks[:upto]
    ax.scatter(ks, res.noisy_responses[:upto], s=15, c=_C_DOT,
               alpha=0.6, zorder=2, label="Noisy response")
    ax.plot(ks, res.cum_means[:upto], lw=1.9, c=_C_LINE, zorder=3,
            label="Cumulative mean")
    if upto >= 2:
        ax.fill_between(ks[1:], res.ci_los[1:upto], res.ci_his[1:upto],
                        color=_C_LINE, alpha=0.15, zorder=1, label="95% CI")
    ax.axhline(res.true_mean, ls="--", c=_C_TRUE, lw=1.4, zorder=4,
               label="True mean")

    # 진행 중인 지점을 눈으로 따라가게 하는 세로선
    ax.axvline(upto, color=_C_MUTE, ls=":", lw=1.0, zorder=1)

    ax.set_xlim(0, res.k + 1)
    ax.set_ylim(*ylim)
    ax.set_xlabel("Query count  k", fontsize=10, color=_C_MUTE)
    ax.set_ylabel(res.target_col, fontsize=10, color=_C_MUTE)
    ax.grid(alpha=0.28, color=_C_GRID, lw=0.7)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(_C_GRID)
    ax.tick_params(colors=_C_MUTE, labelsize=9)
    ax.legend(frameon=False, fontsize=9, loc="best")

    # 라이브 수치 — '계산이 돌고 있다'는 신호를 그림 안에 넣는다
    _cm = res.cum_means[upto - 1]
    if upto >= 2 and np.isfinite(res.ci_his[upto - 1]):
        _w = res.ci_his[upto - 1] - res.ci_los[upto - 1]
    else:
        _w = float("nan")
    _err = (abs(_cm - res.true_mean) / abs(res.true_mean) * 100
            if res.true_mean else float("nan"))
    ax.text(
        0.985, 0.975,
        f"k = {upto} / {res.k}\n"
        f"cumulative mean = {_cm:,.2f}\n"
        f"95% CI width = {_w:,.2f}\n"
        f"|error| vs true = {_err:.2f}%",
        transform=ax.transAxes, ha="right", va="top", fontsize=9.5,
        color=_C_INK, linespacing=1.5,
        bbox=dict(boxstyle="round,pad=0.45", facecolor="#f8fafc",
                  edgecolor=_C_GRID),
    )

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


# ── 재생 ──────────────────────────────────────────

def render_convergence(res: dp_sim.SimResult, state_key: str) -> None:
    """시각화 A 섹션 전체를 그린다(카드 + 애니메이션 + 다시 재생).

    state_key : 재생 완료를 세션에 기억하는 키.
        확정 버튼 등을 눌러 리런이 일어날 때마다 재생을 처음부터 다시 기다리지 않게 한다.
        (재생을 원하면 '다시 재생' 버튼으로 명시적으로 다시 돌린다.)
    """
    inject_section_css()

    with st.container(key="dpviz_card"):
        st.markdown('<div class="dpviz-title">Convergence of 95% CI</div>',
                    unsafe_allow_html=True)
        st.markdown(
            f'<div class="dpviz-sub">질의 1회당 ε = {res.eps_per_query:.2f} · '
            f'총 ε = {res.total_eps:.0f} (Risk {res.risk_level}) · '
            f'k = {res.k} 라운드 · 참평균 {res.true_mean:,.2f} · Δ {res.sensitivity:,.2f}</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "라운드마다 라플라스 노이즈가 주입된 응답(회색 점)이 누적되고, "
            "그 누적평균(보라 선)의 95% 신뢰구간(음영)이 좁아집니다. "
            "노이즈 적용 결과이며 실제 질의 응답이 아닙니다."
        )
        if res.n_dropped:
            st.caption(
                f"※ 대상 컬럼의 결측/무한 {res.n_dropped}행은 제외하고 "
                f"{res.n_rows:,}행으로 계산했습니다 (참평균도 그 기준)."
            )

        ph = st.empty()
        ylim = _ylim(res)
        plan = frame_plan(res.k)

        if st.session_state.get(state_key, False):
            ph.image(build_frame(res, res.k, ylim), width="stretch")
        else:
            # 프레임당 고정 간격으로 재생한다 (총 길이 고정이 아니다).
            #   총 길이 = len(plan) × FRAME_INTERVAL_S.
            #   실측 렌더 시간이 간격보다 길면 잠들지 않는다 — 그 이상 늦출 수 없다.
            ph.image(build_frame(res, 1, ylim), width="stretch")
            for q in plan[1:]:
                _t0 = time.perf_counter()
                ph.image(build_frame(res, q, ylim), width="stretch")
                _gap = FRAME_INTERVAL_S - (time.perf_counter() - _t0)
                if _gap > 0:
                    time.sleep(_gap)
            st.session_state[state_key] = True

        c_btn, c_txt = st.columns([1, 3.2], vertical_alignment="center")
        with c_btn:
            if st.button("↻ 다시 재생", key=f"{state_key}_replay",
                         width="stretch"):
                st.session_state[state_key] = False
                st.rerun()
        with c_txt:
            st.caption(
                f"프레임 {len(plan)}개 · 프레임당 {FRAME_INTERVAL_S * 1000:.0f}ms · "
                f"약 {len(plan) * FRAME_INTERVAL_S:.1f}초 "
                f"(렌더 실측 {RENDER_COST_S * 1000:.0f}ms/장)"
            )