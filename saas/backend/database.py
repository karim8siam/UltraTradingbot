import os
import sqlite3
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta

DB_DIR = os.getenv("SAAS_DATA_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")))
DB_FILE = os.path.join(DB_DIR, "platform.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT DEFAULT '',
            role TEXT DEFAULT 'user',
            created_at TEXT NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tier TEXT NOT NULL,          -- 'trial_7d', 'paid_7d', 'paid_30d'
            status TEXT NOT NULL,        -- 'active', 'expired', 'disconnected'
            starts_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            amount_paid REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS exchange_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exchange TEXT NOT NULL,      -- 'binance' or 'bybit'
            api_key TEXT NOT NULL,
            api_secret_encrypted TEXT NOT NULL,
            is_valid INTEGER DEFAULT 0,
            futures_enabled INTEGER DEFAULT 0,
            withdrawals_disabled INTEGER DEFAULT 1,
            balance_usdt REAL DEFAULT 0.0,
            status TEXT DEFAULT 'disconnected', -- 'connected', 'disconnected', 'error'
            verified_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            engine_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL DEFAULT 0.0,
            pnl_usd REAL DEFAULT 0.0,
            status TEXT DEFAULT 'CLOSED', -- 'OPEN', 'CLOSED'
            timestamp TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS payment_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tx_hash TEXT UNIQUE NOT NULL,
            amount REAL NOT NULL,
            token_symbol TEXT NOT NULL,
            tier TEXT NOT NULL,
            sender_address TEXT NOT NULL,
            receiver_address TEXT NOT NULL,
            network TEXT DEFAULT 'BEP20',
            block_number INTEGER DEFAULT 0,
            status TEXT DEFAULT 'verified',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)
        conn.commit()


# Initialize schema on load
init_db()
