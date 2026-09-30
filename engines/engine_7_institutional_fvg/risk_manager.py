"""
Institutional Risk Manager & Position Sizer
Implements Sections 33-42:
- 1% Account Risk Sizing with Binance Step Size & Min Notional Formatting
- Daily Loss Limit (2% UTC equity)
- Consecutive Loss Cooldown (3 losses -> 4 hours)
- Daily Trade Cap (5 trades)
- Max Open Positions (3) & Symbol Uniqueness
- UTC Session Filter (07:00-11:00, 13:00-17:00)
- Volatility Ratio Filter
"""

import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


@dataclass
class SymbolSpecs:
    symbol: str
    tick_size: float = 0.01
    step_size: float = 0.001
    price_precision: int = 2
    qty_precision: int = 3
    min_qty: float = 0.001
    min_notional: float = 5.0
    max_leverage: int = 50
    status: str = "TRADING"


@dataclass
class PositionSizeResult:
    is_valid: bool
    symbol: str
    entry_price: float
    sl_price: float
    risk_amount: float
    stop_distance: float
    raw_qty: float
    formatted_qty: float
    notional_value: float
    required_margin: float
    leverage: int
    rejection_reason: Optional[str] = None


@dataclass
class RiskState:
    current_utc_date: str = ""
    daily_starting_equity: float = 10000.0
    daily_current_equity: float = 10000.0
    daily_realized_pnl: float = 0.0
    daily_trades_count: int = 0
    consecutive_losses: int = 0
    cooldown_until_ts: float = 0.0
    open_positions: Dict[str, dict] = field(default_factory=dict)


