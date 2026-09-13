"""데모용 계정 & 예산 신청 & 운영 정책 저장소.

분석 대상 데이터(parquet)와는 완전히 분리된 SQLite 파일.
- users: 로그인 계정 + 사용자별 개인 ε 상한
- budget_requests: 분석가가 예산 증액을 신청하고 관리자가 결재하는 워크플로우
- dp_policy: 관리자가 실험 후 '확정' 한 운영 규칙 (분석가 계정 전체에 적용)
"""
import datetime as dt
import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "dp_demo.db"
ITERATIONS = 200_000

# 지원하는 질의 유형. 이 값은 policy 스코프, agent_qa 드롭다운에 모두 쓰인다.
QUERY_TYPES = ("mean", "count", "sum", "variance", "max")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username    TEXT PRIMARY KEY,
    salt        TEXT NOT NULL,
    pw_hash     TEXT NOT NULL,
    is_admin    INTEGER NOT NULL DEFAULT 0,
    eps_cap     REAL NOT NULL DEFAULT 10.0,
    created_at  TEXT NOT NULL,
    last_login  TEXT
);

CREATE TABLE IF NOT EXISTS budget_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT NOT NULL,
    db_name      TEXT NOT NULL,
    requested    REAL NOT NULL,
    reason       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    approved     REAL,
    admin_note   TEXT,
    reviewer     TEXT,
    created_at   TEXT NOT NULL,
    reviewed_at  TEXT
);
CREATE INDEX IF NOT EXISTS ix_req_user   ON budget_requests(username);
CREATE INDEX IF NOT EXISTS ix_req_status ON budget_requests(status);

-- 운영 정책. 관리자가 privacy 페이지에서 실험 후 '확정' 하면 여기 스냅샷으로 남고
-- 그 시점부터 모든 분석가에게 적용된다. 확정 레코드가 하나도 없으면 DEFAULT_POLICY 사용.
CREATE TABLE IF NOT EXISTS dp_policy (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    db_name           TEXT NOT NULL,
    query_type        TEXT NOT NULL,      -- mean|count|sum|variance|max
    is_draft          INTEGER NOT NULL DEFAULT 1,   -- 1=실험중, 0=확정
    eps_per_query     REAL NOT NULL,
    eps_cap_default   REAL NOT NULL,
    target_rel_width  REAL NOT NULL,
    step              REAL NOT NULL,
    admin             TEXT,
    updated_at        TEXT NOT NULL,
    confirmed_at      TEXT,
    note              TEXT
);
CREATE INDEX IF NOT EXISTS ix_policy_scope
    ON dp_policy(db_name, query_type, is_draft);
