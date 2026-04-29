from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.constants import PLANS


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass
class PaymentRecord:
    id: int
    user_id: int
    plan_key: str
    amount: int
    status: str
    payment_ref: str
    proof_text: str


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    timezone TEXT,
                    last_seen TEXT,
                    created_at TEXT NOT NULL,
                    is_banned INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    plan_key TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payment_ref TEXT NOT NULL,
                    proof_text TEXT,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    approved_by TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    plan_key TEXT NOT NULL,
                    start_at TEXT NOT NULL,
                    end_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, key),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_users_tg ON users(telegram_id);
                CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id);
                CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
                CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, created_at);
                """
            )

    def upsert_user(
        self,
        telegram_id: int,
        username: Optional[str],
        first_name: Optional[str],
        tz: Optional[str] = None,
    ) -> int:
        now = utcnow_iso()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO users (telegram_id, username, first_name, timezone, last_seen, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username=excluded.username,
                    first_name=excluded.first_name,
                    timezone=COALESCE(users.timezone, excluded.timezone),
                    last_seen=excluded.last_seen
                """,
                (telegram_id, username, first_name, tz, now, now),
            )
            row = conn.execute(
                "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()
            return int(row["id"])

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()

    def get_user_by_id(self, user_id: int) -> Optional[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def get_user_by_username(self, username: str) -> Optional[sqlite3.Row]:
        norm = username.lstrip("@").strip().lower()
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE lower(username) = ?", (norm,)
            ).fetchone()

    def update_last_seen(self, user_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET last_seen = ? WHERE id = ?",
                (utcnow_iso(), user_id),
            )

    def set_timezone(self, user_id: int, tz: str) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE users SET timezone = ? WHERE id = ?", (tz, user_id))

    def is_banned(self, user_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT is_banned FROM users WHERE id = ?", (user_id,)).fetchone()
            return bool(row and row["is_banned"])

    def ban_user_by_handle_or_id(self, value: str) -> bool:
        with self._conn() as conn:
            if value.isdigit():
                res = conn.execute(
                    "UPDATE users SET is_banned = 1 WHERE telegram_id = ?",
                    (int(value),),
                )
            else:
                res = conn.execute(
                    "UPDATE users SET is_banned = 1 WHERE lower(username) = ?",
                    (value.lstrip("@").lower(),),
                )
            return res.rowcount > 0

    def create_payment(self, user_id: int, plan_key: str, payment_ref: str) -> int:
        amount = PLANS[plan_key].price_inr
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO payments (user_id, plan_key, amount, status, payment_ref, proof_text, created_at)
                VALUES (?, ?, ?, 'pending', ?, '', ?)
                """,
                (user_id, plan_key, amount, payment_ref, utcnow_iso()),
            )
            return int(cur.lastrowid)

    def attach_payment_proof(self, user_id: int, proof: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM payments WHERE user_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if not row:
                return False
            conn.execute(
                "UPDATE payments SET proof_text = ? WHERE id = ?",
                (proof, row["id"]),
            )
            return True

    def _activate_subscription(self, conn: sqlite3.Connection, user_id: int, plan_key: str) -> None:
        now = datetime.now(timezone.utc)
        start_at = now
        active = conn.execute(
            """
            SELECT * FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY id DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if active:
            current_end = parse_iso(active["end_at"])
            if current_end > now:
                start_at = current_end
            conn.execute(
                "UPDATE subscriptions SET status = 'expired' WHERE id = ?",
                (active["id"],),
            )

        end_at = start_at + PLANS[plan_key].duration
        conn.execute(
            """
            INSERT INTO subscriptions (user_id, plan_key, start_at, end_at, status, created_at)
            VALUES (?, ?, ?, ?, 'active', ?)
            """,
            (user_id, plan_key, start_at.isoformat(), end_at.isoformat(), utcnow_iso()),
        )

    def approve_latest_payment(self, user_id: int, approved_by: str) -> Optional[PaymentRecord]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM payments
                WHERE user_id = ? AND status = 'pending'
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if not row:
                return None

            conn.execute(
                """
                UPDATE payments
                SET status = 'approved', approved_at = ?, approved_by = ?
                WHERE id = ?
                """,
                (utcnow_iso(), approved_by, row["id"]),
            )
            self._activate_subscription(conn, user_id, row["plan_key"])
            return PaymentRecord(
                id=row["id"],
                user_id=row["user_id"],
                plan_key=row["plan_key"],
                amount=row["amount"],
                status="approved",
                payment_ref=row["payment_ref"],
                proof_text=row["proof_text"] or "",
            )

    def approve_by_payment_ref(self, payment_ref: str, approved_by: str) -> Optional[int]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM payments WHERE payment_ref = ? ORDER BY id DESC LIMIT 1",
                (payment_ref,),
            ).fetchone()
            if not row or row["status"] == "approved":
                return None
            conn.execute(
                "UPDATE payments SET status='approved', approved_at=?, approved_by=? WHERE id=?",
                (utcnow_iso(), approved_by, row["id"]),
            )
            self._activate_subscription(conn, int(row["user_id"]), row["plan_key"])
            return int(row["user_id"])

    def _expire_old_subscriptions(self, conn: sqlite3.Connection) -> None:
        now = utcnow_iso()
        conn.execute(
            """
            UPDATE subscriptions
            SET status = 'expired'
            WHERE status = 'active' AND end_at <= ?
            """,
            (now,),
        )

    def get_active_subscription(self, user_id: int) -> Optional[sqlite3.Row]:
        with self._conn() as conn:
            self._expire_old_subscriptions(conn)
            return conn.execute(
                """
                SELECT * FROM subscriptions
                WHERE user_id = ? AND status = 'active'
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()

    def has_active_access(self, user_id: int) -> bool:
        return self.get_active_subscription(user_id) is not None

    def add_message(self, user_id: int, role: str, content: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO messages (user_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, role, content, utcnow_iso()),
            )

    def get_recent_messages(self, user_id: int, limit: int = 12) -> List[Dict[str, str]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT role, content FROM messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
            ordered = list(reversed(rows))
            return [{"role": r["role"], "content": r["content"]} for r in ordered]

    def upsert_memory(self, user_id: int, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memory (user_id, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, key)
                DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (user_id, key, value, utcnow_iso()),
            )

    def get_memory(self, user_id: int) -> Dict[str, str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT key, value FROM memory WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            return {r["key"]: r["value"] for r in rows}

    def update_behavior_memory(self, user_id: int, user_text: str) -> None:
        lowered = user_text.lower().strip()
        self.upsert_memory(user_id, "last_seen", utcnow_iso())

        if any(word in lowered for word in ["sad", "down", "alone", "hurt", "broken"]):
            self.upsert_memory(user_id, "emotional_notes", "Needs comfort sometimes")
        elif any(word in lowered for word in ["miss", "thinking", "want you", "come back"]):
            self.upsert_memory(user_id, "emotional_notes", "Attached and expressive")

        if any(word in lowered for word in ["movie", "music", "cricket", "gym", "work", "late"]):
            self.upsert_memory(user_id, "favorite_topics", lowered[:120])

        tone = "balanced"
        if any(word in lowered for word in ["please", "sorry", "can i", "may i"]):
            tone = "soft"
        if any(word in lowered for word in ["bold", "dare", "prove", "now"]):
            tone = "confident"
        self.upsert_memory(user_id, "tone_level", tone)

    def get_stats(self) -> Dict[str, int]:
        with self._conn() as conn:
            users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
            active = conn.execute(
                """
                SELECT COUNT(DISTINCT user_id) AS c
                FROM subscriptions
                WHERE status = 'active' AND end_at > ?
                """,
                (utcnow_iso(),),
            ).fetchone()["c"]
            revenue = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE status = 'approved'"
            ).fetchone()["total"]
            return {"users": int(users), "active": int(active), "revenue": int(revenue)}

    def get_users_for_retention(self, since_hours: int = 24) -> List[sqlite3.Row]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
        with self._conn() as conn:
            self._expire_old_subscriptions(conn)
            return conn.execute(
                """
                SELECT u.telegram_id, u.id, u.first_name
                FROM users u
                JOIN subscriptions s ON s.user_id = u.id
                WHERE s.status = 'active'
                  AND s.end_at > ?
                  AND COALESCE(u.last_seen, '') < ?
                  AND u.is_banned = 0
                GROUP BY u.id
                ORDER BY u.last_seen ASC
                LIMIT 50
                """,
                (utcnow_iso(), cutoff),
            ).fetchall()