class RiskManager:
    def __init__(
        self,
        risk_per_trade: float = 0.01,
        max_daily_loss: float = 0.02,
        max_consecutive_losses: int = 3,
        cooldown_hours: float = 4.0,
        max_daily_trades: int = 5,
        max_open_positions: int = 3,
        default_leverage: int = 5,
        sessions: Optional[List[Tuple[int, int]]] = None
    ):
        self.risk_per_trade = risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_seconds = cooldown_hours * 3600
        self.max_daily_trades = max_daily_trades
        self.max_open_positions = max_open_positions
        self.default_leverage = default_leverage
        self.sessions = sessions or [(7, 11), (13, 17)]
        self.state = RiskState()
        self._update_utc_day()

    def _update_utc_day(self, current_ts: Optional[float] = None) -> None:
        """Resets daily counters on new UTC day."""
        now_dt = datetime.fromtimestamp(current_ts or time.time(), tz=timezone.utc)
        today_str = now_dt.strftime("%Y-%m-%d")
        if self.state.current_utc_date != today_str:
            self.state.current_utc_date = today_str
            self.state.daily_starting_equity = self.state.daily_current_equity
            self.state.daily_realized_pnl = 0.0
            self.state.daily_trades_count = 0

    def is_session_active(self, current_ts: Optional[float] = None) -> bool:
        """Checks if current time falls within configured UTC trading windows."""
        now_dt = datetime.fromtimestamp(current_ts or time.time(), tz=timezone.utc)
        curr_hour = now_dt.hour
        for start_h, end_h in self.sessions:
            if start_h <= curr_hour < end_h:
                return True
        return False

    def can_open_new_trade(
        self,
        symbol: str,
        current_ts: Optional[float] = None,
        volatility_ratio: float = 1.0,
        emergency_stop: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """Validates all global risk constraints."""
        ts = current_ts or time.time()
        self._update_utc_day(ts)

        if emergency_stop:
            return False, "REJECTED_EMERGENCY_STOP"

        # 1. Trading Session Check (Section 41)
        if not self.is_session_active(ts):
            return False, "REJECTED_OUTSIDE_SESSION"

        # 2. Cooldown Check (Section 36)
        if ts < self.state.cooldown_until_ts:
            return False, "REJECTED_COOLDOWN_ACTIVE"

        # 3. Daily Loss Limit (Section 35)
        if self.state.daily_starting_equity > 0:
            daily_loss_pct = (self.state.daily_starting_equity - self.state.daily_current_equity) / self.state.daily_starting_equity
            if daily_loss_pct >= self.max_daily_loss:
                return False, "REJECTED_DAILY_LIMIT"

        # 4. Daily Trades Limit (Section 37)
        if self.state.daily_trades_count >= self.max_daily_trades:
            return False, "REJECTED_DAILY_TRADES_EXCEEDED"

        # 5. Max Open Positions (Section 38)
        if len(self.state.open_positions) >= self.max_open_positions:
            return False, "REJECTED_MAX_POSITIONS"

        # 6. One Position per Symbol (Section 39)
        if symbol in self.state.open_positions:
            return False, "REJECTED_EXISTING_POSITION"

        # 7. Volatility Filter (Section 42)
        if volatility_ratio > 2.5:
            return False, "REJECTED_HIGH_VOLATILITY"

        return True, None

    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        sl_price: float,
        account_equity: float,
        specs: SymbolSpecs,
        leverage: Optional[int] = None,
        max_leverage_cap: int = 5
    ) -> PositionSizeResult:
        """
        Calculates exact 2% maximum equity risk position sizing at 5x leverage:
          - Dollar risk at Stop Loss = account_equity × 2% ($0.265 USDT on $13.25)
          - Position quantity = dollar_risk / stop_distance
          - Take profit is set at 1:2 Risk/Reward ratio (reward = 2 × risk)
          - Leverage is 5x fixed
        """
        lev = leverage or self.default_leverage
        lev = min(lev, specs.max_leverage, max_leverage_cap)

        stop_dist = abs(entry_price - sl_price)
        if stop_dist <= 0 or entry_price <= 0:
            return PositionSizeResult(
                is_valid=False, symbol=symbol, entry_price=entry_price, sl_price=sl_price,
                risk_amount=0.0, stop_distance=0.0, raw_qty=0.0, formatted_qty=0.0,
                notional_value=0.0, required_margin=0.0, leverage=lev,
                rejection_reason="INVALID_STOP_DISTANCE"
            )

        # 2% Maximum Equity Risk Amount
        risk_amount = account_equity * self.risk_per_trade  # e.g. $13.25 × 0.02 = $0.265 USDT
        raw_qty = risk_amount / stop_dist

        # Step size precision rounding (floor)
        if specs.step_size > 0:
            factor = 1.0 / specs.step_size
            formatted_qty = math.floor(raw_qty * factor) / factor
            formatted_qty = round(formatted_qty, specs.qty_precision)
        else:
            formatted_qty = round(raw_qty, specs.qty_precision)

        notional = formatted_qty * entry_price

        # Cap position size by maximum allowable margin at 5x leverage (up to 85% equity)
        max_allowable_qty = (account_equity * lev * 0.85) / entry_price
        if formatted_qty > max_allowable_qty:
            if specs.step_size > 0:
                factor = 1.0 / specs.step_size
                formatted_qty = math.floor(max_allowable_qty * factor) / factor
                formatted_qty = round(formatted_qty, specs.qty_precision)
            else:
                formatted_qty = round(max_allowable_qty, specs.qty_precision)
            notional = formatted_qty * entry_price

        # Check minQty
        if formatted_qty < specs.min_qty:
            formatted_qty = specs.min_qty
            notional = formatted_qty * entry_price

        # Check Binance minNotional (5.00 USDT)
        if notional < specs.min_notional:
            min_notional_qty = math.ceil((specs.min_notional / entry_price) / specs.step_size) * specs.step_size if specs.step_size > 0 else (specs.min_notional / entry_price)
            min_notional_qty = round(min_notional_qty, specs.qty_precision)
            min_notional_risk = min_notional_qty * stop_dist

            # Allow if dollar risk at minNotional is within ~2.3% of total equity
            if min_notional_risk <= (account_equity * self.risk_per_trade * 1.15):
                formatted_qty = min_notional_qty
                notional = formatted_qty * entry_price
                risk_amount = min_notional_risk
            else:
                return PositionSizeResult(
                    is_valid=False, symbol=symbol, entry_price=entry_price, sl_price=sl_price,
                    risk_amount=risk_amount, stop_distance=stop_dist, raw_qty=raw_qty,
                    formatted_qty=formatted_qty, notional_value=notional, required_margin=0.0,
                    leverage=lev, rejection_reason="RISK_EXCEEDS_2_PERCENT_CAP"
                )

        required_margin = notional / lev
        if required_margin > (account_equity * 0.90):
            return PositionSizeResult(
                is_valid=False, symbol=symbol, entry_price=entry_price, sl_price=sl_price,
                risk_amount=risk_amount, stop_distance=stop_dist, raw_qty=raw_qty,
                formatted_qty=formatted_qty, notional_value=notional, required_margin=required_margin,
                leverage=lev, rejection_reason="INSUFFICIENT_MARGIN"
            )

        return PositionSizeResult(
            is_valid=True, symbol=symbol, entry_price=entry_price, sl_price=sl_price,
            risk_amount=risk_amount, stop_distance=stop_dist, raw_qty=raw_qty,
            formatted_qty=formatted_qty, notional_value=notional, required_margin=required_margin,
            leverage=lev, rejection_reason=None
        )

    def record_trade_opened(self, symbol: str, position_info: dict, current_ts: Optional[float] = None) -> None:
        ts = current_ts or time.time()
        self._update_utc_day(ts)
        self.state.open_positions[symbol] = position_info
        self.state.daily_trades_count += 1

    def record_trade_closed(
        self,
        symbol: str,
        pnl: float,
        current_equity: float,
        current_ts: Optional[float] = None
    ) -> None:
        ts = current_ts or time.time()
        self._update_utc_day(ts)
        if symbol in self.state.open_positions:
            del self.state.open_positions[symbol]

        self.state.daily_current_equity = current_equity
        self.state.daily_realized_pnl += pnl

        if pnl < 0:
            self.state.consecutive_losses += 1
            if self.state.consecutive_losses >= self.max_consecutive_losses:
                self.state.cooldown_until_ts = ts + self.cooldown_seconds
        else:
            self.state.consecutive_losses = 0