"""

# 확정된 정책이 없을 때 fallback.
DEFAULT_POLICY = {
    "id":               None,
    "db_name":          "*",     # 의미상 fallback (매치 안 됨)
    "query_type":       "*",
    "is_draft":         False,
    "eps_per_query":    0.5,
    "eps_cap_default": 10.0,
    "target_rel_width": 0.01,
    "step":             1.2,
    "admin":            None,
    "updated_at":       None,
    "confirmed_at":     None,
    "note":             "default (해당 (DB, query_type) 조합에 확정된 정책이 없음)",
}


@contextmanager
def connect():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _ensure_column(con, table: str, col: str, ddl: str) -> None:
    cur = con.execute(f"PRAGMA table_info({table})")
    if col not in {r[1] for r in cur.fetchall()}:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init(seed_demo: bool = True) -> None:
    with connect() as con:
        con.executescript(SCHEMA)
        _ensure_column(con, "users", "eps_cap",
                       "eps_cap REAL NOT NULL DEFAULT 10.0")

        # dp_policy 의 새 컬럼 마이그레이션 (기존 스키마에 없으면 추가).
        # 기존 레코드에는 임시 값 '__legacy__' 가 들어가지만, 매치되지
        # 않으므로 자연스레 DEFAULT_POLICY 로 fallback 된다.
        _ensure_column(con, "dp_policy", "db_name",
                       "db_name TEXT NOT NULL DEFAULT '__legacy__'")
        _ensure_column(con, "dp_policy", "query_type",
                       "query_type TEXT NOT NULL DEFAULT '__legacy__'")

        if seed_demo:
            if not user_exists("analyst"):
                create_user("analyst", "demo1234", is_admin=False)
            if not user_exists("admin"):
                create_user("admin",   "admin1234", is_admin=True)

    if seed_demo:
        if not user_exists("analyst"):
            create_user("analyst", "demo1234", is_admin=False)
        if not user_exists("admin"):
            create_user("admin",   "admin1234", is_admin=True)


def _derive(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"),
        bytes.fromhex(salt_hex), ITERATIONS,
    ).hex()


# ── users ────────────────────────────────────────────────────────────

def user_exists(username: str) -> bool:
    with connect() as con:
        return con.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone() is not None


def create_user(username: str, password: str,
                is_admin: bool = False,
                eps_cap: float | None = None) -> tuple[bool, str]:
    username = username.strip()
    if not username or not password:
        return False, "아이디와 비밀번호를 입력하세요."
    if len(password) < 8:
        return False, "비밀번호는 8자 이상이어야 합니다."
    # 신규 사용자 초기 상한 = 시스템 기본 정책의 eps_cap_default.
    # (DB×query_type 조합별 정책은 실 사용 시점에 조회되므로 여기선
    #  스코프를 특정하지 않는다.)
    if eps_cap is None:
        eps_cap = DEFAULT_POLICY["eps_cap_default"]
    salt = secrets.token_hex(16)
    try:
        with connect() as con:
            con.execute(
                "INSERT INTO users "
                "  (username, salt, pw_hash, is_admin, eps_cap, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (username, salt, _derive(password, salt), int(is_admin),
                 float(eps_cap),
                 dt.datetime.now().isoformat(timespec="seconds")),
            )
    except sqlite3.IntegrityError:
        return False, "이미 존재하는 아이디입니다."
    return True, "가입이 완료되었습니다."


def verify(username: str, password: str):
    """성공하면 {'username', 'is_admin', 'eps_cap'}, 실패하면 None."""
    with connect() as con:
        row = con.execute(
            "SELECT username, salt, pw_hash, is_admin, eps_cap "
            "FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if row is None:
        _derive(password, "0" * 32)   # 존재 여부로 응답 시간이 갈리지 않게
        return None

    if not hmac.compare_digest(_derive(password, row["salt"]), row["pw_hash"]):
        return None

    with connect() as con:
        con.execute(
            "UPDATE users SET last_login = ? WHERE username = ?",
            (dt.datetime.now().isoformat(timespec="seconds"), row["username"]),
        )

    return {
        "username": row["username"],
        "is_admin": bool(row["is_admin"]),
        "eps_cap":  float(row["eps_cap"]),
    }


def get_eps_cap(username: str) -> float:
    with connect() as con:
        row = con.execute(
            "SELECT eps_cap FROM users WHERE username = ?", (username,)
        ).fetchone()
    return float(row["eps_cap"]) if row else 10.0


def grant_eps(username: str, extra: float) -> float:
    """개인 상한을 `extra` 만큼 증액하고 새 상한 반환.
    관리자의 예산 신청 승인 시 사용. 운영 정책과는 무관하다."""
    with connect() as con:
        con.execute(
            "UPDATE users SET eps_cap = eps_cap + ? WHERE username = ?",
            (float(extra), username),
        )
        row = con.execute(
            "SELECT eps_cap FROM users WHERE username = ?", (username,)
        ).fetchone()
    return float(row["eps_cap"]) if row else 0.0


def list_users() -> list[sqlite3.Row]:
    with connect() as con:
        return con.execute(
            "SELECT username, is_admin, eps_cap, created_at, last_login "
            "FROM users ORDER BY created_at"
        ).fetchall()


# ── policy (운영 규칙) ────────────────────────────────────────────────
# 흐름:
#   1) 관리자가 privacy 페이지에서 슬라이더/라운드 실험 → save_draft()
#      (is_draft=1 레코드가 관리자별로 하나 유지됨)
#   2) 결과가 만족스러우면 [확정] → confirm_draft()
#      → is_draft=0 으로 승격, 그 시점부터 분석가에게 적용
#   3) 확정된 정책이 하나도 없으면 DEFAULT_POLICY 가 fallback.

def _row_to_policy(row) -> dict:
    return {
        "id":               row["id"],
        "db_name":          row["db_name"],
        "query_type":       row["query_type"],
        "is_draft":         bool(row["is_draft"]),
        "eps_per_query":    float(row["eps_per_query"]),
        "eps_cap_default":  float(row["eps_cap_default"]),
        "target_rel_width": float(row["target_rel_width"]),
        "step":             float(row["step"]),
        "admin":            row["admin"],
        "updated_at":       row["updated_at"],
        "confirmed_at":     row["confirmed_at"],
        "note":             row["note"],
    }


def get_active_policy(db_name: str, query_type: str) -> dict:
    """(db_name, query_type) 조합의 활성(확정) 정책.
    없으면 DEFAULT_POLICY 를 db_name/query_type 만 채워 반환."""
    with connect() as con:
        row = con.execute(
            "SELECT * FROM dp_policy "
            "WHERE is_draft = 0 AND db_name = ? AND query_type = ? "
            "ORDER BY confirmed_at DESC, id DESC LIMIT 1",
            (db_name, query_type),
        ).fetchone()
    if row is None:
        pol = dict(DEFAULT_POLICY)
        pol["db_name"]    = db_name
        pol["query_type"] = query_type
        return pol
    return _row_to_policy(row)


def list_active_policies() -> dict:
    """{(db_name, query_type): policy_dict} 매트릭스 뷰용."""
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM dp_policy WHERE is_draft = 0 "
            "ORDER BY db_name, query_type, confirmed_at DESC"
        ).fetchall()
    out = {}
    for r in rows:
        key = (r["db_name"], r["query_type"])
        if key in out:      # 최신 confirmed_at 하나만 유지
            continue
        out[key] = _row_to_policy(r)
    return out


def get_draft_policy(admin: str, db_name: str, query_type: str) -> dict:
    """관리자의 (db, qt) 실험용 draft. 없으면 현재 active(또는 default) 로 seed."""
    with connect() as con:
        row = con.execute(
            "SELECT * FROM dp_policy "
            "WHERE is_draft = 1 AND admin = ? "
            "  AND db_name = ? AND query_type = ? "
            "ORDER BY id DESC LIMIT 1",
            (admin, db_name, query_type),
        ).fetchone()
    if row is not None:
        return _row_to_policy(row)
    seed = get_active_policy(db_name, query_type)
    seed["is_draft"]  = True
    seed["admin"]     = admin
    seed["id"]        = None
    return seed


def list_draft_policies(admin: str) -> list[dict]:
    """관리자가 현재 갖고 있는 모든 draft (배치 확정용 큐)."""
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM dp_policy WHERE is_draft = 1 AND admin = ? "
            "ORDER BY db_name, query_type",
            (admin,),
        ).fetchall()
    return [_row_to_policy(r) for r in rows]


def save_draft(admin: str, *, db_name: str, query_type: str,
               eps_per_query: float, eps_cap_default: float,
               target_rel_width: float, step: float,
               note: str | None = None) -> int:
    """관리자당 (db, qt) draft 1건 유지. 있으면 UPDATE, 없으면 INSERT."""
    now = dt.datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        row = con.execute(
            "SELECT id FROM dp_policy "
            "WHERE is_draft = 1 AND admin = ? "
            "  AND db_name = ? AND query_type = ?",
            (admin, db_name, query_type),
        ).fetchone()
        if row is None:
            cur = con.execute(
                "INSERT INTO dp_policy "
                "  (db_name, query_type, is_draft, "
                "   eps_per_query, eps_cap_default, "
                "   target_rel_width, step, admin, updated_at, note) "
                "VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)",
                (db_name, query_type,
                 float(eps_per_query), float(eps_cap_default),
                 float(target_rel_width), float(step),
                 admin, now, note),
            )
            return int(cur.lastrowid)
        con.execute(
            "UPDATE dp_policy SET "
            "  eps_per_query = ?, eps_cap_default = ?, "
            "  target_rel_width = ?, step = ?, updated_at = ?, note = ? "
            "WHERE id = ?",
            (float(eps_per_query), float(eps_cap_default),
             float(target_rel_width), float(step), now, note,
             int(row["id"])),
        )
        return int(row["id"])


def confirm_draft(admin: str, db_name: str, query_type: str,
                  note: str | None = None) -> dict:
    """단일 (db, qt) draft 를 활성 정책으로 승격."""
    now = dt.datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        row = con.execute(
            "SELECT * FROM dp_policy "
            "WHERE is_draft = 1 AND admin = ? "
            "  AND db_name = ? AND query_type = ? "
            "ORDER BY id DESC LIMIT 1",
            (admin, db_name, query_type),
        ).fetchone()
        if row is None:
            raise ValueError(
                f"확정할 draft 가 없습니다: {db_name}/{query_type}"
            )
        con.execute(
            "UPDATE dp_policy SET is_draft = 0, confirmed_at = ?, "
            "  note = COALESCE(?, note) "
            "WHERE id = ?",
            (now, note, int(row["id"])),
        )
        active = con.execute(
            "SELECT * FROM dp_policy WHERE id = ?", (int(row["id"]),),
        ).fetchone()
    return _row_to_policy(active)


def confirm_all_drafts(admin: str,
                       note: str | None = None) -> list[dict]:
    """관리자가 만든 모든 draft 를 한꺼번에 승격 (배치 확정)."""
    drafts = list_draft_policies(admin)
    return [
        confirm_draft(admin, d["db_name"], d["query_type"], note=note)
        for d in drafts
    ]


def discard_draft(admin: str,
                  db_name: str | None = None,
                  query_type: str | None = None) -> None:
    """db_name/query_type 을 지정하면 그 조합만, 둘 다 None 이면 전체 draft 삭제."""
    q = "DELETE FROM dp_policy WHERE is_draft = 1 AND admin = ?"
    params: list = [admin]
    if db_name is not None:
        q += " AND db_name = ?"
        params.append(db_name)
    if query_type is not None:
        q += " AND query_type = ?"
        params.append(query_type)
    with connect() as con:
        con.execute(q, params)


def policy_history(limit: int = 20,
                   db_name: str | None = None,
                   query_type: str | None = None) -> list[dict]:
    q = "SELECT * FROM dp_policy WHERE is_draft = 0"
    params: list = []
    if db_name:
        q += " AND db_name = ?"
        params.append(db_name)
    if query_type:
        q += " AND query_type = ?"
        params.append(query_type)
    q += " ORDER BY confirmed_at DESC LIMIT ?"
    params.append(int(limit))
    with connect() as con:
        rows = con.execute(q, params).fetchall()
    return [_row_to_policy(r) for r in rows]