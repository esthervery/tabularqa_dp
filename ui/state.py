"""세션 상태 & ε 원장.

Streamlit 은 매 rerun 마다 스크립트를 처음부터 다시 실행하므로,
페이지 간에 공유해야 하는 값은 모두 st.session_state 에 넣는다.

[0923 수정] 예산을 데이터셋 단위로 분리
    이전에는 소모 ε 을 세션 단일 스칼라(spent)로만 들고 있어서
    데이터셋을 바꿔도 누적 소모가 그대로 넘어갔다 (= 데이터셋 구분 없이 쌓임).
    이제 소모 ε 과 질의 기록은 SQLite 의 query_log 에 (계정 × 데이터셋) 단위로
    남기고, 세션은 "지금 선택된 데이터셋"의 값을 조회해서 보여주기만 한다.

    · 누적 소모 ε  = query_log 의 SUM(eps_spent)   → spent_of(db)
    · 질의 횟수    = query_log 의 COUNT(*)          → queries_of(db)

주요 API
    init()                     - 첫 실행 시 기본값 세팅
    logout()                   - 로그아웃 (세션 초기화)
    log(kind, detail, cost)    - 감사 로그(session-local) 에 한 줄 추가
    apply_effective_policy(db) - 지정 DB 의 유효 정책(오버라이드 > 기본 > default)
                                 을 세션에 반영
    spent_of(db?)              - 해당 데이터셋의 누적 소모 ε
    queries_of(db?)            - 해당 데이터셋에 이 계정이 실행한 질의 횟수
    can_spend(cost, db?)       - 해당 데이터셋의 총 ε 예산을 넘지 않는지
    spend(cost, kind, detail)  - 상한 안이면 소비하고 로그 남김 (True/False)
    record_query(...)          - 질의·응답을 데이터셋별 history 에 기록
"""
from copy import deepcopy
import streamlit as st


DEFAULTS = {
    # 로그인 상태
    "authenticated": False,
    "username":      None,
    "is_admin":      False,

    # 현재 선택된 DB
    "db_name": "CardBase",

    # 대화/실행 기록
    "messages": [],

    # 유효 정책 (Agent Console 에서 사용 · 선택된 데이터셋 기준)
    "eps":           0.1,      # 질의당 ε (dp_sim.EPS_PER_QUERY 와 동일)
    "risk_level":    1,        # 유효 리스크 레벨
    "total_epsilon": 2.0,      # 유효 총 ε (도넛 게이지 분모)

    # Privacy 페이지 - 모달 상태
    "policy_modal_open":  False,
    "policy_modal_level": None,   # 미리보기 중인 레벨 (1..5)

    # Budget Requests 페이지 - Agent 콘솔에서 넘어올 때 프리셋
    "req_prefill_db":    None,    # 자동 선택될 대상 DB (넘어온 컨텍스트)
    "req_prefill_level": None,    # 자동 선택될 요청 레벨 (없으면 current+1)

    # 감사 로그 (session-local)
    "audit": [],

    # LLM 파이프라인 캐시
    "pipe": None,

    # 콘솔 상태
    "input_mode":  None,       # "agent" | "manual" | None(아직 선택 안 함)
    "pending_q":   None,
    "manual_code": "    return df.shape[0]",
    "last_result": None,
    "_last_trace": None,
}


def init() -> None:
    """앱 진입 시 한 번 호출. 이미 있는 키는 건드리지 않는다."""
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, deepcopy(v))


def logout() -> None:
    """세션 상태를 지우고 로그인 전 상태로 되돌린다.

    소모 ε 과 질의 기록은 SQLite(query_log)에 있으므로 세션을 지워도 보존된다.
    """
    for k in list(st.session_state):
        del st.session_state[k]
    init()


# [0928 수정] 데이터셋 전환 시 콘솔 영역 초기화
def reset_console() -> None:
    """이전 데이터셋에서 받아온 콘솔 영역의 코드·결과를 비운다.

    데이터셋 selectbox 의 on_change 콜백으로 호출된다.
    콜백은 스크립트 재실행 "전"에 실행되므로, 본문에서 조건 비교로 지우는 방식과 달리
    이전 데이터셋의 코드·결과가 한 프레임 보였다가 사라지는 깜빡임이 없다.

    주의: 이 함수는 st.session_state["db_name"] 을 읽지 않는다.
    (콜백 시점의 db_name 이 새 값인지 이전 값인지에 의존하지 않기 위함 —
     어느 쪽이든 "콘솔만 비운다"는 동작은 동일하다.)
    """
    st.session_state.manual_code = DEFAULTS["manual_code"]
    st.session_state.last_result = None
    st.session_state._last_trace = None


