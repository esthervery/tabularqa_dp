"""질의 콘솔 — 자연어 질의 → 가드레일 → ε 예산 → 에이전트 코드 → DP 응답.

화면은 design/platform_v14.html 의 '질의 콘솔'을 Streamlit 으로 옮긴 것이다.

구성 (위→아래)
    상단 바
    밴드 헤더 : 질의 대상(데이터셋) 선택 · 예산 신청 · ε 도넛
    필드 힌트 : 종류만 노출하는 카드 스트립 (건수·비율·최소·최대 없음)
    대화      : 질문 / 생성 코드 / DP 응답
    입력      : 본문 흐름 안의 폼 (하단 고정 오버레이 없음)

질의 1건의 처리 순서는 기획서의 '접근 경로 단일화'를 그대로 따른다.
    guardrail → state.can_spend → agent_bridge → state.record_query
어느 단계에서 막혀도 eps_spent=0 으로 기록해 감사 추적은 남긴다.
"""
from __future__ import annotations

import os
import time

import streamlit as st

from ui import agent_bridge as ab

from ui import db, design, fields, guardrail, hints, state, dp_noise
from ui import answer_explain as ax


# 질의당 ε. dp_sim 은 scipy 를 요구하므로, 없어도 화면이 뜨도록 기본값을 먼저 확정한다.
EPS = 0.1
try:
    # dp_sim 은 scipy 가 필요하다 — 없어도 콘솔은 떠야 한다
    from ui import dp_sim
    EPS = float(dp_sim.EPS_PER_QUERY)
except Exception:         # noqa: BLE001
    dp_sim = None

ORD = [k for k, v in fields.SPECS.items() if v.get("enabled")]
TL = {k: fields.SPECS[k]["title"] for k in ORD}

# 대화는 데이터셋별로 분리해 보관한다 (최근 MAX_THREAD 개만).
# 세션 전역 messages 를 쓰면 데이터셋을 바꿔도 이전 대화가 그대로 남는다.
MAX_THREAD = 10
# 타이핑 효과 총 재생 시간(초) — 코드 길이와 무관하게 이 시간 안에 끝난다.
TYPE_SECONDS = 1.7


# def _store() -> dict:
#     """대화 저장소 — (계정 → 데이터셋 → 메시지). 계정이 다르면 절대 섞이지 않는다."""
#     user = st.session_state.get("username") or "_anon"
#     return st.session_state.setdefault("threads", {}).setdefault(user, {})


# def _msgs(db: str) -> list:
#     return _store().setdefault(db, [])


def _user() -> str:
    return st.session_state.get("username") or "_anon"


def _store() -> dict:
    """대화 캐시 — (계정 → 데이터셋 → 메시지). 원본은 query_log 다."""
    return st.session_state.setdefault("threads", {}).setdefault(_user(), {})


def _totals() -> dict:
    """데이터셋별 누적 질의 수 — 계정별로 분리."""
    return st.session_state.setdefault("thread_totals", {}).setdefault(_user(), {})


def _msgs(name: str) -> list:
    """이 세션에서 처음 여는 (계정 × 데이터셋)이면 query_log 에서 최근 대화를 복원한다."""
    store = _store()
    if name not in store:
        store[name] = _load_thread(name)
    return store[name]


_FAIL = ("[blocked]", "[error]")


