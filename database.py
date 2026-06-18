# database.py
"""
SQLite ma'lumotlar bazasi — bot uchun doimiy saqlash qatlami.

Saqlanadigan narsalar:
  - Foydalanuvchi profili (oxirgi to'ldirgan CV ma'lumotlari — qayta tahrirlash uchun)
  - Bepul/pullik foydalanish holati (necha marta CV/xat yaratgan, nechta bepul huquqi bor)
  - Referal aloqalari (kim kimni taklif qilgan)
  - To'lov so'rovlari (kutilayotgan/tasdiqlangan/rad etilgan)
  - Umumiy statistika uchun hisoblovchi so'rovlar

Fayl manzili: DB_PATH (config.py orqali sozlanadi, default: bot_data.db)
"""

import sqlite3
import json
import time
from contextlib import contextmanager

from config import DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Bot birinchi marta ishga tushganda kerakli jadvallarni yaratadi."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                lang TEXT,
                referred_by INTEGER,
                free_credits INTEGER DEFAULT 1,
                created_at INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                data_json TEXT,
                updated_at INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                created_at INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                doc_type TEXT,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                screenshot_file_id TEXT,
                created_at INTEGER,
                resolved_at INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                doc_type TEXT,
                created_at INTEGER
            )
        """)


# ---------------------------------------------------------------------------
# Foydalanuvchilar
# ---------------------------------------------------------------------------
def get_or_create_user(user_id: int, username: str = "", lang: str = "uz", referred_by: int = None) -> sqlite3.Row:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            return row
        conn.execute(
            "INSERT INTO users (user_id, username, lang, referred_by, free_credits, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (user_id, username, lang, referred_by, int(time.time())),
        )
        if referred_by:
            try:
                conn.execute(
                    "INSERT INTO referrals (referrer_id, referred_id, created_at) VALUES (?, ?, ?)",
                    (referred_by, user_id, int(time.time())),
                )
            except sqlite3.IntegrityError:
                pass  # bu foydalanuvchi allaqachon referal sifatida qayd etilgan
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row


def set_user_lang(user_id: int, lang: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))


def get_free_credits(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT free_credits FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row["free_credits"] if row else 0


def consume_free_credit(user_id: int) -> bool:
    """Agar bepul huquq bo'lsa, bittasini ishlatadi va True qaytaradi. Bo'lmasa False."""
    with get_conn() as conn:
        row = conn.execute("SELECT free_credits FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row or row["free_credits"] <= 0:
            return False
        conn.execute("UPDATE users SET free_credits = free_credits - 1 WHERE user_id = ?", (user_id,))
        return True


def add_free_credit(user_id: int, amount: int = 1):
    with get_conn() as conn:
        conn.execute("UPDATE users SET free_credits = free_credits + ? WHERE user_id = ?", (amount, user_id))


def count_referrals(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = ?", (user_id,)).fetchone()
        return row["c"] if row else 0


# ---------------------------------------------------------------------------
# Profil (oxirgi to'ldirilgan CV ma'lumotlari — qayta tahrirlash uchun)
# ---------------------------------------------------------------------------
def save_profile(user_id: int, data: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO profiles (user_id, data_json, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET data_json = excluded.data_json, updated_at = excluded.updated_at",
            (user_id, json.dumps(data, ensure_ascii=False), int(time.time())),
        )


def load_profile(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT data_json FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return None
        return json.loads(row["data_json"])


# ---------------------------------------------------------------------------
# To'lovlar
# ---------------------------------------------------------------------------
def create_payment_request(user_id: int, doc_type: str, amount: int, screenshot_file_id: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO payments (user_id, doc_type, amount, status, screenshot_file_id, created_at) "
            "VALUES (?, ?, ?, 'pending', ?, ?)",
            (user_id, doc_type, amount, screenshot_file_id, int(time.time())),
        )
        return cur.lastrowid


def resolve_payment(payment_id: int, approved: bool):
    with get_conn() as conn:
        status = "approved" if approved else "rejected"
        conn.execute(
            "UPDATE payments SET status = ?, resolved_at = ? WHERE id = ?",
            (status, int(time.time()), payment_id),
        )


def get_payment(payment_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()


# ---------------------------------------------------------------------------
# Statistika
# ---------------------------------------------------------------------------
def log_document_created(user_id: int, doc_type: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO documents_log (user_id, doc_type, created_at) VALUES (?, ?, ?)",
            (user_id, doc_type, int(time.time())),
        )


def get_stats() -> dict:
    with get_conn() as conn:
        total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        total_docs = conn.execute("SELECT COUNT(*) AS c FROM documents_log").fetchone()["c"]
        cv_docs = conn.execute(
            "SELECT COUNT(*) AS c FROM documents_log WHERE doc_type = 'cv'"
        ).fetchone()["c"]
        letter_docs = conn.execute(
            "SELECT COUNT(*) AS c FROM documents_log WHERE doc_type = 'letter'"
        ).fetchone()["c"]
        pending_payments = conn.execute(
            "SELECT COUNT(*) AS c FROM payments WHERE status = 'pending'"
        ).fetchone()["c"]
        approved_payments = conn.execute(
            "SELECT COUNT(*) AS c, COALESCE(SUM(amount), 0) AS total FROM payments WHERE status = 'approved'"
        ).fetchone()
        return {
            "total_users": total_users,
            "total_docs": total_docs,
            "cv_docs": cv_docs,
            "letter_docs": letter_docs,
            "pending_payments": pending_payments,
            "approved_payments_count": approved_payments["c"],
            "approved_payments_sum": approved_payments["total"],
        }
