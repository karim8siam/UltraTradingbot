import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List
from strategy.models import SMCSetup, TradeSide

logger = logging.getLogger("SMC_RiskManager")

class RiskManager:
    def __init__(self, risk_per_trade: float = 0.01, max_daily_loss: float = 0.02,
                 max_consecutive_losses: int = 3, cooldown_hours: int = 4,
                 max_daily_trades: int = 5, max_open_positions: int = 3,
                 default_leverage: int = 5):
        self.risk_per_trade = risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_hours = cooldown_hours
        self.max_daily_trades = max_daily_trades
        self.max_open_positions = max_open_positions
        self.default_leverage = default_leverage

        # Tracking state
        self.current_consecutive_losses = 0
        self.cooldown_until: Optional[datetime] = None
        self.emergency_stop: bool = False

    def check_trade_allowed(self, current_equity: float, starting_daily_equity: float,
                            today_realized_pnl: float, today_trade_count: int,
                            open_positions_count: int, symbol_has_open_position: bool,
                            current_time: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Validates all risk rules before approving an order.
        """
        now_utc = current_time or datetime.now(timezone.utc)

        # 1. Emergency stop check
        if self.emergency_stop:
            return False, "REJECTED_EMERGENCY_STOP_ACTIVE"

        # 2. Cooldown check
        if self.cooldown_until and now_utc < self.cooldown_until:
            rem = (self.cooldown_until - now_utc).total_seconds() / 60.0
            return False, f"REJECTED_COOLDOWN_ACTIVE (Remaining: {rem:.1f} mins)"

        # 3. Maximum daily loss check (2% of starting daily equity)
        if starting_daily_equity > 0:
            daily_loss_pct = (today_realized_pnl / starting_daily_equity)
            if daily_loss_pct <= -self.max_daily_loss:
                return False, f"REJECTED_DAILY_LOSS_LIMIT_REACHED (Loss: {daily_loss_pct*100:.2f}%)"

        # 4. Maximum daily trades check (5 trades/day)
        if today_trade_count >= self.max_daily_trades:
            return False, f"REJECTED_MAX_DAILY_TRADES_REACHED ({today_trade_count}/{self.max_daily_trades})"

        # 5. Maximum open positions check (3 open positions)
        if open_positions_count >= self.max_open_positions:
            return False, f"REJECTED_MAX_OPEN_POSITIONS_REACHED ({open_positions_count}/{self.max_open_positions})"

        # 6. One position per symbol
        if symbol_has_open_position:
            return False, "REJECTED_EXISTING_POSITION_FOR_SYMBOL"

        return True, "APPROVED"

    def record_trade_outcome(self, is_win: bool, current_time: Optional[datetime] = None):
        now_utc = current_time or datetime.now(timezone.utc)
        if is_win:
            self.current_consecutive_losses = 0
        else:
            self.current_consecutive_losses += 1
            if self.current_consecutive_losses >= self.max_consecutive_losses:
                self.cooldown_until = now_utc + timedelta(hours=self.cooldown_hours)
                logger.warning(f"Reached {self.current_consecutive_losses} consecutive losses. Cooldown activated until {self.cooldown_until.isoformat()}")

    def calculate_position_size(self, account_equity: float, entry_price: float,
                                stop_loss: float, symbol_rules: Dict[str, Any]) -> Tuple[float, float, float, str]:
        """
        Calculates position size risking strictly 1% of account equity.
        Returns (position_qty, notional, risk_amount, validation_status)
        """
        stop_distance = abs(entry_price - stop_loss)
        if stop_distance <= 0:
            return 0.0, 0.0, 0.0, "INVALID_STOP_DISTANCE"

        risk_amount = account_equity * self.risk_per_trade
        raw_qty = risk_amount / stop_distance

        # Cap max notional to leverage limit (e.g. 5x equity)
        max_allowed_notional = account_equity * self.default_leverage
        if (raw_qty * entry_price) > max_allowed_notional:
            raw_qty = max_allowed_notional / entry_price

        step_size = symbol_rules.get("stepSize", 0.001)
        min_qty = symbol_rules.get("minQty", 0.001)
        min_notional = symbol_rules.get("minNotional", 5.0)
        qty_precision = symbol_rules.get("quantityPrecision", 3)

        # Precision rounding
        if step_size > 0:
            steps = int(raw_qty / step_size)
            rounded_qty = round(steps * step_size, qty_precision)
        else:
            rounded_qty = round(raw_qty, qty_precision)

        notional = rounded_qty * entry_price

        if rounded_qty < min_qty:
            return rounded_qty, notional, risk_amount, f"QUANTITY_BELOW_MIN ({rounded_qty} < {min_qty})"

        if notional < min_notional:
            return rounded_qty, notional, risk_amount, f"NOTIONAL_BELOW_MIN ({notional:.2f} < {min_notional})"

        return rounded_qty, notional, risk_amount, "VALID"
