"""프라이버시 분석 — 신뢰구간 수렴 애니메이션 (demo 브랜치).

dev-esther 의 ui/dp_viz.py 에서 필요한 부분만 옮겨 다시 썼다.

속도는 일정하게
    프레임마다 질의 QUERIES_PER_FRAME 회씩 늘리고, 간격 FRAME_INTERVAL_S 초로 고정한다.
    총 길이를 고정하지 않으므로 도중에 빨라지거나 느려지지 않는다.
        Utility 1 (k=20)  → 10프레임 · 약 2초
        Utility 5 (k=100) → 50프레임 · 약 10초
y축은 데이터셋마다 고정 (모든 Utility · 모든 프레임 공통) → 레벨 간 폭 비교가 된다.
그림 안 글자는 한글 — 시스템 한글 글꼴을 찾아 쓴다 (KO_FONT 가 None 이면 글자 깨짐).
"""
from __future__ import annotations

import io
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import numpy as np

from ui import dp_sim


# ── 조절값 ──────────────────────────────────────
QUERIES_PER_FRAME = 2        # 프레임당 늘어나는 질의 수 (작을수록 촘촘·길어짐)
FRAME_INTERVAL_S  = 0.2      # 프레임 간격(초) (작을수록 빨라짐, 렌더 시간보다 작게는 의미 없음)    
FIG_W, FIG_H = 5.6, 2.5   # 그림 비율(인치). 표시 폭은 아래 SIM_COLS 가 정한다
FIG_DPI      = 200        # 작게 표시해도 글자가 선명하도록
SIM_COLS     = [11, 9]    # 그래프 : 수치 패널 → 그래프가 카드 폭의 약 55%

PRI, SUC, DOT = "#6366f1", "#10b981", "#94a3b8"
INK, MID, GRID = "#334155", "#64748b", "#e2e8f0"

_KO_FONTS = ("Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans KR", "Noto Sans CJK KR")


def _setup_font() -> str | None:
    have = {f.name for f in fm.fontManager.ttflist}
    plt.rcParams["axes.unicode_minus"] = False       # 한글 글꼴에서 '−' 깨짐 방지
    for name in _KO_FONTS:
        if name in have:
            plt.rcParams["font.family"] = name
            return name
    return None


KO_FONT = _setup_font()


def _ylim(tr: "dp_sim.Trace") -> tuple[float, float]:
    """k=3 이후 CI + 모든 응답 + 참 평균이 들어가는 범위 (k=2 의 큰 CI 는 잘려 보이게 둔다)."""
    v = np.concatenate([tr.noisy, tr.ci_los[2:], tr.ci_his[2:], [tr.true_mean]])
    v = v[np.isfinite(v)]
    lo, hi = float(v.min()), float(v.max())
    pad = (hi - lo) * 0.08 or abs(tr.true_mean) * 0.01 or 1.0
    return lo - pad, hi + pad


def _frame(tr, k_now: int, k_tot: int, ylim, ylabel: str) -> bytes:
    ks = np.arange(1, k_now + 1)
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=FIG_DPI)
    fig.subplots_adjust(left=0.08, right=0.985, top=0.95, bottom=0.30)   # 고정 → 프레임 간 흔들림 없음

    ax.fill_between(ks, tr.ci_los[:k_now], tr.ci_his[:k_now],
                    color=PRI, alpha=0.12, lw=0, label="95% 신뢰구간")
    ax.scatter(ks, tr.noisy[:k_now], s=14, color=DOT, alpha=0.75, lw=0,
               label="노이즈 섞인 응답값", zorder=2)
    ax.plot(ks, tr.cum_means[:k_now], color=PRI, lw=2, label="추정된 평균값", zorder=3)
    ax.axhline(tr.true_mean, color=SUC, ls="--", lw=1.4, label="실제 평균값", zorder=1)
    ax.axvline(k_now, color=MID, ls=":", lw=0.8)

    ax.set_xlim(0, k_tot + 1)
    ax.set_ylim(*ylim)
    ax.set_xlabel("질의 횟수 (k)", color=MID, fontsize=9)
    ax.set_ylabel(ylabel, color=MID, fontsize=9)
    ax.tick_params(colors=MID, labelsize=8)
    ax.grid(axis="y", color=GRID, lw=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)

    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=4,
              frameon=False, fontsize=7.5, labelcolor=INK)

    buf = io.BytesIO()
    fig.savefig(buf, format="png")       # bbox_inches='tight' 금지 — 프레임마다 크기가 달라져 흔들린다
    plt.close(fig)
    return buf.getvalue()


def stats_html(tr, k_now: int, k_tot: int) -> str:
    """그래프 오른쪽 수치 패널 — 그림 밖에 두어 그래프를 가리지 않는다."""
    i = k_now - 1
    m, lo, hi = tr.cum_means[i], tr.ci_los[i], tr.ci_his[i]
    ok = np.isfinite(lo) and np.isfinite(hi)
    f = dp_sim.fmt_sig
    err = abs(m - tr.true_mean) / abs(tr.true_mean) * 100 if tr.true_mean else float("nan")
    rows = [
        ("질의 횟수", f"{k_now} / {k_tot}"),
        ("추정된 평균값", f(m, 5)),
        ("95% 신뢰구간", f"[{f(lo, 5)}, {f(hi, 5)}]" if ok else "—"),
        ("신뢰구간 폭", f(hi - lo) if ok else "—"),
        ("실제 평균값", f(tr.true_mean, 5)),
        ("실제 평균값과의 오차", f"{err:.2f}%" if np.isfinite(err) else "—"),
    ]
    return ('<div class="dpstat">'
            + "".join(f'<div class="r"><span class="k">{k}</span><b>{v}</b></div>' for k, v in rows)
            + '</div>')


def play(tr, level: int, ylabel: str, slot, info=None) -> None:
    """일정한 속도로 k=QUERIES_PER_FRAME … k_tot 까지 재생."""
    k_tot = tr.k_of(level)
    ylim = _ylim(tr)
    for k in range(QUERIES_PER_FRAME, k_tot + 1, QUERIES_PER_FRAME):
        t0 = time.perf_counter()
        slot.image(_frame(tr, k, k_tot, ylim, ylabel), width="stretch")
        if info is not None:
            info.html(stats_html(tr, k, k_tot))
        rest = FRAME_INTERVAL_S - (time.perf_counter() - t0)
        if rest > 0:
            time.sleep(rest)


def still(tr, level: int, ylabel: str, slot, info=None) -> None:
    """마지막 장면 한 장 (재생 후 다른 조작으로 rerun 될 때)."""
    k_tot = tr.k_of(level)
    slot.image(_frame(tr, k_tot, k_tot, _ylim(tr), ylabel), width="stretch")
    if info is not None:
        info.html(stats_html(tr, k_tot, k_tot))