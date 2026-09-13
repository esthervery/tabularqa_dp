import streamlit as st


DEFAULTS = {
    "authenticated": False,
    "username": None,
    "is_admin": False,              # ε 관리자 여부
    "db_name": "CardBase",          # 질의 대상 DB
    "query_type": "mean",
    "messages": [],                 # 채팅 히스토리

    # ── 예산 상태 (분석가 세션)
    "eps": 0.5,                     # 질의당 ε (정책에서 로드)
    "eps_cap": 10.0,                # 개인 상한 (users.eps_cap 에서 로드)
    "eps_alloc": 2.0,               # 이번 라운드 배정 예산 (관리자 실험용)
    "spent": 0.0,                   # 누적 소모 (세션 내)
    "target_rel_width": 0.01,
    "step": 1.2,

    # ── 관리자 실험용 draft (privacy 페이지 로컬 위젯 값)
    "draft_eps": 0.5,
    "draft_eps_cap": 10.0,
    "draft_target_rel_width": 0.01,
    "draft_step": 1.2,
    "policy_loaded": False,         # 페이지 첫 진입 시 draft/active 로드 트리거

    "rounds_by_scope": {},          # {"db_name/query_type": [round dict, ...]}
    "audit": [],
    "pipe": None,

    "pending_q": None,
    "manual_code": "    return df.shape[0]",
    "last_result": None,
    "_last_trace": None,
}


def init():
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v)


def logout():
    for k in DEFAULTS:
        st.session_state.pop(k, None)
    init()


def log(kind: str, detail: str, cost: float = 0.0):
    import datetime as dt
    st.session_state.audit.append({
        "time": dt.datetime.now().strftime("%H:%M:%S"),
        "user": st.session_state.username,
        "kind": kind, "detail": detail, "eps_spent": cost,
    })


def apply_active_policy(db_name: str | None = None,
                        query_type: str | None = None) -> dict:
    """현재 (또는 지정된) (DB, query_type) 조합의 활성 정책을 세션에 반영."""
    from ui import db as _db
    db_name    = db_name    or st.session_state.get("db_name", "")
    query_type = query_type or st.session_state.get("query_type", "mean")

    pol = _db.get_active_policy(db_name, query_type)
    st.session_state.eps              = pol["eps_per_query"]
    st.session_state.target_rel_width = pol["target_rel_width"]
    st.session_state.step             = pol["step"]

    u = st.session_state.get("username")
    if u:
        st.session_state.eps_cap = _db.get_eps_cap(u)
    else:
        st.session_state.eps_cap = pol["eps_cap_default"]
    return pol


def can_spend(cost: float) -> bool:
    return st.session_state.spent + cost <= st.session_state.eps_cap + 1e-12


def spend(cost: float, kind: str, detail: str) -> bool:
    """상한을 넘으면 거절. 원장은 여기서만 갱신한다."""
    if not can_spend(cost):
        return False
    st.session_state.spent += cost
    log(kind, detail, cost=cost)
    return True