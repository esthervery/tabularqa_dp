### 0919 수정
"""계정 · 예산 신청 · 운영 정책 저장소 (SQLite).

분석 대상 데이터(parquet)와 완전히 분리된 dp_demo.db 파일을 쓴다.

테이블 4개
    users                  로그인 계정 + 사용자별 개인 ε 상한(예산 원장 용도)
    budget_requests        분석가의 리스크 업그레이드 신청 워크플로우
                           (pending / approved / partial / rejected)
    dp_policy              DB별 기본 정책. 관리자가 [확정] 하면 저장.
                           없으면 DEFAULT_POLICY (Risk 1) 가 fallback.
    user_policy_override   (username × db_name) 개인 오버라이드.
                           예산 신청이 승인되면 여기에 기록.
                           Agent Console 진입/새로고침 시 이 값이 우선 적용.

주요 API
    init()                              스키마 준비 + 데모 계정 seed

    verify / create_user / user_exists / list_users
    get_eps_cap / grant_eps

    ── 리스크 매핑 ──
    RISK_TO_EPSILON                     {1..5: 2..10}
    epsilon_of(risk_level)              편의 함수

    ── DB 기본 정책 ──
    get_active_policy(db)               DB 기본 정책 (없으면 DEFAULT_POLICY)
    list_active_policies()              {db: policy} 매트릭스 뷰용
    confirm_policy(admin, db, risk)     DB 기본 정책 확정 (upsert)
    policy_history(limit=?)             확정 이력

    ── 사용자 오버라이드 ──
    get_user_override(user, db)         (user × db) 오버라이드 조회 (없으면 None)
    set_user_override(user, db, risk, approver, req_id?)
    get_effective_policy(user, db)      오버라이드 > 기본 > DEFAULT 순 fallback

    ── 리스크 레벨 접근 헬퍼 ──
    risk_level_of(user, db)             현재 유효 정책의 리스크 레벨
    total_epsilon_of(user, db)          현재 유효 정책의 총 ε
"""
import datetime as dt
import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "dp_demo.db"
ITERATIONS = 200_000    # pbkdf2 반복 횟수 (데모라 짧게)

# 리스크 레벨 → 총 ε (dp_sim.RISK_LEVELS 와 동일 값 유지)
RISK_TO_EPSILON: dict[int, float] = {1: 2.0, 2: 4.0, 3: 6.0, 4: 8.0, 5: 10.0}


def epsilon_of(risk_level: int) -> float:
    """리스크 레벨(1~5) → 총 ε 예산."""
    if risk_level not in RISK_TO_EPSILON:
        raise ValueError(f"risk_level 은 1..5 만 지원: {risk_level}")
    return RISK_TO_EPSILON[risk_level]


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
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username         TEXT NOT NULL,
    db_name          TEXT NOT NULL,
    current_level    INTEGER NOT NULL,      -- 신청 시점의 이 사용자 × DB 유효 레벨
    requested_level  INTEGER NOT NULL,      -- 요청하는 레벨 (current+1 이상)
    reason           TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending',
    approved_level   INTEGER,               -- 실제로 승인된 레벨
    admin_note       TEXT,
    reviewer         TEXT,
    created_at       TEXT NOT NULL,
    reviewed_at      TEXT
);
CREATE INDEX IF NOT EXISTS ix_req_user   ON budget_requests(username);
CREATE INDEX IF NOT EXISTS ix_req_status ON budget_requests(status);

-- DB 기본 정책 (관리자가 Privacy 페이지에서 확정)
CREATE TABLE IF NOT EXISTS dp_policy (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    db_name       TEXT NOT NULL,
    risk_level    INTEGER NOT NULL,
    total_epsilon REAL NOT NULL,
    admin         TEXT,
    confirmed_at  TEXT NOT NULL,
    note          TEXT
);
CREATE INDEX IF NOT EXISTS ix_policy_db ON dp_policy(db_name, confirmed_at);

-- 사용자별 오버라이드 (예산 신청 승인으로만 생성)
CREATE TABLE IF NOT EXISTS user_policy_override (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    username           TEXT NOT NULL,
    db_name            TEXT NOT NULL,
    risk_level         INTEGER NOT NULL,
    total_epsilon      REAL NOT NULL,
    approved_by        TEXT NOT NULL,      -- 승인한 관리자
    approved_at        TEXT NOT NULL,
    budget_request_id  INTEGER,            -- 승인 근거가 된 budget_requests.id
    note               TEXT
);
CREATE INDEX IF NOT EXISTS ix_override_scope
    ON user_policy_override(username, db_name);
