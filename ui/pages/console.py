"""질의 콘솔 — 자연어 질의 → 가드레일 → ε 예산 → 에이전트 코드 → DP 응답.

화면은 design/platform_v14.html 의 '질의 콘솔'을 Streamlit 으로 옮긴 것이다.

구성 (위→아래)
    상단 바
    밴드 헤더 : 질의 대상(데이터셋) 선택 · 예산 신청 · ε 도넛
    필드 힌트 : 종류만 노출하는 카드 스트립 (건수·비율·최소·최대 없음)
    대화      : 질문 / 생성 코드 / DP 응답
    입력      : st.chat_input (화면 하단 고정)

질의 1건의 처리 순서는 기획서의 '접근 경로 단일화'를 그대로 따른다.
    guardrail → state.can_spend → agent_bridge → state.record_query
어느 단계에서 막혀도 eps_spent=0 으로 기록해 감사 추적은 남긴다.
"""
from __future__ import annotations

import os

import streamlit as st

from ui import agent_bridge as ab
from ui import catalog, db, design, fields, guardrail, hints, state

try:                      # dp_sim 은 scipy 가 필요하다 — 없어도 콘솔은 떠야 한다
    from ui import dp_sim
    EPS = float(EPS)
except Exception:         # noqa: BLE001
    dp_sim = None
    EPS = 0.1

ORD = [k for k, v in fields.SPECS.items() if v.get("enabled")]
TL = {k: fields.SPECS[k]["title"] for k in ORD}


# ── 가드레일 정책 주입 ──────────────────────────────────
# guardrail.DATASET_POLICY 는 원래 000_CardBase 만 갖고 있다.
# 데모 데이터셋 4종은 ui/fields.py 스펙이 정본이므로, 그 스펙에서 정책을 만들어
# 주입한다. (guardrail.py 자체를 고치지 않아도 되고, 스펙과 정책이 어긋나지 않는다.)

def _inject_policies() -> None:
    for name in ORD:
        if name in guardrail.DATASET_POLICY:
            continue
        s = fields.SPECS[name]
        cols = {s["measure"]["col"]:
                "수치형 — 통계 질의 대상 (평균·중앙값·최소·최대·합계·표준편차·분위수 등)"}
        enum: list[str] = []
        for c in s["cat"]:
            cols[c["col"]] = ("범주형 — 고유값(종류) 열거 허용, 집단 구분 기준으로 사용 가능")
            enum.append(c["col"])
        for c in s["fil"]:
            cols[c["col"]] = "수치형 — 필터·구간 조건으로 사용 (값 자체 열거는 금지)"
        for c in s["pat"]:
            cols[c["col"]] = "이진 결과 — 집단 구분 기준으로 사용 가능"
        guardrail.DATASET_POLICY[name] = {"columns": cols, "value_enum_ok": enum}


def _guardrail_on() -> bool:
    """데모에서 LLM 판정을 끄고 싶으면 DP_GUARDRAIL=off (기본값 on)."""
    return os.getenv("DP_GUARDRAIL", "on").strip().lower() not in ("off", "0", "false", "no")


# ── 렌더 ────────────────────────────────────────────────

def render() -> None:
    design.inject()
    _inject_policies()
    is_admin = bool(st.session_state.get("is_admin"))
    st.markdown(design.topbar("질의 콘솔", "Admin" if is_admin else "Workspace"),
                unsafe_allow_html=True)

    if st.session_state.get("db_name") not in ORD:
        st.session_state.db_name = ORD[0]
    cur = st.session_state.db_name

    _band_head(cur)
    _band_body(cur)
    _thread(cur)
    _composer(cur)


def _band_head(cur: str) -> None:
    """데이터셋 선택 · 예산 신청 · ε 도넛."""
    total = float(st.session_state.get("total_epsilon") or 2.0)
    spent = state.spent_of(cur)
    eps = float(st.session_state.get("eps") or EPS)
    remain = max(0, int((total - spent) / eps + 1e-9))

    left, right = st.columns([3.05, 1.35], vertical_alignment="center")
    with left:
        pick = st.selectbox(
            "질의 대상", ORD, index=ORD.index(cur),
            format_func=lambda k: f"{TL.get(k, k)}  ·  {k}",
            label_visibility="collapsed", key="ds_pick",
        )
        if pick != cur:
            st.session_state.db_name = pick
            state.reset_console()
            st.rerun()

    with right:
        b, d = st.columns([1.05, 1], vertical_alignment="center")
        with b:
            if st.button("↓ 예산 신청", key="to_budget", use_container_width=True):
                st.switch_page("ui/pages/budget_request.py")
        with d:
            st.markdown(
                design.donut(spent / total if total else 0.0,
                             f"{spent:.2f} / {total:.2f} ε",
                             f"잔여 {remain}회"),
                unsafe_allow_html=True,
            )


def _band_body(cur: str) -> None:
    """필드 힌트 스트립. 카드 순서는 조건 → 수치형 → 이진."""
    cards = hints.cards_of(cur)
    if not cards:
        return
    meta = hints.load().get(cur) or {}
    sub = f"노출 {len(cards)}필드 · 측정 대상 {meta.get('measure', {}).get('label', '')}"
    st.markdown(design.band("필드 힌트", sub, [design.field_card(f) for f in cards]),
                unsafe_allow_html=True)


