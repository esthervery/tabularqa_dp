"""채팅 히스토리 — (계정 × 데이터셋) 질의·응답 기록.

기본은 표(한 눈에 훑기)이고, 코드·응답 전문은 [자세히 보기] 대화상자에서 본다.
단일 출처는 SQLite 의 query_log 다.
"""
from __future__ import annotations

import streamlit as st

from ui import db, design, fields

ORD = [k for k, v in fields.SPECS.items() if v.get("enabled")]
TL = {k: fields.SPECS[k]["title"] for k in ORD}
EPS = 0.1
ALL = "전체"

COLS = (1.15, 4.6, 0.7, 0.85, 2.6, 1.05)        # 시각·질의·ε·상태·응답·상세
HEAD = ("시각", "질의", "ε", "상태", "응답", "상세")


def render() -> None:
    design.inject()
    # st.markdown(design.page_head("채팅 히스토리",
    #                              "데이터셋별 질의·응답 기록 — 감사 추적용으로 삭제되지 않습니다"),
    #             unsafe_allow_html=True)

    cur = st.session_state.get("db_name")
    if cur not in ORD:
        cur = ORD[0]

    pick = st.session_state.get("hist_ds") or ALL        # 표시용 ('전체' 또는 데이터셋 키)
    scope = None if pick == ALL else pick                # 조회용 (None = 전체)


    limit = st.selectbox("표시 개수", [20, 50, 100, 200], index=1, key="hist_limit", width=160)

    user = st.session_state.get("username") or "analyst"
    rows  = db.list_queries(user, scope, limit=int(limit))
    spent = db.spent_epsilon(user, scope)
    ok_n   = db.count_queries(user, scope, only_ok=True)
    fail_n = db.count_queries(user, scope, only_ok=False) - ok_n


    st.markdown(design.line([
        ("질의", f"{ok_n}건"),
        ("차단·실패", f"{fail_n}건"),
        ("누적 ε", f"{spent:.2f}"),
        ("데이터셋", ALL if scope is None else pick),
    ]), unsafe_allow_html=True)
    st.write("")

    if not rows:
        st.markdown(design.empty("해당 범위에 기록이 없습니다"), unsafe_allow_html=True)
        return

    _table(rows)
    _dialog(rows)


# ── 표 ────────────────────────────────────────────────
def _table(rows: list[dict]) -> None:
    # htable 로 한 번 감싸야 행 사이 gap 을 0 으로 만들고 테두리를 둘 수 있다
    with st.container(key="htable"):
        with st.container(key="hhead"):
            h = st.columns(COLS, vertical_alignment="center")
            for i, t in enumerate(HEAD):
                h[i].html(f'<div class="hcol">{t}</div>')

        for r in rows:
            ok = bool(r.get("ok"))
            eps = float(r.get("eps_spent") or 0.0)
            ans = (r.get("answer") or "").strip()
            with st.container(key=f"hrow_{r['id']}"):
                c = st.columns(COLS, vertical_alignment="center")
                c[0].html(f'<div class="hcell tm">{_t(r.get("asked_at"))}</div>')
                c[1].html(f'<div class="hcell q">{_esc(r.get("question") or "")}</div>')
                c[2].html(f'<div class="hcell mono">{eps:.2f}</div>')
                c[3].html(design.pill("허용", "success") if ok else design.pill("차단", "danger"))
                c[4].html(f'<div class="hcell ans">{_esc(_short(ans)) if ok and ans else "&ndash;"}</div>')
                if c[5].button("자세히 보기", key=f"det_{r['id']}", type="tertiary"):
                    st.session_state["hist_sel"] = int(r["id"])
                    st.rerun()


# ── 대화상자 ──────────────────────────────────────────
def _dialog(rows: list[dict]) -> None:
    sel = st.session_state.get("hist_sel")
    if sel is None:
        return
    row = next((x for x in rows if int(x["id"]) == int(sel)), None)
    if row is None:                      # 표시 개수/범위가 바뀌어 사라진 경우
        st.session_state["hist_sel"] = None
        return
    _detail(row)

def _close() -> None:
    """X / ESC / 바깥 클릭으로 닫아도 선택 상태를 지운다 (안 지우면 다음 rerun 에 다시 뜸)."""
    st.session_state["hist_sel"] = None


@st.dialog("질의 상세", width="medium", on_dismiss=_close)
def _detail(r: dict) -> None:
    label = fields.SPECS.get(r.get("db_name"), {}).get("measure", {}).get("label", "결과")
    st.html(design.history_card(
        _t(r.get("asked_at")),
        r.get("question") or "",
        r.get("code") or "",
        (r.get("answer") or "").strip(),
        ok=bool(r.get("ok")),
        eps=float(r.get("eps_spent") or 0.0),
        label=label,
    ))
    if st.button("닫기", key="hist_close"):
        st.session_state["hist_sel"] = None
        st.rerun()


# ── 헬퍼 ──────────────────────────────────────────────
def _t(v: str | None) -> str:
    if not v:
        return "-"
    return str(v).replace("T", " ")[5:19]      # '10-25 23:25:41' — 초까지

def _short(s, n: int = 44) -> str:
    v = " ".join(design.fmt_answer(s).split())  # 숫자 포맷 재사용 + 줄바꿈 정리
    return v if len(v) <= n else v[: n - 1] + "…"

def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

render()