def _load_thread(name: str) -> list:
    """query_log → 콘솔 메시지 목록 (오래된 것 → 최신 순). 로그인 계정 것만 조회된다."""
    user = _user()
    rows = db.list_queries(user, name, limit=MAX_THREAD)[::-1]   # 최신순으로 오므로 뒤집는다
    total = db.count_queries(user, name, only_ok=False)
    _totals()[name] = total
    start = total - len(rows)

    out = []
    for i, r in enumerate(rows):
        ok = bool(r.get("ok"))
        ans = (r.get("answer") or "").strip()
        err = None
        if not ok:
            for p in _FAIL:                       # history_card 와 같은 접두어 규칙
                if ans.startswith(p):
                    ans = ans[len(p):].strip()
            err, ans = (ans or "실행하지 못했습니다"), ""
        out.append({
            "q": r.get("question") or "",
            "code": r.get("code") or "",
            "ans": ans,
            "label": "결과",
            "err": err,
            "note": (ax.template(ax.fmt_value(ans),
                                 unit=fields.SPECS[name]["measure"].get("unit") or "",
                                 eps=float(r.get("eps_spent") or 0.0),
                                 noised=float(r.get("eps_spent") or 0.0) > 0)
                     if ok and ans else None),
            "eps": float(r.get("eps_spent") or 0.0) if ok else None,
            "meta": f"{name} · {start + i + 1}번째 질의",
            "fresh": False,                       # 복원분은 타이핑 효과 없음
        })
    return out


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
                "수치형 — 통계 질의 대상 (평균·중앙값·최댓값·최솟값과 그 차이)"}
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

    if st.session_state.get("db_name") not in ORD:
        st.session_state.db_name = ORD[0]
    cur = st.session_state.db_name

    _band(cur)
    with st.container(height=500, border=False, autoscroll=True, key="convo"):
        _thread(cur)
    _composer(cur)


def _band(cur: str) -> None:
    """왼쪽: 통계 대상 · ε 예산 도넛 카드 / 오른쪽: 필드 힌트 카드."""
    total = float(st.session_state.get("total_epsilon") or 2.0)
    spent = state.spent_of(cur)
    eps = float(st.session_state.get("eps") or EPS)
    remain = max(0, int((total - spent) / eps + 1e-9))

    is_admin = bool(st.session_state.get("is_admin"))
    rel   = "ui/pages/budget_admin.py" if is_admin else "ui/pages/budget_request.py"
    link  = "예산 관리" if is_admin else "예산 신청"
    title = "예산 관리"   if is_admin else "예산 신청"
    target = st.session_state.get("page_map", {}).get(rel)

    meta = hints.load().get(cur) or {}
    mlabel = (meta.get("measure", {}).get("label")
              or fields.SPECS[cur]["measure"]["label"])

    with st.container(key="cband"):                       # ← 바깥: 테두리 없음
        # 가로 컨테이너 — distribute: 안의 요소가 모두 같은 행 높이로 늘어난다
        with st.container(horizontal=True, vertical_alignment="distribute",
                          gap="small", wrap=False, key="cbrow"):
            # 왼쪽: 폭 고정 (높이는 CSS 가 행 높이에 맞춘다)
            with st.container(key="cbright", width=250):  # ← height="stretch" 제거
                # 제목 줄: 통계 대상(왼쪽) ↔ 예산 링크(오른쪽)
                with st.container(horizontal=True, horizontal_alignment="distribute",
                                  vertical_alignment="center", key="cbhead"):
                    st.html(f'<div class="mtarget">통계 대상 <b>{mlabel}</b></div>',
                            width="content")
                    if st.button(link, key="to_budget", type="tertiary",
                                 disabled=target is None):
                        st.session_state.nav_active = title
                        st.switch_page(target)
                # 도넛 묶음 카드 — 남은 높이는 CSS(flex)로 채운다
                with st.container(key="cbring", border=True,   # ← height="stretch" 제거
                                  vertical_alignment="center"):
                    # SVG 는 st.html(DOMPurify)에서 제거되므로 st.markdown 으로 렌더링한다
                    st.markdown(design.budget_meter(spent, total, remain, size=84),
                                unsafe_allow_html=True, width="stretch")
            # 오른쪽: 남은 폭 전부
            with st.container(key="cbhint", width="stretch"):
                _band_body(cur)


def _band_body(cur: str) -> None:
    """필드 힌트 스트립. 카드 순서는 조건 → 수치형 → 이진."""
    cards = hints.cards_of(cur)
    if not cards:
        return
    meta = hints.load().get(cur) or {}
    sub = f"노출 {len(cards)}필드"
    st.markdown(design.band("필드 힌트", sub, [design.field_card(f) for f in cards]),
                unsafe_allow_html=True)


