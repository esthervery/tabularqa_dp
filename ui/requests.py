# """예산 추가 신청/승인 워크플로우.

# 분석가는 create() 로 신청을 남기고, 관리자는 decide() 로 결재한다.
# 승인이 통과하면 db.grant_eps() 를 호출해 해당 분석가의 개인 상한을 증액.

# Status 값
#     pending     관리자 검토 대기
#     approved    요청 그대로 승인
#     partial     관리자가 금액을 조정해 부분 승인
#     rejected    거절

# 주요 API
#     create(user, db_name, requested, reason) → 신청 id
#     list_by_user(user)                       → 분석가의 신청 목록
#     list_all(status=?, user=?)               → 관리자용 전체 조회 (필터 지원)
#     decide(req_id, reviewer, status, approved=?, note=?)  → 결재
#     stats()                                  → 상태별 카운트 스냅샷
# """
# from __future__ import annotations
# import datetime as dt
# from typing import Optional
# from ui import db


# def _now() -> str:
#     return dt.datetime.now().isoformat(timespec="seconds")


# # ── 분석가 API ────────────────────────────────────────────

# def create(username: str, db_name: str, requested: float, reason: str) -> int:
#     """신청 생성. 초기 status='pending'."""
#     with db.connect() as con:
#         cur = con.execute(
#             "INSERT INTO budget_requests "
#             "  (username, db_name, requested, reason, status, created_at) "
#             "VALUES (?, ?, ?, ?, 'pending', ?)",
#             (username, db_name, float(requested), reason.strip(), _now()),
#         )
#         return int(cur.lastrowid)


# def list_by_user(username: str) -> list[dict]:
#     """이 분석가가 낸 신청들, 최근순."""
#     with db.connect() as con:
#         rows = con.execute(
#             "SELECT * FROM budget_requests WHERE username = ? "
#             "ORDER BY id DESC", (username,)
#         ).fetchall()
#     return [dict(r) for r in rows]


# # ── 관리자 API ────────────────────────────────────────────

# def list_all(status: Optional[str] = None,
#              user: Optional[str] = None) -> list[dict]:
#     """전체 신청 조회. pending 이 먼저, 그 뒤 최근순."""
#     q = "SELECT * FROM budget_requests WHERE 1=1"
#     params: list = []
#     if status and status != "전체":
#         q += " AND status = ?"
#         params.append(status)
#     if user:
#         q += " AND username LIKE ?"
#         params.append(f"%{user}%")
#     q += " ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, id DESC"

#     with db.connect() as con:
#         rows = con.execute(q, params).fetchall()
#     return [dict(r) for r in rows]


# def decide(req_id: int, *, reviewer: str, status: str,
#            approved: float = 0.0, note: str = "") -> dict:
#     """결재.
#     status ∈ {approved, partial, rejected}.
#     approved > 0 이면 신청자 users.eps_cap 을 그만큼 증액한다.
#     """
#     assert status in {"approved", "partial", "rejected"}
#     with db.connect() as con:
#         row = con.execute(
#             "SELECT * FROM budget_requests WHERE id = ?", (req_id,)
#         ).fetchone()
#         if row is None:
#             raise ValueError(f"request {req_id} not found")
#         if row["status"] != "pending":
#             raise ValueError(f"request {req_id} already decided ({row['status']})")

#         con.execute(
#             "UPDATE budget_requests SET "
#             "  status = ?, approved = ?, admin_note = ?, "
#             "  reviewer = ?, reviewed_at = ? "
#             "WHERE id = ?",
#             (status, float(approved), note.strip(), reviewer, _now(), req_id),
#         )

#     if approved > 0 and status in ("approved", "partial"):
#         db.grant_eps(row["username"], float(approved))

#     return {"id": req_id, "status": status, "approved": approved,
#             "target_user": row["username"]}


# def stats() -> dict:
#     """상태별 카운트: {'pending': N, 'approved': N, 'partial': N, 'rejected': N}."""
#     with db.connect() as con:
#         rows = con.execute(
#             "SELECT status, COUNT(*) c FROM budget_requests GROUP BY status"
#         ).fetchall()
#     out = {"pending": 0, "approved": 0, "partial": 0, "rejected": 0}
#     for r in rows:
#         out[r["status"]] = int(r["c"])
#     return out



