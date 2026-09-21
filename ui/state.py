# """세션 상태 & ε 원장.

# Streamlit 은 매 rerun 마다 스크립트를 처음부터 다시 실행하므로,
# 페이지 간에 공유해야 하는 값은 모두 st.session_state 에 넣는다.

# 주요 API
#     init()                       - 첫 실행 시 기본값 세팅
#     logout()                     - 로그아웃(세션 초기화)
#     log(kind, detail, cost)      - 감사 로그(session-local) 에 한 줄 추가
#     apply_active_policy(db, qt)  - 현재 (DB x query_type) 조합의 확정 정책을
#                                    세션에 반영 (질의당 ε, 목표 상대폭, step 등)
#     can_spend(cost)              - 개인 ε 상한을 넘지 않는지 검사
#     spend(cost, kind, detail)    - 상한 안이면 소비하고 로그 남김
# """
# import streamlit as st


# # 세션의 초기값. 존재하지 않는 키만 채우므로 재실행에도 안전하다.
# DEFAULTS = {
#     # 로그인 상태
#     "authenticated": False,
#     "username":      None,
#     "is_admin":      False,

#     # 현재 편집 중인 대상
#     "db_name":    "CardBase",
#     "query_type": "mean",         # mean|count|sum|variance|max

#     # 대화/실행 기록
#     "messages": [],               # [{"role": ..., "content": ..., "code": ...}]

#     # ε 예산 (분석가 세션)
#     "eps":              0.5,      # 질의당 ε (정책에서 로드)
#     "eps_cap":         10.0,      # 개인 상한 (users.eps_cap 에서 로드) -> 예산 증원 기능 추가되면서 생김
#     "eps_alloc":        2.0,      # 관리자 실험용 라운드 배정
#     "spent":            0.0,      # 세션 내 누적 소모
#     "target_rel_width": 0.01,
#     "step":             1.2,

#     # 관리자 draft (privacy 페이지의 슬라이더가 바인딩)
#     "draft_eps":              0.5,
#     "draft_eps_cap":         10.0,
#     "draft_target_rel_width": 0.01,
#     "draft_step":             1.2,
#     "policy_loaded": False,

#     # 실험실 라운드 로그: {"db/qt": [round_dict, ...]}
#     "rounds_by_scope": {},

#     # ===감사 로그(session-local)===
#     # {
#     #     "time":      "14:23:07",              # HH:MM:SS
#     #     "user":      "analyst",               # 현재 로그인 사용자
#     #     "kind":      "query",                 # 이벤트 종류
#     #     "detail":    "신용한도 평균은?",       # 자유 설명
#     #     "eps_spent": 0.5,                     # 이 이벤트에서 소비된 ε (없으면 0)
#     # }
#     # auth.py 로그인 성공 / agent_qa.py 에이전트 스트리밍 성공 / agent_qa.py 수동 실행 성공 
#     # budget_requests.py 신청 제출 / audit.py 관리자 승인 / audit.py 관리자 거절 
#     # privacy.py 정책 확정 / privacy.py 배치 확정 시 호출
#     "audit": [],
        

#     # LLM 파이프라인 캐시
#     "pipe": None,

#     # 콘솔 상태
#     "pending_q":   None,          # chat_input 이 넣은 질문 (다음 rerun 에서 처리)
#     "manual_code": "    return df.shape[0]",
#     "last_result": None,
#     "_last_trace": None,
# }


# # DEFAULTS에 정의된 기본값들을 st.session_state에 채워 넣되, 이미 값이 있으면 덮어쓰지 않고 그대로 듀는 초기화 함수
# def init() -> None:
#     """앱 진입 시 한 번 호출. 이미 있는 키는 건드리지 않는다."""
#     for k, v in DEFAULTS.items():
#         st.session_state.setdefault(k, v)


# def logout() -> None:
#     """세션 상태를 지우고 로그인 전 상태로 되돌린다."""
#     for k in DEFAULTS:
#         st.session_state.pop(k, None)
#     init()


# def log(kind: str, detail: str, cost: float = 0.0) -> None:
#     """감사 로그에 한 줄 추가. audit 페이지의 액세스 로그 탭에 노출됨."""
#     import datetime as dt
#     st.session_state.audit.append({
#         "time":      dt.datetime.now().strftime("%H:%M:%S"),
#         "user":      st.session_state.username,
#         "kind":      kind,      # "auth" | "query" | "manual" | "approve" | ...
#         "detail":    detail,
#         "eps_spent": cost,
#     })


# def apply_active_policy(db_name: str | None = None,
#                         query_type: str | None = None) -> dict:
#     """현재 (또는 지정된) (DB x query_type) 조합의 활성 정책을 세션에 반영.

