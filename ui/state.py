import streamlit as st


DEFAULTS = {
    "authenticated": False,
    "username": None,
    "is_admin": False,              # ε 관리자 여부
    "db_name": "CardBase",          # 질의 대상 DB
    "messages": [],                 # 채팅 히스토리

    # ── 예산 관리
    "eps": 0.5,                     # 질의당 ε
    "eps_cap": 10.0,                # 전체 상한 (관리자가 설정 가능한 전체 한도)
    "eps_alloc": 2.0,               # 이번 추정에 배정한 예산 (라운드마다 step 배로 커짐)
    "spent": 0.0,                   # 누적 소모 (되돌릴 수 없음)

    "target_rel_width": 0.01,
    "step": 1.2,
    "rounds": [],
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

def can_spend(cost: float) -> bool:
    return st.session_state.spent + cost <= st.session_state.eps_cap + 1e-12

def spend(cost: float, kind: str, detail: str) -> bool:
    """상한을 넘으면 거절. 원장은 여기서만 갱신한다."""
    if not can_spend(cost):
        return False
    st.session_state.spent += cost
    log(kind, detail, cost=cost)
    return True