def _thread(cur: str) -> None:
    msgs = st.session_state.get("messages") or []
    if not msgs:
        st.markdown(design.empty("아직 대화가 없습니다 — 아래에 통계량 질의를 입력하세요"),
                    unsafe_allow_html=True)
        _suggestions(cur)
        return

    blocks: list[str] = []
    for m in msgs:
        blocks.append(design.bubble_user(m.get("q", ""), m.get("meta", "")))
        if m.get("err"):
            blocks.append('<div class="msg a"><div class="av">D</div><div class="bub">'
                          + design.warn(m["err"]) + "</div></div>")
        else:
            blocks.append(design.bubble_agent(
                m.get("code"), m.get("ans", ""),
                label=m.get("label", "결과"), eps=m.get("eps")))
    st.markdown('<div class="thread">' + "".join(blocks) + "</div>", unsafe_allow_html=True)


def _suggestions(cur: str) -> None:
    """예시 질의 2개 — 스펙의 첫 패턴/필터 컬럼으로 문장을 만든다."""
    spec = fields.SPECS.get(cur, {})
    pat = (spec.get("pat") or [{}])[0]
    fil = (spec.get("fil") or [{}])[0]
    meas = spec.get("measure", {})
    if not meas:
        return
    qs = [
        f"{pat.get('label', '')}에 따라 {meas.get('label', '')} 중앙값이 얼마나 차이 나?",
        f"{fil.get('label', '')} 조건을 더 걸어서 다시 봐줘",
    ]
    cols = st.columns(len(qs))
    for c, q in zip(cols, qs):
        with c:
            if st.button(q, key=f"sg_{q[:12]}", use_container_width=True):
                st.session_state.pending_q = q
                st.rerun()


def _composer(cur: str) -> None:
    spec = fields.SPECS.get(cur, {})
    pat = (spec.get("pat") or [{}])[0]
    meas = spec.get("measure", {})
    ph = (f"자연어로 통계량을 질의하세요 — 예: {pat.get('label', '조건')}에 따른 "
          f"{meas.get('label', '값')} 중앙값")

    q = st.session_state.pop("pending_q", None)
    typed = st.chat_input(ph)
    if typed:
        q = typed
    if q:
        _answer(cur, q)


# ── 질의 처리 ────────────────────────────────────────────

def _answer(cur: str, q: str) -> None:
    user = st.session_state.get("username") or "analyst"
    eps = float(st.session_state.get("eps") or EPS)
    meas = fields.SPECS[cur]["measure"]

    # 1) 가드레일 — 통계량 질의만 통과 (fail-closed)
    if _guardrail_on():
        try:
            verdict = guardrail.check(q, cur)
            if not getattr(verdict, "allowed", True):
                msg = (verdict.user_message() if hasattr(verdict, "user_message")
                       else "이 질의는 통계량 질의가 아니어서 차단되었습니다.")
                _push(q, err=msg)
                db.log_query(user, cur, q, f"[blocked] {msg}", ok=False, eps_spent=0.0)
                st.rerun()
        except Exception as e:  # 판정 실패 = 차단 (fail-closed)
            msg = f"가드레일 판정에 실패해 질의를 차단했습니다 ({type(e).__name__})."
            _push(q, err=msg)
            db.log_query(user, cur, q, f"[blocked] {msg}", ok=False, eps_spent=0.0)
            st.rerun()

    # 2) ε 예산
    if not state.can_spend(eps, cur):
        msg = (f"이 데이터셋의 ε 예산을 모두 사용했습니다 "
               f"({state.spent_of(cur):.2f} / {float(st.session_state.total_epsilon):.2f}). "
               f"예산 신청으로 리스크 레벨 상향을 요청하세요.")
        _push(q, err=msg)
        db.log_query(user, cur, q, f"[blocked] {msg}", ok=False, eps_spent=0.0)
        st.rerun()

    # 3) 에이전트 — 코드 생성 → 실행
    box = st.empty()
    acc = ""
    try:
        for chunk in ab.stream_code(q, cur):
            acc += chunk
            box.markdown('<div class="thread">' + design.bubble_user(q) +
                         design.bubble_agent(acc, "") + "</div>", unsafe_allow_html=True)

        trace = st.session_state.get("_last_trace") or {}
        code = trace.get("code") or acc
        ans = trace.get("output")
        if ans is None:
            raise RuntimeError("에이전트가 결과를 반환하지 않았습니다.")
        ans_s = str(ans)
        if ans_s.startswith("__CODE_ERROR__") or ans_s.startswith("__TIMEOUT__"):
            _push(q, code=code, err=f"코드 실행 실패 · {ans_s.split(':', 1)[-1].strip()[:160]}")
            db.log_query(user, cur, q, f"[error] {ans_s}", code=code, ok=False, eps_spent=0.0)
        else:
            _push(q, code=code, ans=ans_s, label=meas["label"])
            state.record_query(q, ans_s, code=code, ok=True, db_name=cur)
    except ab.PipelineUnavailable as e:
        msg = f"에이전트 파이프라인을 사용할 수 없습니다 — {e.reason}"
        _push(q, err=msg)
        db.log_query(user, cur, q, f"[blocked] {msg}", ok=False, eps_spent=0.0)
    except Exception as e:
        msg = f"질의를 처리하지 못했습니다 ({type(e).__name__}: {e})"
        _push(q, err=msg)
        db.log_query(user, cur, q, f"[error] {msg}", ok=False, eps_spent=0.0)
    finally:
        box.empty()

    st.rerun()


def _push(q: str, *, code: str | None = None, ans: str = "",
          label: str = "결과", err: str | None = None) -> None:
    msgs = st.session_state.setdefault("messages", [])
    msgs.append({
        "q": q, "code": code, "ans": ans, "label": label, "err": err,
        "eps": float(st.session_state.get("eps") or EPS) if not err else None,
        "meta": f"{st.session_state.get('db_name')} · {len(msgs) + 1}번째 질의",
    })
