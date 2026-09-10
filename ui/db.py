"""데모용 계정 저장소. 분석 대상 데이터(parquet)와는 완전히 분리된 파일이다."""
import datetime as dt
import hashlib
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
import hmac

DB_PATH = Path(__file__).resolve().parent.parent / "dp_demo.db"
ITERATIONS = 200_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username   TEXT PRIMARY KEY,
    salt       TEXT NOT NULL,
    pw_hash    TEXT NOT NULL,
    is_admin   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_login TEXT
);
"""


@contextmanager
def connect():
    """호출마다 새 커넥션. Streamlit 이 스크립트를 스레드에서 재실행하므로
    커넥션을 전역/캐시로 들고 있지 않는다."""
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init(seed_demo: bool = True):
    with connect() as con:
        con.executescript(SCHEMA)
    if seed_demo and not user_exists("analyst"):
        create_user("analyst", "demo1234")


def _derive(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"),
        bytes.fromhex(salt_hex), ITERATIONS
    ).hex()


def user_exists(username: str) -> bool:
    with connect() as con:
        return con.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone() is not None


def create_user(username: str, password: str, is_admin: bool = False) -> tuple[bool, str]:
    username = username.strip()
    if not username or not password:
        return False, "아이디와 비밀번호를 입력하세요."
    if len(password) < 8:
        return False, "비밀번호는 8자 이상이어야 합니다."
    salt = secrets.token_hex(16)
    try:
        with connect() as con:
            con.execute(
                "INSERT INTO users (username, salt, pw_hash, is_admin, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (username, salt, _derive(password, salt), int(is_admin),
                dt.datetime.now().isoformat(timespec="seconds")),
            )
    except sqlite3.IntegrityError:
        return False, "이미 존재하는 아이디입니다."
    return True, "가입이 완료되었습니다."


def verify(username: str, password: str):
    """성공하면 {"username": ..., "is_admin": ...}, 실패하면 None."""
    with connect() as con:
        row = con.execute(
            "SELECT username, salt, pw_hash, is_admin FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if row is None:
        _derive(password, "no-such-user")   # 존재 여부로 응답 시간이 갈리지 않게
        return None

    uname, salt, pw_hash, is_admin = row[0], row[1], row[2], row[3]

    if not hmac.compare_digest(_derive(password, salt), pw_hash):
        return None

    with connect() as con:
        con.execute(
            "UPDATE users SET last_login = ? WHERE username = ?",
            (dt.datetime.now().isoformat(timespec="seconds"), uname),
        )
        con.commit()

    return {"username": uname, "is_admin": bool(is_admin)}


def list_users() -> list[sqlite3.Row]:
    with connect() as con:
        return con.execute(
            "SELECT username, is_admin, created_at, last_login FROM users "
            "ORDER BY created_at"
        ).fetchall()