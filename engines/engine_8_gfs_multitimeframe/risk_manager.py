"""
Risk Management Engine for Binance Futures GFS Trading Bot
Deterministic Account Protection, Position Sizing, Daily Loss, and Streak Limiting.
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field

from config import (
    RISK_PER_TRADE, DEFAULT_LEVERAGE, MAX_DAILY_LOSS,
    MAX_CONSECUTIVE_LOSSES, CONSECUTIVE_LOSS_COOLDOWN_HOURS,
    MAX_DAILY_TRADES, MAX_OPEN_POSITIONS, ONE_POSITION_PER_SYMBOL,
    TRADING_SESSIONS, ENFORCE_TRADING_SESSIONS, ENABLE_STOP_LOSS,
    TARGET_PROFIT_EQUITY_PCT, STOP_LOSS_EQUITY_PCT
)


@dataclass
class SymbolFilters:
    symbol: str
    price_precision: int = 2
    quantity_precision: int = 3
    step_size: float = 0.001
    tick_size: float = 0.01
    min_qty: float = 0.001
    min_notional: float = 5.0
    max_leverage: int = 50


@dataclass
class DailyRiskState:
    current_date_utc: str             # YYYY-MM-DD
    starting_equity: float
    current_equity: float
    realized_daily_pnl: float = 0.0
    daily_trade_count: int = 0
    consecutive_losses: int = 0
    cooldown_until_ts: int = 0        # UTC timestamp ms
    emergency_halt: bool = False


class RiskManager:
    """
    Enforces strict risk management rules and dynamic position sizing.
    """

    def __init__(
        self,
        starting_equity: float = 10000.0,
        risk_per_trade: float = RISK_PER_TRADE,
        max_daily_loss: float = MAX_DAILY_LOSS,
        max_consecutive_losses: int = MAX_CONSECUTIVE_LOSSES,
        max_daily_trades: int = MAX_DAILY_TRADES,
        max_open_positions: int = MAX_OPEN_POSITIONS,
        default_leverage: int = DEFAULT_LEVERAGE,
        enforce_sessions: bool = ENFORCE_TRADING_SESSIONS,
        enable_stop_loss: bool = ENABLE_STOP_LOSS,
        target_profit_equity_pct: float = TARGET_PROFIT_EQUITY_PCT,
        stop_loss_equity_pct: float = STOP_LOSS_EQUITY_PCT
    ):
        self.risk_per_trade = risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_consecutive_losses = max_consecutive_losses
        self.max_daily_trades = max_daily_trades
        self.max_open_positions = max_open_positions
        self.default_leverage = default_leverage
        self.enforce_sessions = enforce_sessions
        self.enable_stop_loss = enable_stop_loss
        self.target_profit_equity_pct = target_profit_equity_pct
        self.stop_loss_equity_pct = stop_loss_equity_pct

        today_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        self.daily_state = DailyRiskState(
            current_date_utc=today_utc,
            starting_equity=starting_equity,
            current_equity=starting_equity
        )

        self.symbol_filters: Dict[str, SymbolFilters] = {}
        self.open_positions: Dict[str, Dict[str, Any]] = {}

    def set_symbol_filter(self, symbol: str, filters: SymbolFilters):
        self.symbol_filters[symbol] = filters

    def get_symbol_filter(self, symbol: str) -> SymbolFilters:
        if symbol not in self.symbol_filters:
            # Default fallback filter
            self.symbol_filters[symbol] = SymbolFilters(symbol=symbol)
        return self.symbol_filters[symbol]

    def check_utc_day_rollover(self, current_equity: float, now_dt: Optional[datetime] = None):
        """
        Resets daily counters at 00:00 UTC.
        """
        if now_dt is None:
            now_dt = datetime.now(timezone.utc)
        today_utc = now_dt.strftime('%Y-%m-%d')

        if today_utc != self.daily_state.current_date_utc:
            self.daily_state.current_date_utc = today_utc
            self.daily_state.starting_equity = current_equity
            self.daily_state.current_equity = current_equity
            self.daily_state.realized_daily_pnl = 0.0
            self.daily_state.daily_trade_count = 0
            self.daily_state.emergency_halt = False

    def is_session_active(self, now_dt: Optional[datetime] = None) -> bool:
        """
        Checks if current UTC time falls within configured trading sessions.
        """
        if not self.enforce_sessions:
            return True

        if now_dt is None:
            now_dt = datetime.now(timezone.utc)

        current_time_str = now_dt.strftime('%H:%M')

        for start_str, end_str in TRADING_SESSIONS:
            if start_str <= current_time_str <= end_str:
                return True
        return False

    def check_trade_allowed(
        self,
        symbol: str,
        current_equity: float,
        now_ts_ms: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Validates all risk constraints before opening a trade.
        """
        now_dt = datetime.fromtimestamp(now_ts_ms / 1000.0, tz=timezone.utc) if now_ts_ms else datetime.now(timezone.utc)
        self.check_utc_day_rollover(current_equity, now_dt)

        # 1. Emergency Halt
        if self.daily_state.emergency_halt:
            return False, 'REJECTED_EMERGENCY_HALT'

        # 2. Trading Session
        if not self.is_session_active(now_dt):
            return False, 'REJECTED_SESSION_INACTIVE'

        # 3. Consecutive Loss Cooldown
        current_ms = int(now_dt.timestamp() * 1000)
        if self.daily_state.cooldown_until_ts > current_ms:
            return False, 'REJECTED_CONSECUTIVE_LOSS_COOLDOWN'

        # 4. Daily Loss Limit (2% of starting equity)
        loss_amount = self.daily_state.starting_equity - current_equity
        if loss_amount >= (self.daily_state.starting_equity * self.max_daily_loss):
            return False, 'REJECTED_DAILY_LOSS_LIMIT_REACHED'

        # 5. Daily Trade Count Limit
        if self.daily_state.daily_trade_count >= self.max_daily_trades:
            return False, 'REJECTED_DAILY_TRADE_LIMIT_REACHED'

        # 6. Maximum Open Positions
        if len(self.open_positions) >= self.max_open_positions:
            return False, 'REJECTED_MAX_OPEN_POSITIONS_REACHED'

        # 7. One Position Per Symbol
        if ONE_POSITION_PER_SYMBOL and symbol in self.open_positions:
            return False, 'REJECTED_EXISTING_SYMBOL_POSITION'

        return True, 'APPROVED'

    def calculate_position_size(
        self,
        symbol: str,
        equity: float,
        entry_price: float,
        stop_loss: float = 0.0
    ) -> Tuple[float, float, float, str]:
        """
        Calculates position size:
        - Sizes targeting Binance minimum viable notional ($5.00 min) with dynamic buffer.
        - Calculates required margin at current leverage (5x).
        - Risk amount is capped at max risk per trade (2% of equity), targeting 1% equity loss for 1:2 R:R.
        Returns: (quantized_qty, risk_amount, notional_value, status)
        """
        if entry_price <= 0:
            return 0.0, 0.0, 0.0, 'INVALID_PRICE_PARAMETERS'

        filters = self.get_symbol_filter(symbol)

        # Risk amount targeting stop_loss_equity_pct (1% of equity), bounded by max risk (2%)
        risk_amount = equity * self.stop_loss_equity_pct
        if risk_amount > (equity * self.risk_per_trade):
            risk_amount = equity * self.risk_per_trade

        min_notional = max(filters.min_notional, 5.0)
        target_notional = min_notional + 0.20  # Buffer to ensure rounding stays >= min_notional

        # If a stop_loss is provided, compute risk-based quantity
        if stop_loss > 0 and abs(entry_price - stop_loss) > 0:
            stop_dist = abs(entry_price - stop_loss)
            risk_based_qty = risk_amount / stop_dist
            risk_based_notional = risk_based_qty * entry_price
            if risk_based_notional >= target_notional:
                raw_qty = risk_based_qty
            else:
                raw_qty = target_notional / entry_price
        else:
            raw_qty = target_notional / entry_price

        step = filters.step_size
        if step > 0:
            quantized_qty = math.ceil(raw_qty / step) * step
            quantized_qty = round(quantized_qty, filters.quantity_precision)
        else:
            quantized_qty = round(raw_qty, filters.quantity_precision)

        if quantized_qty < filters.min_qty:
            quantized_qty = filters.min_qty

        notional = quantized_qty * entry_price
        if notional < min_notional and step > 0:
            quantized_qty = round(quantized_qty + step, filters.quantity_precision)
            notional = quantized_qty * entry_price

        margin_required = notional / max(self.default_leverage, 1)
        if margin_required > equity:
            return 0.0, margin_required, notional, 'INSUFFICIENT_MARGIN'

        return quantized_qty, risk_amount, notional, 'OK'

    def record_trade_closed(self, pnl: float, exit_ts_ms: Optional[int] = None):
        """
        Updates daily PnL, win/loss streaks, and triggers cooldowns if needed.
        """
        self.daily_state.realized_daily_pnl += pnl
        self.daily_state.current_equity += pnl
        self.daily_state.daily_trade_count += 1

        if pnl < 0:
            self.daily_state.consecutive_losses += 1
            if self.daily_state.consecutive_losses >= self.max_consecutive_losses:
                # 4-hour cooldown
                now_ms = exit_ts_ms if exit_ts_ms else int(datetime.now(timezone.utc).timestamp() * 1000)
                self.daily_state.cooldown_until_ts = now_ms + (CONSECUTIVE_LOSS_COOLDOWN_HOURS * 3600 * 1000)
        else:
            self.daily_state.consecutive_losses = 0

    def add_open_position(self, symbol: str, pos_data: Dict[str, Any]):
        self.open_positions[symbol] = pos_data

    def remove_open_position(self, symbol: str):
        if symbol in self.open_positions:
            del self.open_positions[symbol]