def log(kind: str, detail: str, cost: float = 0.0) -> None:
    """감사 로그에 한 줄 추가. audit 페이지의 액세스 로그 탭에 노출됨."""
    import datetime as dt
    st.session_state.audit.append({
        "time":      dt.datetime.now().strftime("%H:%M:%S"),
        "user":      st.session_state.username,
        "kind":      kind,      # "auth" | "query" | "manual" | "approve" | ...
        "detail":    detail,
        "eps_spent": cost,
    })


def apply_effective_policy(db_name: str | None = None) -> dict:
    """지정된 DB 의 유효 정책을 세션에 반영.

    우선순위: 사용자 오버라이드 > DB 기본 정책 > 시스템 기본값.
    Agent Console 진입/새로고침 시 호출된다.
    """
    from ui import db as _db
    from ui import dp_sim

    db_name = db_name or st.session_state.get("db_name", "")
    user = st.session_state.get("username")
    pol = _db.get_effective_policy(user, db_name)

    st.session_state.risk_level    = int(pol["risk_level"])
    st.session_state.total_epsilon = float(pol["total_epsilon"])
    st.session_state.policy_source = pol["source"]
    st.session_state.eps           = dp_sim.EPS_PER_QUERY
    return pol


# ── ε 원장 · 질의 수 (계정 × 데이터셋) ──────────────
# 값 자체는 query_log 에 있고, 여기서는 "현재 데이터셋"의 값을 꺼내온다.

def _scope(db_name: str | None) -> tuple[str, str]:
    return (st.session_state.get("username"),
            db_name or st.session_state.get("db_name"))


def spent_of(db_name: str | None = None) -> float:
    """해당 데이터셋에서 이 계정이 소모한 ε (누적)."""
    from ui import db as _db
    user, dn = _scope(db_name)
    if not user or not dn:
        return 0.0
    return _db.spent_epsilon(user, dn)


def queries_of(db_name: str | None = None) -> int:
    """해당 데이터셋에 이 계정이 실행한 질의 횟수 (응답을 받은 건만)."""
    from ui import db as _db
    user, dn = _scope(db_name)
    if not user or not dn:
        return 0
    return _db.count_queries(user, dn, only_ok=True)


def can_spend(cost: float, db_name: str | None = None) -> bool:
    """해당 데이터셋의 총 ε 예산(=유효 정책의 total_epsilon)을 넘지 않는지."""
    return spent_of(db_name) + cost <= st.session_state.total_epsilon + 1e-12


def spend(cost: float, kind: str, detail: str,
          db_name: str | None = None) -> bool:
    """상한 내면 True 반환하고 감사 로그를 남긴다. 초과면 아무것도 안 하고 False.

    실제 ε 원장 값은 record_query() 가 query_log 에 남기는 eps_spent 로 집계된다.
    (여기서는 예산 초과 여부 판정과 감사 로그만 담당한다.)
    """
    if not can_spend(cost, db_name):
        return False
    log(kind, detail, cost=cost)
    return True


def record_query(question: str, answer: str,
                 code: str | None = None, ok: bool = True,
                 db_name: str | None = None) -> int:
    """질의·응답을 데이터셋별 history 에 기록한다.

    ok=False 인 시도(실행 실패·예산 초과 차단)는 eps_spent=0 으로 남는다.
    반환값은 기록된 행 id.
    """
    from ui import db as _db
    user, dn = _scope(db_name)
    eps = float(st.session_state.eps) if ok else 0.0
    return _db.log_query(user, dn, question, answer,
                         code=code, ok=ok, eps_spent=eps)

def select_database() -> bool:
    """Validate the selection before headers and policy are rendered."""
    from ui import catalog
    if st.session_state.get("db_domain") not in catalog.domains():
        st.session_state.db_domain = "전체"
    choices = catalog.names(st.session_state.db_domain)
    if not choices:
        return False
    if st.session_state.db_name not in choices:
        st.session_state.db_name = choices[0]
    if st.session_state.get("_active_database") != st.session_state.db_name:
        reset_console()
        st.session_state.pending_q = None
        st.session_state.policy_modal_open = False
        st.session_state.policy_modal_level = None
        st.session_state.pop("policy_confirm_note", None)
        st.session_state._active_database = st.session_state.db_name
    return True