def _thread(cur: str) -> None:
    full = _msgs(cur)
    msgs = full[-MAX_THREAD:]          # 표시 상한 (저장은 _push 에서도 자른다)
    if not msgs:
        st.markdown(design.empty("아직 대화가 없습니다 — 아래에 통계량 질의를 입력하세요"),
                    unsafe_allow_html=True)
        _suggestions(cur)
        return

    user = st.session_state.get("username") or "_anon"
    totals = _totals().get(cur, len(msgs))

    if totals > len(msgs):
        st.html(
            f'<div class="dim" style="font-size:9px;text-align:center;padding:2px 0 6px">'
            f'이전 {totals - len(msgs)}개 질의는 채팅 히스토리에서 볼 수 있습니다 '
            f'(화면에는 최근 {len(msgs)}개)</div>'
        )

    # 말풍선마다 st.html 로 따로 그린다 (st.markdown + 빈 줄 → 태그 노출 버그 방지)
    for m in msgs:
        st.html(design.bubble_user(m.get("q", ""), m.get("meta", "")))
        if m.get("err"):
            st.html(design.agent_error(m["err"]))
        elif m.pop("fresh", False):          # 방금 받은 응답 — 한 번만 타이핑 재생
            _type_out(m)
        else:
            st.html(design.agent_card(m.get("code"), m.get("ans", ""),
                                      label=m.get("label", "결과"), eps=m.get("eps")))
        if m.get("note") and not m.get("err"):
            st.html(design.agent_note(m["note"]))


