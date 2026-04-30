"""Local SQLite users and session signing material."""

from __future__ import annotations

import logging
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import MutableMapping
from typing import Any

import bcrypt

from backend.infrastructure import sqlite_store

logger = logging.getLogger(__name__)

MIN_PASSWORD_LEN = 8
MIN_USERNAME_LEN = 2
MAX_USERNAME_LEN = 64

TIER_NONE = "none"
TIER_BASIC = "basic"
TIER_PREMIUM = "premium"
_VALID_TIERS = frozenset({TIER_NONE, TIER_BASIC, TIER_PREMIUM})


class UserAlreadyExistsError(Exception):
    """Raised when ``username`` is already registered."""


class UsageQuotaExceeded(Exception):
    """Daily report quota exceeded for this principal."""


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or sqlite_store.default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    sqlite_store.init_db(conn)
    return conn


def get_or_create_session_secret(db_path: Path | None = None) -> str:
    """Return persisted signing secret for ``SessionMiddleware`` (created on first use)."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM app_meta WHERE key = ?",
            ("session_secret",),
        ).fetchone()
        if row and row[0]:
            return str(row[0])
        secret = secrets.token_hex(32)
        conn.execute(
            "INSERT INTO app_meta (key, value) VALUES (?, ?)",
            ("session_secret", secret),
        )
        conn.commit()
        logger.info("Generated new session signing secret in app_meta")
        return secret
    finally:
        conn.close()


def normalize_membership_tier(raw: str) -> str:
    t = raw.strip().lower()
    if t not in _VALID_TIERS:
        raise ValueError(f"membership_tier must be one of: {', '.join(sorted(_VALID_TIERS))}")
    return t


def daily_limit_for_tier(tier: str) -> int | None:
    """None means unlimited (premium)."""
    if tier == TIER_PREMIUM:
        return None
    if tier == TIER_BASIC:
        return 50
    return 10


def _utc_date_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def ensure_anon_principal(session: MutableMapping[str, Any]) -> None:
    """Assign a stable anonymous principal id for quota attribution (session cookie)."""
    if session.get("anon_principal_id"):
        return
    session["anon_principal_id"] = secrets.token_urlsafe(24)


def principal_key_for_session(session: MutableMapping[str, Any]) -> str:
    """Return ``user:<id>`` when logged in, else ``anon:<token>``."""
    if session.get("authenticated") and session.get("user_id") is not None:
        return f"user:{int(session['user_id'])}"
    ensure_anon_principal(session)
    return f"anon:{str(session['anon_principal_id'])}"


def effective_tier_for_session(
    session: MutableMapping[str, Any], db_path: Path | None = None
) -> str:
    if not session.get("authenticated") or session.get("user_id") is None:
        return TIER_NONE
    row = get_user_by_id(int(session["user_id"]), db_path=db_path)
    if row is None:
        return TIER_NONE
    return normalize_membership_tier(str(row["membership_tier"]))


def get_user_by_id(user_id: int, db_path: Path | None = None) -> dict[str, Any] | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT id, username, is_admin, membership_tier, created_at
            FROM users WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": int(row[0]),
            "username": str(row[1]),
            "is_admin": bool(row[2]),
            "membership_tier": str(row[3]),
            "created_at": str(row[4]),
        }
    finally:
        conn.close()


def get_report_usage_today(
    principal_key: str, tier: str, db_path: Path | None = None
) -> int:
    limit = daily_limit_for_tier(tier)
    if limit is None:
        return 0
    today = _utc_date_str()
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT count FROM daily_report_usage
            WHERE principal_key = ? AND usage_date = ?
            """,
            (principal_key, today),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def try_consume_report_slot(
    principal_key: str, tier: str, db_path: Path | None = None
) -> None:
    """Increment daily usage once; raises ``UsageQuotaExceeded`` if limit reached."""
    limit = daily_limit_for_tier(tier)
    if limit is None:
        return
    today = _utc_date_str()
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT count FROM daily_report_usage
            WHERE principal_key = ? AND usage_date = ?
            """,
            (principal_key, today),
        ).fetchone()
        current = int(row[0]) if row else 0
        if current >= limit:
            conn.rollback()
            raise UsageQuotaExceeded
        if row is None:
            conn.execute(
                """
                INSERT INTO daily_report_usage (principal_key, usage_date, count)
                VALUES (?, ?, 1)
                """,
                (principal_key, today),
            )
        else:
            conn.execute(
                """
                UPDATE daily_report_usage SET count = count + 1
                WHERE principal_key = ? AND usage_date = ?
                """,
                (principal_key, today),
            )
        conn.commit()
    except UsageQuotaExceeded:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def count_users(db_path: Path | None = None) -> int:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def create_user(
    username: str,
    password: str,
    *,
    is_admin: bool,
    membership_tier: str = TIER_NONE,
    db_path: Path | None = None,
) -> int:
    norm = username.strip()
    if len(norm) < MIN_USERNAME_LEN or len(norm) > MAX_USERNAME_LEN:
        raise ValueError(
            f"Username length must be between {MIN_USERNAME_LEN} and {MAX_USERNAME_LEN}"
        )
    if len(password) < MIN_PASSWORD_LEN:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LEN} characters")
    tier = normalize_membership_tier(membership_tier)
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, is_admin, membership_tier, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (norm, hashed, 1 if is_admin else 0, tier, now),
        )
        conn.commit()
        return int(cur.lastrowid)
    except sqlite3.IntegrityError as e:
        raise UserAlreadyExistsError(norm) from e
    finally:
        conn.close()


def verify_user(
    username: str, password: str, db_path: Path | None = None
) -> dict[str, object] | None:
    norm = username.strip()
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT id, username, is_admin, membership_tier, password_hash
            FROM users WHERE username = ? COLLATE NOCASE
            """,
            (norm,),
        ).fetchone()
        if row is None:
            return None
        user_id, uname, is_admin, m_tier, pw_hash = (
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
        )
        if not isinstance(pw_hash, (bytes, memoryview)):
            return None
        if not bcrypt.checkpw(password.encode("utf-8"), bytes(pw_hash)):
            return None
        return {
            "id": int(user_id),
            "username": str(uname),
            "is_admin": bool(is_admin),
            "membership_tier": normalize_membership_tier(str(m_tier)),
        }
    finally:
        conn.close()