### 0919 수정
"""예산 추가 신청/승인 워크플로우.

분석가는 create() 로 리스크 업그레이드 신청을 남기고,
관리자는 decide() 로 결재. 승인이 통과하면 db.set_user_override() 를
호출해 (사용자 × DB) 개인 오버라이드가 생성된다.

Status 값
    pending     관리자 검토 대기
    approved    요청 그대로 승인
    partial     관리자가 레벨을 조정해 부분 승인 (요청보다 낮은 레벨)
    rejected    거절

주요 API
    create(user, db, current_level, requested_level, reason) → 신청 id
    list_by_user(user)                       → 분석가의 신청 목록
    list_all(status=?, user=?)               → 관리자용 전체 조회
    decide(req_id, reviewer, status, approved_level=?, note=?)
    stats()                                  → 상태별 카운트 스냅샷
"""
from __future__ import annotations
import datetime as dt
from typing import Optional
from ui import db


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


# ── 분석가 API ────────────────────────────────────────────

def create(username: str, db_name: str,
           current_level: int, requested_level: int,
           reason: str) -> int:
    """신청 생성. 초기 status='pending'."""
    if requested_level <= current_level:
        raise ValueError("requested_level 은 current_level 보다 높아야 합니다.")
    if requested_level not in db.RISK_TO_EPSILON:
        raise ValueError(f"requested_level 은 1..5 만 지원: {requested_level}")

    with db.connect() as con:
        cur = con.execute(
            "INSERT INTO budget_requests "
            "  (username, db_name, current_level, requested_level, "
            "   reason, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (username, db_name, int(current_level), int(requested_level),
             reason.strip(), _now()),
        )
        return int(cur.lastrowid)


def list_by_user(username: str) -> list[dict]:
    """이 분석가가 낸 신청들, 최근순."""
    with db.connect() as con:
        rows = con.execute(
            "SELECT * FROM budget_requests WHERE username = ? "
            "ORDER BY id DESC", (username,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── 관리자 API ────────────────────────────────────────────

def list_all(status: Optional[str] = None,
             user: Optional[str] = None) -> list[dict]:
    """전체 신청 조회. pending 이 먼저, 그 뒤 최근순."""
    q = "SELECT * FROM budget_requests WHERE 1=1"
    params: list = []
    if status and status != "전체":
        q += " AND status = ?"
        params.append(status)
    if user:
        q += " AND username LIKE ?"
        params.append(f"%{user}%")
    q += " ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, id DESC"

    with db.connect() as con:
        rows = con.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def decide(req_id: int, *, reviewer: str, status: str,
           approved_level: int | None = None,
           note: str = "") -> dict:
    """결재.
    status ∈ {approved, partial, rejected}.
    approved_level 이 설정되고 status 가 approved/partial 이면
    db.set_user_override() 로 개인 오버라이드가 기록된다.
    """
    assert status in {"approved", "partial", "rejected"}

    with db.connect() as con:
        row = con.execute(
            "SELECT * FROM budget_requests WHERE id = ?", (req_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"request {req_id} not found")
        if row["status"] != "pending":
            raise ValueError(
                f"request {req_id} already decided ({row['status']})"
            )

        con.execute(
            "UPDATE budget_requests SET "
            "  status = ?, approved_level = ?, admin_note = ?, "
            "  reviewer = ?, reviewed_at = ? "
            "WHERE id = ?",
            (status,
             int(approved_level) if approved_level is not None else None,
             note.strip(), reviewer, _now(), req_id),
        )

    # 승인이면 사용자 오버라이드 생성
    if status in ("approved", "partial") and approved_level is not None:
        if approved_level > row["current_level"]:
            db.set_user_override(
                username=row["username"],
                db_name=row["db_name"],
                risk_level=int(approved_level),
                approver=reviewer,
                budget_request_id=int(req_id),
                note=note.strip() or None,
            )

    return {
        "id": req_id,
        "status": status,
        "approved_level": approved_level,
        "target_user": row["username"],
        "db_name": row["db_name"],
    }


def stats() -> dict:
    """상태별 카운트: {'pending':N, 'approved':N, 'partial':N, 'rejected':N}."""
    with db.connect() as con:
        rows = con.execute(
            "SELECT status, COUNT(*) c FROM budget_requests GROUP BY status"
        ).fetchall()
    out = {"pending": 0, "approved": 0, "partial": 0, "rejected": 0}
    for r in rows:
        out[r["status"]] = int(r["c"])
    return out