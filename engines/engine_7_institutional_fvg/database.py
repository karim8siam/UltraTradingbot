"""
SQLite Database Layer
Implements Section 59 (36 Trade Fields) & Section 60 (Rejected Setups Logging).
Zero external dependencies.
"""

import sqlite3
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass
class TradeRecord:
    trade_id: str
    timestamp: int
    symbol: str
    side: str
    bias_4h: str
    bias_1h: str
    bias_15m: str
    fvg_type: str
    fvg_high: float
    fvg_low: float
    fvg_mid: float
    fvg_size: float
    fvg_size_atr: float
    fvg_age: int
    displacement_size: float
    atr: float
    pullback_high: float
    pullback_low: float
    confirmation_level: float
    entry: float
    sl: float
    tp: float
    risk_amount: float
    position_size: float
    leverage: int
    rr: float
    setup_score: int
    funding_rate: float
    entry_time: int
    exit_time: int = 0
    exit_price: float = 0.0
    gross_pnl: float = 0.0
    fees: float = 0.0
    funding_cost: float = 0.0
    net_pnl: float = 0.0
    result: str = "OPEN"  # WIN, LOSS, OPEN, CANCELLED
    exit_reason: str = ""  # SL_HIT, TP_HIT, TIMEOUT, EMERGENCY


class BotDatabase:
    def __init__(self, db_path: str = "trades.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Section 59: 36 Trade Fields
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                timestamp INTEGER,
                symbol TEXT,
                side TEXT,
                bias_4h TEXT,
                bias_1h TEXT,
                bias_15m TEXT,
                fvg_type TEXT,
                fvg_high REAL,
                fvg_low REAL,
                fvg_mid REAL,
                fvg_size REAL,
                fvg_size_atr REAL,
                fvg_age INTEGER,
                displacement_size REAL,
                atr REAL,
                pullback_high REAL,
                pullback_low REAL,
                confirmation_level REAL,
                entry REAL,
                sl REAL,
                tp REAL,
                risk_amount REAL,
                position_size REAL,
                leverage INTEGER,
                rr REAL,
                setup_score INTEGER,
                funding_rate REAL,
                entry_time INTEGER,
                exit_time INTEGER,
                exit_price REAL,
                gross_pnl REAL,
                fees REAL,
                funding_cost REAL,
                net_pnl REAL,
                result TEXT,
                exit_reason TEXT
            )
            """)

            # Section 60: Rejected Setups Log
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS rejected_setups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                symbol TEXT,
                reason_code TEXT,
                setup_score INTEGER,
                price REAL,
                fvg_id TEXT,
                details TEXT
            )
            """)

            # Daily Metrics
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date_utc TEXT PRIMARY KEY,
                starting_equity REAL,
                ending_equity REAL,
                realized_pnl REAL,
                total_trades INTEGER,
                win_count INTEGER,
                loss_count INTEGER
            )
            """)
            conn.commit()

    def insert_trade(self, record: TradeRecord) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            data = asdict(record)
            placeholders = ", ".join("?" for _ in data)
            columns = ", ".join(data.keys())
            cursor.execute(f"INSERT OR REPLACE INTO trades ({columns}) VALUES ({placeholders})", list(data.values()))
            conn.commit()

    def update_trade_exit(
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
    ) -> None:
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
                exit_reason = ?
            WHERE trade_id = ?
            """, (exit_time, exit_price, gross_pnl, fees, funding_cost, net_pnl, result, exit_reason, trade_id))
            conn.commit()

    def log_rejected_setup(
        self,
        symbol: str,
        reason_code: str,
        score: int = 0,
        price: float = 0.0,
        fvg_id: str = "",
        details: str = "",
        timestamp: Optional[int] = None
    ) -> None:
        ts = timestamp or int(time.time() * 1000)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO rejected_setups (timestamp, symbol, reason_code, setup_score, price, fvg_id, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ts, symbol, reason_code, score, price, fvg_id, details))
            conn.commit()

    def get_all_trades(self) -> List[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades ORDER BY entry_time ASC")
            return [dict(row) for row in cursor.fetchall()]

    def get_open_trades(self) -> List[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE result = 'OPEN'")
            return [dict(row) for row in cursor.fetchall()]
