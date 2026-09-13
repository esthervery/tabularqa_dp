"""예산 추가 신청/승인 워크플로우 저장소.

Status 값
  pending    → 관리자 검토 대기
  approved   → 요청한 만큼 전액 승인
  partial    → 관리자가 금액을 조정해 일부만 승인
  rejected   → 거절
"""
from __future__ import annotations
import datetime as dt
from typing import Optional
from ui import db


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


# ── 분석가 API ───────────────────────────────────────────────────────

def create(username: str, db_name: str, requested: float, reason: str) -> int:
    with db.connect() as con:
        cur = con.execute(
            "INSERT INTO budget_requests "
            "  (username, db_name, requested, reason, status, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (username, db_name, float(requested), reason.strip(), _now()),
        )
        return int(cur.lastrowid)


def list_by_user(username: str) -> list[dict]:
    with db.connect() as con:
        rows = con.execute(
            "SELECT * FROM budget_requests WHERE username = ? "
            "ORDER BY id DESC", (username,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── 관리자 API ───────────────────────────────────────────────────────

def list_all(status: Optional[str] = None,
             user: Optional[str] = None) -> list[dict]:
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
           approved: float = 0.0, note: str = "") -> dict:
    """status: approved|partial|rejected. approved>0 이면 사용자 eps_cap 을 증액한다."""
    assert status in {"approved", "partial", "rejected"}
    with db.connect() as con:
        row = con.execute(
            "SELECT * FROM budget_requests WHERE id = ?", (req_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"request {req_id} not found")
        if row["status"] != "pending":
            raise ValueError(f"request {req_id} already decided ({row['status']})")

        con.execute(
            "UPDATE budget_requests SET "
            "  status = ?, approved = ?, admin_note = ?, "
            "  reviewer = ?, reviewed_at = ? "
            "WHERE id = ?",
            (status, float(approved), note.strip(), reviewer, _now(), req_id),
        )

    if approved > 0 and status in ("approved", "partial"):
        db.grant_eps(row["username"], float(approved))

    return {"id": req_id, "status": status, "approved": approved,
            "target_user": row["username"]}


def stats() -> dict:
    with db.connect() as con:
        rows = con.execute(
            "SELECT status, COUNT(*) c FROM budget_requests GROUP BY status"
        ).fetchall()
    out = {"pending": 0, "approved": 0, "partial": 0, "rejected": 0}
    for r in rows:
        out[r["status"]] = int(r["c"])
    return out
