"""
database.py — PostgreSQL (Neon) database layer for UltraQuant SaaS.

Built for high-performance production using:
- Modern psycopg (v3) with psycopg_pool.ConnectionPool
- Direct SSL negotiation (sslnegotiation=direct) optimized for Neon serverless
- Thread-safe connection pooling
- Dictionary-style row access (dict_row)
- Automated schema migrations and index creation
"""

import os
import logging
from contextlib import contextmanager
from typing import Generator
import urllib.parse as urllib_parse

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ── Load .env from the saas/ directory ────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=os.path.abspath(_env_path))

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to saas/.env or export it as an environment variable."
    )

# Sanitize DATABASE_URL for Neon
# 1. Remove channel_binding (unsupported by some clients)
# 2. Ensure sslnegotiation=direct is present for Neon endpoints
parsed = urllib_parse.urlparse(DATABASE_URL)
query_params = urllib_parse.parse_qs(parsed.query)

# Remove channel_binding if present
query_params.pop("channel_binding", None)

# Force sslmode=require and sslnegotiation=direct
query_params["sslmode"] = ["require"]
if "neon.tech" in parsed.netloc:
    query_params["sslnegotiation"] = ["direct"]

new_query = urllib_parse.urlencode(query_params, doseq=True)
DATABASE_URL = urllib_parse.urlunparse((
    parsed.scheme,
    parsed.netloc,
    parsed.path,
    parsed.params,
    new_query,
    parsed.fragment
))

# ── Connection Pool ───────────────────────────────────────────────────────────
_pool: ConnectionPool = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=DATABASE_URL,
            min_size=1,
            max_size=10,
            timeout=30.0,
            max_idle=300.0,
            kwargs={
                "row_factory": dict_row,
                "autocommit": False
            }
        )
    return _pool


# ── Public Context Manager ───────────────────────────────────────────────────
@contextmanager
def get_db() -> Generator[psycopg.Connection, None, None]:
    """
    Yields a connection from the pool.
    Usage:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ...", (param,))
            conn.commit()
    """
    pool = get_pool()
    with pool.connection() as conn:
        try:
            yield conn
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise


# ── Schema Bootstrap ───────────────────────────────────────────────────────────
def init_db() -> None:
    """Creates all required tables and indexes if they do not exist."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # 1. users
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

            # 2. subscriptions
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

            # 3. exchange_keys
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

            # 4. trades
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

            # 5. payment_transactions (UNIQUE tx_hash prevents double redemption)
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
    logger.info("✅ Neon PostgreSQL schema verified and initialized.")


# Automatically initialize schema on module load
try:
    init_db()
except Exception as err:
    logger.warning(f"Initial schema check failed: {err}")