def _type_out(m: dict) -> None:
    """코드를 한 글자씩 써 내려간 뒤 결과 영역을 붙인다."""
    code = m.get("code") or ""
    kw = {"label": m.get("label", "결과"), "eps": m.get("eps")}
    box = st.empty()
    frames = max(1, min(90, len(code)))
    step = max(1, -(-len(code) // frames))   # 올림 나눗셈
    delay = TYPE_SECONDS / frames
    for i in range(step, len(code), step):
        box.html(design.agent_card(code[:i], typing=True, **kw))
        time.sleep(delay)
    box.html(design.agent_card(code, m.get("ans", ""), **kw))


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
    """입력줄 — st.bottom(공식 하단 고정 영역)에 폼을 둔다.

    st.bottom 은 Streamlit 이 관리하는 영역이라 직접 만든 fixed 오버레이와 다르다.
    단, 질의 처리(_answer)는 본문에서 호출해야 '작성 중' 카드가 대화 흐름 안에 뜬다.
    """
    spec = fields.SPECS.get(cur, {})
    pat = (spec.get("pat") or [{}])[0]
    meas = spec.get("measure", {})
    ph = (f"자연어로 통계량을 질의하세요 — 예: {pat.get('label', '조건')}에 따른 "
          f"{meas.get('label', '값')} 중앙값")

    q = st.session_state.pop("pending_q", None)
    if q:
        _answer(cur, q)

    with st.bottom:                                   # ← 폼만 하단 고정 영역으로
        with st.form("composer", clear_on_submit=True, border=False):
            c1, c2 = st.columns([1, 0.13], vertical_alignment="bottom")
            with c1:
                typed = st.text_input("질의", value="", placeholder=ph,
                                      label_visibility="collapsed", key="q_input")
            with c2:
                sent = st.form_submit_button("질의", type="primary",
                                             use_container_width=True)
    if sent:                                          # ← 처리는 본문에서
        text = (typed or "").strip()
        if text:
            _answer(cur, text)


# ── 질의 처리 ────────────────────────────────────────────

def _answer(cur: str, q: str) -> None:
    user = st.session_state.get("username") or "analyst"
    eps = float(st.session_state.get("eps") or EPS)
    meas = fields.SPECS[cur]["measure"]

    # 1) 가드레일 — 허용 여부 + 질의코드 (fail-closed)
    #    질의코드가 없으면 노이즈 Δ 를 정할 수 없으므로, 가드레일을 끈 상태에서는 질의를 받지 않는다.
    if not _guardrail_on():
        _block(user, cur, q, "가드레일이 꺼져 있어 노이즈 유형을 정할 수 없습니다 — DP_GUARDRAIL 을 켜 주세요.")
    verdict = guardrail.check(q, cur)            # 예외를 던지지 않는다 (실패는 내부에서 차단 처리)
    if not verdict.allowed:
        _block(user, cur, q, verdict.user_message())
    qcode = verdict.code

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
        # 응답을 기다리는 동안엔 '작성 중' 카드만 보여주고, 실제 타이핑은 리런 후 _thread 에서 재생
        box.html(design.bubble_user(q) + design.agent_pending())
        for chunk in ab.stream_code(q, cur):
            acc += chunk

        trace = st.session_state.pop("_last_trace", None) or {}
        code = trace.get("code") or acc
        ans = trace.get("output")
        if ans is None:
            raise RuntimeError("에이전트가 결과를 반환하지 않았습니다.")
        ans_s = str(ans)
        if ans_s.startswith("__CODE_ERROR__") or ans_s.startswith("__TIMEOUT__"):
            print(f"[exec-error] user={user} db={cur}: {ans_s}")   # 상세는 터미널에만
            msg = "코드를 실행하지 못했습니다. 질문을 바꿔 다시 시도해 주세요."
            _push(q, code=code, err=msg)
            db.log_query(user, cur, q, f"[error] {msg}", code=code, ok=False, eps_spent=0.0)
        else:
            unit = meas.get("unit") or ""
            if st.session_state.get("is_admin"):
                # 관리자 — 노이즈 없이 원본 정답. ε 도 차감하지 않는다(DP 응답이 아니므로).
                note = ax.explain(q, ans_s, qcode=qcode, measure=meas["label"],
                                  unit=unit, eps=0.0, noised=False)
                _push(q, code=code, ans=ans_s, label=f'{meas["label"]} · 원본', eps=0.0, note=note)
                db.log_query(user, cur, q, ans_s, code=code, ok=True, eps_spent=0.0)
            else:
                try:
                    dp = dp_noise.privatize(ans, qcode, cur, eps)
                except dp_noise.NoiseError as e:      # 노이즈를 못 붙이면 응답을 내보내지 않는다
                    _push(q, code=code, err=f"DP 노이즈를 적용하지 못해 응답을 보류했습니다 — {e}")
                    db.log_query(user, cur, q, f"[error] noise: {e}", code=code, ok=False, eps_spent=0.0)
                else:
                    noisy = str(dp["value"])
                    # LLM 에는 노이즈를 붙인 값만 넘긴다
                    note = ax.explain(q, dp["value"], qcode=qcode, measure=meas["label"],
                                      unit=unit, eps=eps, noised=True)
                    _push(q, code=code, ans=noisy, label=meas["label"], note=note)
                    state.record_query(q, noisy, code=code, ok=True, db_name=cur)


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


def _block(user: str, cur: str, q: str, msg: str) -> None:
    """차단 — 화면에 남기고 감사 기록(ε 0)을 쓴 뒤 리런한다."""
    _push(q, err=msg)
    db.log_query(user, cur, q, f"[blocked] {msg}", ok=False, eps_spent=0.0)
    st.rerun()


def _push(q: str, *, code: str | None = None, ans: str = "",
          label: str = "결과", err: str | None = None,
          eps: float | None = None, note: str | None = None) -> None:
    db = st.session_state.get("db_name")
    msgs = _msgs(db)
    msgs.append({
        "q": q, "code": code, "ans": ans, "label": label, "err": err, "note": note,
        "eps": (float(st.session_state.get("eps") or EPS) if eps is None else eps) if not err else None,
        "meta": f"{db} · {len(msgs) + 1}번째 질의",
        "fresh": err is None,          # 다음 렌더에서 한 번만 타이핑 효과
    })
    # 표시 상한 — 넘치면 오래된 것부터 버린다 (기록은 query_log 에 남아 있다).
    totals = _totals()
    totals[db] = totals.get(db, 0) + 1
    if len(msgs) > MAX_THREAD:
        del msgs[:-MAX_THREAD]


# Streamlit 은 페이지 파일을 '스크립트'로 실행한다 — render() 를 직접 호출해야 한다.
render()