"""


# 확정된 정책이 없을 때 fallback 으로 반환되는 시스템 기본값.
# Risk 1 (총 ε = 2.0) — 가장 보수적으로 시작.
DEFAULT_POLICY = {
    "id":            None,
    "db_name":       "*",
    "risk_level":    1,
    "total_epsilon": 2.0,
    "admin":         None,
    "confirmed_at":  None,
    "note":          "system default (no confirmed policy for this DB)",
}


# ── 커넥션 유틸 ──────────────────────────────────

@contextmanager
def connect():
    """호출마다 새 커넥션. Streamlit 이 스레드에서 스크립트를 재실행하므로
    커넥션을 전역/캐시로 들고 있지 않는다."""
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _ensure_column(con, table: str, col: str, ddl: str) -> None:
    """ALTER TABLE ADD COLUMN 을 idempotent 하게 수행."""
    cur = con.execute(f"PRAGMA table_info({table})")
    if col not in {r[1] for r in cur.fetchall()}:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init(seed_demo: bool = True) -> None:
    """스키마 준비 + (원한다면) 데모 계정 seed.

    구버전에서 넘어올 때 새 컬럼만 add 되고 옛 컬럼은 그대로 방치된다.
    dp_policy 는 스키마가 크게 바뀌었으므로, 실제 데모 전에는 dp_demo.db 를
    지우고 새로 시작하는 것을 권장.
    """
    with connect() as con:
        con.executescript(SCHEMA)
        _ensure_column(con, "users", "eps_cap",
                       "eps_cap REAL NOT NULL DEFAULT 10.0")

    if seed_demo:
        if not user_exists("analyst"):
            create_user("analyst", "demo1234", is_admin=False)
        if not user_exists("admin"):
            create_user("admin",   "admin1234", is_admin=True)


# ── 비밀번호 파생 ────────────────────────────────

def _derive(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"),
        bytes.fromhex(salt_hex), ITERATIONS,
    ).hex()


# ── users ────────────────────────────────────────

def user_exists(username: str) -> bool:
    with connect() as con:
        return con.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone() is not None


def create_user(username: str, password: str,
                is_admin: bool = False,
                eps_cap: float | None = None) -> tuple[bool, str]:
    """신규 계정 생성. 초기 eps_cap 은 DEFAULT_POLICY.total_epsilon 을 사용."""
    username = username.strip()
    if not username or not password:
        return False, "아이디와 비밀번호를 입력하세요."
    if len(password) < 8:
        return False, "비밀번호는 8자 이상이어야 합니다."
    if eps_cap is None:
        eps_cap = DEFAULT_POLICY["total_epsilon"]

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
    """로그인 검증. 성공 시 {'username', 'is_admin', 'eps_cap'}, 실패 시 None."""
    with connect() as con:
        row = con.execute(
            "SELECT username, salt, pw_hash, is_admin, eps_cap "
            "FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if row is None:
        _derive(password, "0" * 32)   # 응답 시간 편향 방지
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
    """개인 상한 조회 (users.eps_cap)."""
    with connect() as con:
        row = con.execute(
            "SELECT eps_cap FROM users WHERE username = ?", (username,)
        ).fetchone()
    return float(row["eps_cap"]) if row else 10.0


def grant_eps(username: str, extra: float) -> float:
    """개인 상한(users.eps_cap)을 extra 만큼 증액하고 새 값 반환.

    지금 스키마에서는 리스크 오버라이드가 별도 테이블로 관리되므로
    이 함수는 (호환용) 사용되지 않는다. 필요 시 참고용 지표로만.
    """
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


# ── DB 기본 정책 (dp_policy) ────────────────────
# 관리자가 Privacy 페이지에서 [✓ 확정] 하면 매번 새 행이 INSERT 되고,
# 최신 confirmed_at 을 가진 행이 "현재 활성 정책" 이 된다 (감사 이력 겸용).

def _row_to_policy(row) -> dict:
    return {
        "id":            row["id"],
        "db_name":       row["db_name"],
        "risk_level":    int(row["risk_level"]),
        "total_epsilon": float(row["total_epsilon"]),
        "admin":         row["admin"],
        "confirmed_at":  row["confirmed_at"],
        "note":          row["note"],
    }


def get_active_policy(db_name: str) -> dict:
    """이 DB의 최신 확정 정책. 없으면 DEFAULT_POLICY 를 db_name 만 채워 반환."""
    with connect() as con:
        row = con.execute(
            "SELECT * FROM dp_policy WHERE db_name = ? "
            "ORDER BY confirmed_at DESC, id DESC LIMIT 1",
            (db_name,),
        ).fetchone()
    if row is None:
        pol = dict(DEFAULT_POLICY)
        pol["db_name"] = db_name
        return pol
    return _row_to_policy(row)


def list_active_policies() -> dict:
    """{db_name: latest_policy}. 매트릭스 뷰용."""
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM dp_policy ORDER BY db_name, confirmed_at DESC"
        ).fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        if r["db_name"] not in out:
            out[r["db_name"]] = _row_to_policy(r)
    return out


def confirm_policy(admin: str, db_name: str, risk_level: int,
                   note: str | None = None) -> dict:
    """DB 기본 정책 확정. 새 행을 INSERT 하고 그 정책 dict 반환."""
    total_eps = epsilon_of(risk_level)
    now = dt.datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        cur = con.execute(
            "INSERT INTO dp_policy "
            "  (db_name, risk_level, total_epsilon, admin, confirmed_at, note) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (db_name, int(risk_level), float(total_eps),
             admin, now, note),
        )
        row = con.execute(
            "SELECT * FROM dp_policy WHERE id = ?", (int(cur.lastrowid),),
        ).fetchone()
    return _row_to_policy(row)


def policy_history(limit: int = 20,
                   db_name: str | None = None) -> list[dict]:
    """확정 이력 (최신순)."""
    q = "SELECT * FROM dp_policy WHERE 1=1"
    params: list = []
    if db_name:
        q += " AND db_name = ?"
        params.append(db_name)
    q += " ORDER BY confirmed_at DESC LIMIT ?"
    params.append(int(limit))
    with connect() as con:
        rows = con.execute(q, params).fetchall()
    return [_row_to_policy(r) for r in rows]


# ── 사용자별 오버라이드 (user_policy_override) ──
# 예산 신청 승인 시에만 생성/갱신되며, (username × db_name) 조합당 최신 하나가 유효.

def _row_to_override(row) -> dict:
    return {
        "id":                row["id"],
        "username":          row["username"],
        "db_name":           row["db_name"],
        "risk_level":        int(row["risk_level"]),
        "total_epsilon":     float(row["total_epsilon"]),
        "approved_by":       row["approved_by"],
        "approved_at":       row["approved_at"],
        "budget_request_id": row["budget_request_id"],
        "note":              row["note"],
    }


def get_user_override(username: str, db_name: str) -> dict | None:
    """이 (사용자 × DB) 의 최신 오버라이드. 없으면 None."""
    with connect() as con:
        row = con.execute(
            "SELECT * FROM user_policy_override "
            "WHERE username = ? AND db_name = ? "
            "ORDER BY approved_at DESC, id DESC LIMIT 1",
            (username, db_name),
        ).fetchone()
    return _row_to_override(row) if row else None


def set_user_override(username: str, db_name: str, risk_level: int,
                      approver: str,
                      budget_request_id: int | None = None,
                      note: str | None = None) -> dict:
    """사용자 오버라이드 새 행 INSERT (audit trail 겸용). 최신이 유효."""
    total_eps = epsilon_of(risk_level)
    now = dt.datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        cur = con.execute(
            "INSERT INTO user_policy_override "
            "  (username, db_name, risk_level, total_epsilon, "
            "   approved_by, approved_at, budget_request_id, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (username, db_name, int(risk_level), float(total_eps),
             approver, now, budget_request_id, note),
        )
        row = con.execute(
            "SELECT * FROM user_policy_override WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _row_to_override(row)


# ── 유효 정책 (effective policy) ────────────────
# 우선순위: 사용자 오버라이드 > DB 기본 정책 > DEFAULT_POLICY

def get_effective_policy(username: str | None, db_name: str) -> dict:
    """이 사용자가 이 DB 를 볼 때 실제로 적용되는 정책.

    반환 dict 에는 다음 키가 추가된다:
        source: "override" | "db_default" | "system_default"
    """
    if username:
        ov = get_user_override(username, db_name)
        if ov:
            return {
                "db_name":       db_name,
                "risk_level":    ov["risk_level"],
                "total_epsilon": ov["total_epsilon"],
                "source":        "override",
                "approved_by":   ov["approved_by"],
                "approved_at":   ov["approved_at"],
            }

    base = get_active_policy(db_name)
    return {
        "db_name":       db_name,
        "risk_level":    base["risk_level"],
        "total_epsilon": base["total_epsilon"],
        "source":        ("db_default"
                          if base.get("confirmed_at") is not None
                          else "system_default"),
        "confirmed_at":  base.get("confirmed_at"),
        "admin":         base.get("admin"),
    }


def risk_level_of(username: str | None, db_name: str) -> int:
    return int(get_effective_policy(username, db_name)["risk_level"])


def total_epsilon_of(username: str | None, db_name: str) -> float:
    return float(get_effective_policy(username, db_name)["total_epsilon"])