"""
SQLite Persistence and Audit Logging for Binance Futures GFS Bot
Stores complete trade lifecycle, metrics, and granular setup rejections.
"""

import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class GFSDatabase:
    """
    Thread-safe SQLite Database Manager for GFS Trading Engine.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Trades Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    daily_trend TEXT,
                    daily_ema50 REAL,
                    daily_ema200 REAL,
                    four_hour_trend TEXT,
                    four_hour_ema20 REAL,
                    four_hour_ema50 REAL,
                    pullback_zone_valid INTEGER,
                    fifteen_m_trend TEXT,
                    fifteen_m_structure_level REAL,
                    confirmation_candle_idx INTEGER,
                    atr REAL,
                    planned_entry REAL,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    risk_reward REAL,
                    risk_amount REAL,
                    position_size REAL,
                    leverage INTEGER,
                    setup_score INTEGER,
                    score_breakdown TEXT,
                    funding REAL,
                    entry_time INTEGER,
                    exit_time INTEGER,
                    exit_price REAL,
                    gross_pnl REAL DEFAULT 0.0,
                    fees REAL DEFAULT 0.0,
                    funding_cost REAL DEFAULT 0.0,
                    net_pnl REAL DEFAULT 0.0,
                    result TEXT,
                    exit_reason TEXT,
                    client_order_id TEXT
                )
            """)

            # 2. Rejection Logs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rejection_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    rejection_code TEXT NOT NULL,
                    details TEXT
                )
            """)

            # 3. Account Snapshots Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_snapshots (
                    timestamp INTEGER PRIMARY KEY,
                    date_utc TEXT NOT NULL,
                    equity REAL NOT NULL,
                    available_margin REAL NOT NULL,
                    daily_pnl REAL NOT NULL,
                    open_positions INTEGER NOT NULL,
                    consecutive_losses INTEGER NOT NULL
                )
            """)

            # 4. State Recovery Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_state_recovery (
                    symbol TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    last_updated INTEGER NOT NULL,
                    setup_data TEXT,
                    active_order_id TEXT
                )
            """)

            conn.commit()

    def record_rejection(self, symbol: str, stage: str, rejection_code: str, details: Dict[str, Any] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rejection_logs (timestamp, symbol, stage, rejection_code, details)
                VALUES (?, ?, ?, ?, ?)
            """, (
                int(datetime.now(timezone.utc).timestamp() * 1000),
                symbol,
                stage,
                rejection_code,
                json.dumps(details or {})
            ))
            conn.commit()

    def record_trade_entry(self, trade_data: Dict[str, Any]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO trades (
                    trade_id, symbol, direction, status, timestamp,
                    daily_trend, daily_ema50, daily_ema200,
                    four_hour_trend, four_hour_ema20, four_hour_ema50,
                    pullback_zone_valid, fifteen_m_trend, fifteen_m_structure_level,
                    confirmation_candle_idx, atr, planned_entry, entry_price,
                    stop_loss, take_profit, risk_reward, risk_amount,
                    position_size, leverage, setup_score, score_breakdown,
                    funding, entry_time, client_order_id
                ) VALUES (
                    :trade_id, :symbol, :direction, :status, :timestamp,
                    :daily_trend, :daily_ema50, :daily_ema200,
                    :four_hour_trend, :four_hour_ema20, :four_hour_ema50,
                    :pullback_zone_valid, :fifteen_m_trend, :fifteen_m_structure_level,
                    :confirmation_candle_idx, :atr, :planned_entry, :entry_price,
                    :stop_loss, :take_profit, :risk_reward, :risk_amount,
                    :position_size, :leverage, :setup_score, :score_breakdown,
                    :funding, :entry_time, :client_order_id
                )
            """, trade_data)
            conn.commit()

    def record_trade_exit(
        self,
        trade_id: str,
        exit_time: int,
        exit_price: float,
        gross_pnl: float,
        fees: float,
        funding_cost: float,
        net_pnl: float,
        result: str,
        exit_reason: str
    ):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE trades SET
                    exit_time = ?,
                    exit_price = ?,
                    gross_pnl = ?,
                    fees = ?,
                    funding_cost = ?,
                    net_pnl = ?,
                    result = ?,
                    exit_reason = ?,
                    status = \x27CLOSED\x27
                WHERE trade_id = ?
            """, (
                exit_time, exit_price, gross_pnl, fees,
                funding_cost, net_pnl, result, exit_reason, trade_id
            ))
            conn.commit()

    def record_snapshot(self, equity: float, available_margin: float, daily_pnl: float, open_positions: int, consecutive_losses: int):
        now_dt = datetime.now(timezone.utc)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO account_snapshots (
                    timestamp, date_utc, equity, available_margin, daily_pnl, open_positions, consecutive_losses
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                int(now_dt.timestamp() * 1000),
                now_dt.strftime("%Y-%m-%d"),
                equity,
                available_margin,
                daily_pnl,
                open_positions,
                consecutive_losses
            ))
            conn.commit()

    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_rejection_counts(self) -> Dict[str, int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rejection_code, COUNT(*) as cnt FROM rejection_logs GROUP BY rejection_code ORDER BY cnt DESC")
            return {row["rejection_code"]: row["cnt"] for row in cursor.fetchall()}