#     확정된 정책이 없으면 db.DEFAULT_POLICY 가 fallback(정책 기본 설정값).
#     개인 상한(eps_cap)은 users.eps_cap 을 우선 참조(관리자 결재로 증액 반영).
#     """
#     from ui import db as _db
#     db_name    = db_name    or st.session_state.get("db_name", "")
#     query_type = query_type or st.session_state.get("query_type", "mean")

#     pol = _db.get_active_policy(db_name, query_type)
#         # (db, qt) 의 활성(확정) 정책. 없으면 DEFAULT_POLICY 를 pol에 반환
    
#     # pol에 들어있는 정책 정보를 세션 상태로 설정
#     st.session_state.eps              = pol["eps_per_query"]
#     st.session_state.target_rel_width = pol["target_rel_width"]
#     st.session_state.step             = pol["step"]

#     u = st.session_state.get("username")
#     if u:
#         # get_eps_cap(username)으로 개인 상한 조회 -> 세션 상태로 설정
#         st.session_state.eps_cap = _db.get_eps_cap(u)
#     else:
#         st.session_state.eps_cap = pol["eps_cap_default"]
#     return pol


# def can_spend(cost: float) -> bool:
#     """상한을 넘지 않고 소비 가능한지 확인."""
#     return st.session_state.spent + cost <= st.session_state.eps_cap + 1e-12


# def spend(cost: float, kind: str, detail: str) -> bool:
#     """상한 내면 소비하고 True 반환, 초과면 아무것도 안 하고 False."""
#     if not can_spend(cost):
#         return False
#     st.session_state.spent += cost
#     log(kind, detail, cost=cost)
#     return True



### 0919 수정
"""세션 상태 & ε 원장.

Streamlit 은 매 rerun 마다 스크립트를 처음부터 다시 실행하므로,
페이지 간에 공유해야 하는 값은 모두 st.session_state 에 넣는다.

주요 API
    init()                    - 첫 실행 시 기본값 세팅
    logout()                  - 로그아웃 (세션 초기화)
    log(kind, detail, cost)   - 감사 로그(session-local) 에 한 줄 추가
    apply_effective_policy(db)- 지정 DB 의 유효 정책(오버라이드 > 기본 > default)
                                을 세션에 반영
    can_spend(cost)           - 총 ε 예산 (=total_epsilon) 을 넘지 않는지
    spend(cost, kind, detail) - 상한 안이면 소비하고 로그 남김
"""
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

    # 유효 정책 (Agent Console 에서 사용)
    "eps":           0.1,      # 질의당 ε (dp_sim.EPS_PER_QUERY 와 동일)
    "risk_level":    1,        # 유효 리스크 레벨
    "total_epsilon": 2.0,      # 유효 총 ε (도넛 게이지 분모)
    "policy_source": "system_default",   # "override"|"db_default"|"system_default"
    "spent":         0.0,      # 세션 내 누적 소모

    # Privacy 페이지 - 모달 상태
    "policy_modal_open":  False,
    "policy_modal_level": None,   # 미리보기 중인 레벨 (1..5)

    # Budget Requests 페이지 - Agent 콘솔에서 넘어올 때 프리셋
    "req_prefill_db":    None,    # 자동 선택될 대상 DB (넘어온 컨텍스트)
    "req_prefill_level": None,    # 자동 선택될 요청 레벨 (없으면 current+1)

    # 감사 로그
    "audit": [],

    # LLM 파이프라인 캐시
    "pipe": None,

    # 콘솔 상태
    "pending_q":   None,
    "manual_code": "    return df.shape[0]",
    "last_result": None,
    "_last_trace": None,
}


def init() -> None:
    """앱 진입 시 한 번 호출. 이미 있는 키는 건드리지 않는다."""
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v)


def ensure_valid_db_name() -> None:
    """카탈로그에 없는 이전 세션 DB 선택값을 안전하게 보정한다."""
    from ui import catalog

    names = catalog.names()
    if names and st.session_state.get("db_name") not in names:
        st.session_state.db_name = names[0]


def logout() -> None:
    """세션 상태를 지우고 로그인 전 상태로 되돌린다."""
    for k in DEFAULTS:
        st.session_state.pop(k, None)
    init()


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


def can_spend(cost: float) -> bool:
    """총 ε 예산(=유효 정책의 total_epsilon)을 넘지 않는지."""
    return st.session_state.spent + cost <= st.session_state.total_epsilon + 1e-12


def spend(cost: float, kind: str, detail: str) -> bool:
    """상한 내면 소비하고 True 반환, 초과면 아무것도 안 하고 False."""
    if not can_spend(cost):
        return False
    st.session_state.spent += cost
    log(kind, detail, cost=cost)
    return True
