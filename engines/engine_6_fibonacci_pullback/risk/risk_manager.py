"""
Risk Management & Strategy Boundary Controller
Sections 31, 32, 33, 34, 35, 36, 37, 38, 50
"""

import datetime
from typing import Dict, List, Optional, Set, Tuple
from core.types import SetupRejectReason
from config.constants import (
    MAX_DAILY_LOSS,
    MAX_CONSECUTIVE_LOSSES,
    COOLDOWN_HOURS,
    MAX_DAILY_TRADES,
    MAX_OPEN_POSITIONS,
    DEFAULT_TRADING_SESSIONS,
    MAX_ATR_RATIO,
)


class RiskManager:
    def __init__(
        self,
        max_daily_loss: Optional[float] = MAX_DAILY_LOSS,
        max_consecutive_losses: int = MAX_CONSECUTIVE_LOSSES,
        cooldown_hours: float = COOLDOWN_HOURS,
        max_daily_trades: int = MAX_DAILY_TRADES,
        max_open_positions: int = MAX_OPEN_POSITIONS,
        trading_sessions: List[Tuple[int, int, int, int]] = None,
        max_atr_ratio: float = MAX_ATR_RATIO,
    ):
        self.max_daily_loss = max_daily_loss
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_hours = cooldown_hours
        self.max_daily_trades = max_daily_trades
        self.max_open_positions = max_open_positions
        self.trading_sessions = trading_sessions or DEFAULT_TRADING_SESSIONS
        self.max_atr_ratio = max_atr_ratio

        # State tracking
        self.current_utc_date: Optional[str] = None
        self.starting_equity_today: float = 10000.0
        self.daily_realized_pnl: float = 0.0
        self.daily_trade_count: int = 0
        self.consecutive_losses: int = 0
        self.cooldown_until_ts: int = 0
        self.open_symbols: Set[str] = set()

    def _sync_utc_day(self, current_ts_ms: int, current_equity: float):
        """Resets daily counters on UTC day transition."""
        dt = datetime.datetime.fromtimestamp(current_ts_ms / 1000.0, tz=datetime.timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")

        if self.current_utc_date != date_str:
            self.current_utc_date = date_str
            self.starting_equity_today = current_equity
            self.daily_realized_pnl = 0.0
            self.daily_trade_count = 0

    def is_session_active(self, current_ts_ms: int) -> bool:
        """Verifies if current timestamp is within configured UTC trading sessions."""
        dt = datetime.datetime.fromtimestamp(current_ts_ms / 1000.0, tz=datetime.timezone.utc)
        current_time_minutes = dt.hour * 60 + dt.minute

        for s_hour, s_min, e_hour, e_min in self.trading_sessions:
            start_min = s_hour * 60 + s_min
            end_min = e_hour * 60 + e_min
            if start_min <= current_time_minutes <= end_min:
                return True
        return False

    def validate_new_trade(
        self,
        symbol: str,
        current_ts_ms: int,
        current_equity: float,
        atr_ratio: float = 1.0,
        emergency_stop: bool = False,
    ) -> Optional[SetupRejectReason]:
        """
        Evaluates all portfolio-level and market-condition risk gates:
        Returns None if trade is permitted, or SetupRejectReason if rejected.
        """
        if emergency_stop:
            return SetupRejectReason.REJECTED_EMERGENCY_STOP

        self._sync_utc_day(current_ts_ms, current_equity)

        # 1. Trading Session Check
        if not self.is_session_active(current_ts_ms):
            return SetupRejectReason.REJECTED_SESSION

        # 2. Daily Loss Limit Check (Only if configured)
        if self.max_daily_loss is not None and self.max_daily_loss > 0.0:
            daily_loss_pct = (
                (self.starting_equity_today - current_equity) / self.starting_equity_today
                if self.starting_equity_today > 0
                else 0.0
            )
            if daily_loss_pct >= self.max_daily_loss:
                return SetupRejectReason.REJECTED_DAILY_LIMIT

        # 3. Consecutive Loss Cooldown Check
        if current_ts_ms < self.cooldown_until_ts:
            return SetupRejectReason.REJECTED_CONSECUTIVE_LOSS_COOLDOWN

        # 4. Daily Trade Limit Check
        if self.daily_trade_count >= self.max_daily_trades:
            return SetupRejectReason.REJECTED_DAILY_LIMIT

        # 5. Max Open Positions Check
        if len(self.open_symbols) >= self.max_open_positions:
            return SetupRejectReason.REJECTED_MAX_POSITIONS

        # 6. One Position Per Symbol Check
        if symbol in self.open_symbols:
            return SetupRejectReason.REJECTED_EXISTING_POSITION

        # 7. Volatility Filter Check
        if atr_ratio > self.max_atr_ratio:
            return SetupRejectReason.REJECTED_HIGH_VOLATILITY

        return None

    def on_trade_opened(self, symbol: str, current_ts_ms: int):
        self.open_symbols.add(symbol)
        self.daily_trade_count += 1

    def on_trade_closed(self, symbol: str, net_pnl: float, current_ts_ms: int):
        self.open_symbols.discard(symbol)
        self.daily_realized_pnl += net_pnl

        if net_pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.max_consecutive_losses:
                # Enter 4-hour cooldown
                self.cooldown_until_ts = current_ts_ms + int(self.cooldown_hours * 3600 * 1000)
        else:
            self.consecutive_losses = 0
