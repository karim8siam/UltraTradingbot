"""
SQLite Database Persistence Layer
Section 54 & 55 Specification
"""

import os
import sqlite3
from typing import Any, Dict, List, Optional
from core.types import TradeRecord, SetupRejectReason


class Database:
    def __init__(self, db_path: str = "data/trading_bot.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Trades table (35+ fields)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    timestamp INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    bias_4h TEXT NOT NULL,
                    bias_1h TEXT NOT NULL,
                    impulse_low REAL NOT NULL,
                    impulse_high REAL NOT NULL,
                    impulse_size REAL NOT NULL,
                    atr REAL NOT NULL,
                    fib_236 REAL NOT NULL,
                    fib_382 REAL NOT NULL,
                    fib_500 REAL NOT NULL,
                    fib_618 REAL NOT NULL,
                    fib_786 REAL NOT NULL,
                    pullback_low REAL NOT NULL,
                    pullback_high REAL NOT NULL,
                    confirmation_level REAL NOT NULL,
                    entry REAL NOT NULL,
                    sl REAL NOT NULL,
                    tp REAL NOT NULL,
                    risk_amount REAL NOT NULL,
                    position_size REAL NOT NULL,
                    leverage INTEGER NOT NULL,
                    rr REAL NOT NULL,
                    setup_score INTEGER NOT NULL,
                    funding_rate REAL NOT NULL,
                    entry_time INTEGER NOT NULL,
                    exit_time INTEGER DEFAULT 0,
                    exit_price REAL DEFAULT 0.0,
                    gross_pnl REAL DEFAULT 0.0,
                    fees REAL DEFAULT 0.0,
                    funding_cost REAL DEFAULT 0.0,
                    net_pnl REAL DEFAULT 0.0,
                    result TEXT DEFAULT 'OPEN',
                    exit_reason TEXT DEFAULT '',
                    fib_zone TEXT DEFAULT ''
                )
                """
            )

            # 2. Rejected Signals Log
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS rejected_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    details TEXT DEFAULT ''
                )
                """
            )

            # 3. Daily Equity Tracking
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_equity (
                    date_utc TEXT PRIMARY KEY,
                    starting_equity REAL NOT NULL,
                    current_equity REAL NOT NULL,
                    realized_pnl REAL DEFAULT 0.0,
                    trade_count INTEGER DEFAULT 0,
                    consecutive_losses INTEGER DEFAULT 0
                )
                """
            )
            conn.commit()

    def record_trade(self, trade: TradeRecord):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO trades (
                    trade_id, timestamp, symbol, side, bias_4h, bias_1h,
                    impulse_low, impulse_high, impulse_size, atr,
                    fib_236, fib_382, fib_500, fib_618, fib_786,
                    pullback_low, pullback_high, confirmation_level,
                    entry, sl, tp, risk_amount, position_size, leverage,
                    rr, setup_score, funding_rate, entry_time, exit_time,
                    exit_price, gross_pnl, fees, funding_cost, net_pnl,
                    result, exit_reason, fib_zone
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?
                )
                """,
                (
                    trade.trade_id, trade.timestamp, trade.symbol, trade.side, trade.bias_4h, trade.bias_1h,
                    trade.impulse_low, trade.impulse_high, trade.impulse_size, trade.atr,
                    trade.fib_236, trade.fib_382, trade.fib_500, trade.fib_618, trade.fib_786,
                    trade.pullback_low, trade.pullback_high, trade.confirmation_level,
                    trade.entry, trade.sl, trade.tp, trade.risk_amount, trade.position_size, trade.leverage,
                    trade.rr, trade.setup_score, trade.funding_rate, trade.entry_time, trade.exit_time,
                    trade.exit_price, trade.gross_pnl, trade.fees, trade.funding_cost, trade.net_pnl,
                    trade.result, trade.exit_reason, trade.fib_zone,
                ),
            )
            conn.commit()

    def log_rejection(self, symbol: str, reason: SetupRejectReason, details: str = "", timestamp: int = 0):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO rejected_signals (timestamp, symbol, reason, details)
                VALUES (?, ?, ?, ?)
                """,
                (timestamp, symbol, reason.value if hasattr(reason, 'value') else str(reason), details),
            )
            conn.commit()

    def get_all_trades(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades ORDER BY entry_time ASC")
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_rejections(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rejected_signals ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