def list_users(db_path: Path | None = None) -> list[dict[str, object]]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, username, is_admin, membership_tier, created_at
            FROM users ORDER BY id ASC
            """
        ).fetchall()
        return [
            {
                "id": int(r[0]),
                "username": str(r[1]),
                "is_admin": bool(r[2]),
                "membership_tier": str(r[3]),
                "created_at": str(r[4]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def count_admins(db_path: Path | None = None) -> int:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM users WHERE is_admin = 1",
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def update_user(
    user_id: int,
    *,
    membership_tier: str | None = None,
    is_admin: bool | None = None,
    password: str | None = None,
    db_path: Path | None = None,
) -> bool:
    """Persist field updates. Returns True if a row was updated."""
    sets: list[str] = []
    args: list[Any] = []
    if membership_tier is not None:
        sets.append("membership_tier = ?")
        args.append(normalize_membership_tier(membership_tier))
    if is_admin is not None:
        sets.append("is_admin = ?")
        args.append(1 if is_admin else 0)
    if password is not None:
        if len(password) < MIN_PASSWORD_LEN:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LEN} characters")
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
        sets.append("password_hash = ?")
        args.append(hashed)
    if not sets:
        raise ValueError("No fields to update")
    args.append(user_id)
    sql = f"UPDATE users SET {', '.join(sets)} WHERE id = ?"
    conn = _connect(db_path)
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_user(user_id: int, db_path: Path | None = None) -> bool:
    conn = _connect(db_path)
    try:
        cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
