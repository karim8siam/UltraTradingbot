"""
Database module for trade logging and rejected setup audits.
Complies with Section 59 (Trades schema) and Section 60 (Rejected Setups schema).
"""

import os
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Section 59: Trades table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                daily_trend TEXT,
                daily_structure TEXT,
                daily_EMA50 REAL,
                daily_EMA200 REAL,
                four_h_trend TEXT,
                four_h_EMA20 REAL,
                four_h_EMA50 REAL,
                four_h_swing_high REAL,
                four_h_swing_low REAL,
                impulse_high REAL,
                impulse_low REAL,
                Fibonacci_38_2 REAL,
                Fibonacci_50 REAL,
                Fibonacci_61_8 REAL,
                Fibonacci_70_5 REAL,
                pullback_depth REAL,
                ADX REAL,
                volume_ratio REAL,
                one_h_structure TEXT,
                entry REAL,
                SL REAL,
                TP1 REAL,
                TP2 REAL,
                risk REAL,
                position_size REAL,
                leverage INTEGER,
                RR REAL,
                setup_score INTEGER,
                funding REAL,
                entry_time TEXT,
                exit_time TEXT,
                exit_price REAL,
                gross_pnl REAL,
                fees REAL,
                funding_cost REAL,
                slippage REAL,
                net_pnl REAL,
                R_multiple REAL,
                result TEXT,
                exit_reason TEXT,
                holding_hours REAL
            )
            """)

            # Section 60: Rejected setup logging
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS rejected_setups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT,
                reason_code TEXT NOT NULL,
                setup_score INTEGER,
                daily_trend TEXT,
                four_h_trend TEXT,
                details TEXT
            )
            """)

            # State & Balance Tracking Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                equity REAL NOT NULL,
                available_margin REAL NOT NULL,
                daily_pnl REAL NOT NULL,
                open_positions_count INTEGER NOT NULL,
                total_open_risk REAL NOT NULL
            )
            """)
            conn.commit()

    def record_trade(self, trade: Dict[str, Any]) -> None:
        """Insert or replace trade record."""
        keys = list(trade.keys())
        placeholders = ", ".join(["?"] * len(keys))
        columns = ", ".join(keys)
        values = [trade[k] for k in keys]

        query = f"INSERT OR REPLACE INTO trades ({columns}) VALUES ({placeholders})"
        with self._get_connection() as conn:
            conn.execute(query, values)
            conn.commit()

    def log_rejected_setup(self, symbol: str, reason_code: str, score: int = 0,
                            direction: str = "UNKNOWN", daily_trend: str = "",
                            four_h_trend: str = "", details: str = "") -> None:
        """Log a rejected setup for audit."""
        timestamp = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO rejected_setups (timestamp, symbol, direction, reason_code, setup_score, daily_trend, four_h_trend, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, symbol, direction, reason_code, score, daily_trend, four_h_trend, details))
            conn.commit()

    def record_account_snapshot(self, equity: float, available_margin: float,
                                daily_pnl: float, open_positions_count: int, total_open_risk: float) -> None:
        timestamp = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO account_snapshots (timestamp, equity, available_margin, daily_pnl, open_positions_count, total_open_risk)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (timestamp, equity, available_margin, daily_pnl, open_positions_count, total_open_risk))
            conn.commit()

    def get_all_trades(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades ORDER BY timestamp ASC")
            return [dict(row) for row in cursor.fetchall()]

    def get_rejected_setups(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rejected_setups ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
