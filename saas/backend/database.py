"""
database.py — PostgreSQL (Neon) database layer for UltraQuant SaaS.

Neon free-tier computes auto-suspend after inactivity. On cold start, the TCP
handshake succeeds but SSL + auth may take 5-15 seconds. We handle this with:
  - Lazy pool creation (not at import time)
  - Retry logic with exponential backoff on connect
  - Increased connect_timeout
  - Simple connection (not pool) for reliability on free tier
"""

import os
import time
import logging
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ── Load .env from the saas/ directory ────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=os.path.abspath(_env_path))

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. "
        "Add it to saas/.env or export it as an environment variable."
    )

# Strip channel_binding if present (not supported by psycopg2)
if "channel_binding" in DATABASE_URL:
    import urllib.parse as _up
    _parts = DATABASE_URL.split("?", 1)
    if len(_parts) == 2:
        _params = {k: v for k, v in [p.split("=") for p in _parts[1].split("&") if "channel_binding" not in p]}
        DATABASE_URL = _parts[0] + ("?" + "&".join(f"{k}={v}" for k, v in _params.items()) if _params else "")


def _new_connection(retries: int = 5, base_delay: float = 2.0) -> psycopg2.extensions.connection:
    """
    Opens a new psycopg2 connection with retry + exponential backoff.
    Handles Neon compute cold-start (auto-suspend) gracefully.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(
                DATABASE_URL,
                cursor_factory=RealDictCursor,
                connect_timeout=30,   # 30 s — generous for Neon cold-start
                keepalives=1,
                keepalives_idle=10,
                keepalives_interval=5,
                keepalives_count=3,
            )
            conn.autocommit = False
            return conn
        except psycopg2.OperationalError as e:
            last_err = e
            if attempt < retries:
                delay = base_delay * (2 ** (attempt - 1))  # 2, 4, 8, 16 s
                logger.warning(f"Neon connect attempt {attempt} failed — retrying in {delay:.0f}s: {e}")
                time.sleep(delay)
            else:
                logger.error(f"All {retries} connect attempts failed.")
    raise last_err


# ── Public context manager: `with get_db() as conn:` ──────────────────────────
@contextmanager
def get_db() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Yields a fresh psycopg2 connection.
    Automatically commits on clean exit, rolls back on exception, closes always.

    Usage:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT %s", (value,))
            conn.commit()
    """
    conn = _new_connection()
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ── Schema bootstrap ───────────────────────────────────────────────────────────
def init_db() -> None:
    """Creates all tables and indexes if they don't already exist."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # users
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name     TEXT DEFAULT '',
                role          TEXT DEFAULT 'user',
                created_at    TEXT NOT NULL
            )
            """)

            # subscriptions
            cur.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                tier        TEXT NOT NULL,
                status      TEXT NOT NULL,
                starts_at   TEXT NOT NULL,
                expires_at  TEXT NOT NULL,
                amount_paid FLOAT DEFAULT 0.0,
                created_at  TEXT NOT NULL
            )
            """)

            # exchange_keys
            cur.execute("""
            CREATE TABLE IF NOT EXISTS exchange_keys (
                id                    SERIAL PRIMARY KEY,
                user_id               INTEGER NOT NULL REFERENCES users(id),
                exchange              TEXT NOT NULL,
                api_key               TEXT NOT NULL,
                api_secret_encrypted  TEXT NOT NULL,
                is_valid              INTEGER DEFAULT 0,
                futures_enabled       INTEGER DEFAULT 0,
                withdrawals_disabled  INTEGER DEFAULT 1,
                balance_usdt          FLOAT DEFAULT 0.0,
                status                TEXT DEFAULT 'disconnected',
                verified_at           TEXT
            )
            """)

            # trades
            cur.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                engine_name TEXT NOT NULL,
                symbol      TEXT NOT NULL,
                side        TEXT NOT NULL,
                entry_price FLOAT NOT NULL,
                exit_price  FLOAT DEFAULT 0.0,
                pnl_usd     FLOAT DEFAULT 0.0,
                status      TEXT DEFAULT 'CLOSED',
                timestamp   TEXT NOT NULL
            )
            """)

            # payment_transactions (UNIQUE tx_hash = anti-replay enforcement)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS payment_transactions (
                id               SERIAL PRIMARY KEY,
                user_id          INTEGER NOT NULL REFERENCES users(id),
                tx_hash          TEXT UNIQUE NOT NULL,
                amount           FLOAT NOT NULL,
                token_symbol     TEXT NOT NULL,
                tier             TEXT NOT NULL,
                sender_address   TEXT NOT NULL,
                receiver_address TEXT NOT NULL,
                network          TEXT DEFAULT 'BEP20',
                block_number     INTEGER DEFAULT 0,
                status           TEXT DEFAULT 'verified',
                created_at       TEXT NOT NULL
            )
            """)

            # Performance indexes
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_sub_user_status
                ON subscriptions(user_id, status)
            """)
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_exkeys_user
                ON exchange_keys(user_id)
            """)
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_user_id
                ON trades(user_id, id DESC)
            """)
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pay_tx_hash
                ON payment_transactions(tx_hash)
            """)

        conn.commit()
    logger.info("✅ Neon PostgreSQL schema initialised successfully.")


# ── Initialise schema on import (lazy — won't crash at import if Neon is waking up)
def _safe_init():
    try:
        init_db()
    except Exception as e:
        logger.warning(f"DB init on import failed (Neon may still be waking up): {e}")

_safe_init()
