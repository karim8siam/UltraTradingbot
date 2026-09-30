import sqlite3
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

logger = logging.getLogger("SMC_Database")

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    bias_4h TEXT,
                    bias_1h TEXT,
                    bias_15m TEXT,
                    liquidity_type TEXT,
                    liquidity_level REAL,
                    sweep_high REAL,
                    sweep_low REAL,
                    mss_level REAL,
                    displacement_size REAL,
                    fvg_high REAL,
                    fvg_low REAL,
                    fvg_midpoint REAL,
                    entry REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    risk_amount REAL NOT NULL,
                    position_size REAL NOT NULL,
                    leverage INTEGER NOT NULL,
                    rr REAL NOT NULL,
                    setup_score INTEGER NOT NULL,
                    atr REAL,
                    funding_rate REAL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    exit_price REAL,
                    gross_pnl REAL,
                    fees REAL,
                    funding_cost REAL,
                    net_pnl REAL,
                    result TEXT,
                    exit_reason TEXT,
                    client_order_id TEXT,
                    sl_order_id TEXT,
                    tp_order_id TEXT,
                    mode TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rejected_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    bias_4h TEXT,
                    bias_1h TEXT,
                    setup_score INTEGER,
                    calculated_rr REAL,
                    details TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date_utc TEXT PRIMARY KEY,
                    starting_equity REAL NOT NULL,
                    realized_pnl REAL DEFAULT 0.0,
                    trades_count INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    kill_switch_activated INTEGER DEFAULT 0
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    symbol TEXT,
                    message TEXT NOT NULL
                )
            """)
            conn.commit()

    def record_trade_opened(self, trade_data: Dict[str, Any]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades (
                    trade_id, symbol, side, bias_4h, bias_1h, bias_15m,
                    liquidity_type, liquidity_level, sweep_high, sweep_low,
                    mss_level, displacement_size, fvg_high, fvg_low, fvg_midpoint,
                    entry, stop_loss, take_profit, risk_amount, position_size,
                    leverage, rr, setup_score, atr, funding_rate, entry_time,
                    result, client_order_id, sl_order_id, tp_order_id, mode
                ) VALUES (
                    :trade_id, :symbol, :side, :bias_4h, :bias_1h, :bias_15m,
                    :liquidity_type, :liquidity_level, :sweep_high, :sweep_low,
                    :mss_level, :displacement_size, :fvg_high, :fvg_low, :fvg_midpoint,
                    :entry, :stop_loss, :take_profit, :risk_amount, :position_size,
                    :leverage, :rr, :setup_score, :atr, :funding_rate, :entry_time,
                    :result, :client_order_id, :sl_order_id, :tp_order_id, :mode
                )
            """, trade_data)
            conn.commit()

    def record_trade_closed(self, trade_id: str, exit_time: str, exit_price: float,
                            gross_pnl: float, fees: float, funding_cost: float,
                            net_pnl: float, result: str, exit_reason: str):
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

    def log_rejected_signal(self, symbol: str, reason: str, bias_4h: Optional[str] = None,
                            bias_1h: Optional[str] = None, score: Optional[int] = None,
                            rr: Optional[float] = None, details: Optional[str] = None):
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rejected_signals (timestamp, symbol, reason, bias_4h, bias_1h, setup_score, calculated_rr, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (now_utc, symbol, reason, bias_4h, bias_1h, score, rr, details or ""))
            conn.commit()

    def log_event(self, event_type: str, message: str, symbol: Optional[str] = None):
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_logs (timestamp, event_type, symbol, message)
                VALUES (?, ?, ?, ?)
            """, (now_utc, event_type, symbol, message))
            conn.commit()

    def get_open_trades(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""SELECT * FROM trades WHERE exit_time IS NULL""")
            return [dict(row) for row in cursor.fetchall()]

    def get_all_trades(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""SELECT * FROM trades ORDER BY entry_time DESC""")
            return [dict(row) for row in cursor.fetchall()]

    def get_daily_trades_count(self, date_utc: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM trades
                WHERE entry_time LIKE ? AND mode != "CANCELLED"
            """, (f"{date_utc}%",))
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_daily_realized_pnl(self, date_utc: str) -> float:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUM(net_pnl) FROM trades
                WHERE exit_time LIKE ?
            """, (f"{date_utc}%",))
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else 0.0
