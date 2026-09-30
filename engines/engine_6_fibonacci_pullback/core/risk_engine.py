"""
Risk Management & Order Geometry Engine
Sections 22, 23, 24, 25, 26, 27, 28, 29, 30
"""

import math
from typing import Optional, Tuple
from core.types import Candle, ImpulseLeg, PositionSide, SetupRejectReason
from config.constants import (
    RISK_PER_TRADE,
    MIN_RR,
    SL_ATR_BUFFER,
    MAX_ENTRY_DEVIATION_ATR,
)


class RiskEngine:
    def __init__(
        self,
        risk_per_trade: float = RISK_PER_TRADE,
        min_rr: float = MIN_RR,
        sl_atr_buffer: float = SL_ATR_BUFFER,
        max_entry_dev_atr: float = MAX_ENTRY_DEVIATION_ATR,
    ):
        self.risk_per_trade = risk_per_trade
        self.min_rr = min_rr
        self.sl_atr_buffer = sl_atr_buffer
        self.max_entry_dev_atr = max_entry_dev_atr

    def calculate_entry_price(
        self,
        confirmation_candle: Candle,
        current_price: float,
        atr14: float,
        side: PositionSide,
    ) -> Tuple[Optional[float], Optional[SetupRejectReason]]:
        """
        Calculates 50% retracement of the confirmation candle body.
        Enforces No-Chasing rule: abs(current_price - planned_entry) <= 0.25 * ATR14.
        """
        # 50% of confirmation candle body
        planned_entry = (confirmation_candle.open + confirmation_candle.close) / 2.0

        max_dev = atr14 * self.max_entry_dev_atr
        if abs(current_price - planned_entry) > max_dev:
            # If current price is too far away from planned entry, reject setup (No chasing)
            return None, SetupRejectReason.REJECTED_CHASE_DEVIATION

        return planned_entry, None

    def calculate_stop_loss(
        self,
        side: PositionSide,
        pullback_low: float,
        pullback_high: float,
        entry_price: float,
        atr14: float,
    ) -> Tuple[Optional[float], Optional[SetupRejectReason]]:
        """
        Calculates structural Stop Loss with ATR buffer:
        - Long: PullbackLow - (0.10 * ATR14) -> must be < pullback_low and < entry
        - Short: PullbackHigh + (0.10 * ATR14) -> must be > pullback_high and > entry
        """
        buffer = atr14 * self.sl_atr_buffer

        if side == PositionSide.LONG:
            sl = pullback_low - buffer
            if sl >= pullback_low or sl >= entry_price:
                return None, SetupRejectReason.REJECTED_INVALID_SL_TP
            return sl, None
        else:
            sl = pullback_high + buffer
            if sl <= pullback_high or sl <= entry_price:
                return None, SetupRejectReason.REJECTED_INVALID_SL_TP
            return sl, None

    def calculate_take_profit(
        self,
        side: PositionSide,
        entry_price: float,
        sl_price: float,
        impulse: ImpulseLeg,
    ) -> Tuple[Optional[float], float, Optional[SetupRejectReason]]:
        """
        Calculates structural Take Profit and verifies RR >= 2.0:
        - Long: Target = impulse.high. If RR < 2.0, check extended target (1.272 extension).
        - Short: Target = impulse.low. If RR < 2.0, check extended target (1.272 extension).
        Returns (tp_price, rr, reject_reason).
        """
        stop_dist = abs(entry_price - sl_price)
        if stop_dist <= 0:
            return None, 0.0, SetupRejectReason.REJECTED_INVALID_SL_TP

        if side == PositionSide.LONG:
            target = impulse.high
            reward = target - entry_price
            rr = reward / stop_dist

            if rr < self.min_rr:
                # Check extended target: 1.272 Fibonacci extension of the impulse
                extended_target = impulse.low + (impulse.size * 1.272)
                ext_reward = extended_target - entry_price
                ext_rr = ext_reward / stop_dist
                if ext_rr >= self.min_rr:
                    return extended_target, ext_rr, None
                else:
                    return None, rr, SetupRejectReason.REJECTED_LOW_RR

            return target, rr, None

        else:
            target = impulse.low
            reward = entry_price - target
            rr = reward / stop_dist

            if rr < self.min_rr:
                # Check extended target for short
                extended_target = impulse.high - (impulse.size * 1.272)
                ext_reward = entry_price - extended_target
                ext_rr = ext_reward / stop_dist
                if ext_rr >= self.min_rr:
                    return extended_target, ext_rr, None
                else:
                    return None, rr, SetupRejectReason.REJECTED_LOW_RR

            return target, rr, None

    def calculate_position_size(
        self,
        account_equity: float,
        entry_price: float,
        sl_price: float,
        step_size: float = 0.001,
        min_qty: float = 0.001,
        min_notional: float = 5.0,
        qty_precision: int = 3,
        leverage: int = 5,
    ) -> Tuple[float, float, bool]:
        """
        Calculates position size for 1% risk of account equity:
        RiskAmount = AccountEquity * 0.01
        RawQty = RiskAmount / abs(Entry - SL)
        Returns (formatted_qty, risk_amount, is_valid).
        """
        if account_equity <= 0 or entry_price <= 0 or sl_price <= 0:
            return 0.0, 0.0, False

        stop_dist = abs(entry_price - sl_price)
        if stop_dist <= 0:
            return 0.0, 0.0, False

        risk_amount = account_equity * self.risk_per_trade
        raw_qty = risk_amount / stop_dist

        # Step size truncation (round down to prevent over-risking)
        if step_size > 0:
            precision_factor = 10**qty_precision
            steps = math.floor(raw_qty / step_size)
            qty = round(steps * step_size, qty_precision)
        else:
            qty = round(raw_qty, qty_precision)

        if qty < min_qty:
            return 0.0, risk_amount, False

        notional = qty * entry_price
        if notional < min_notional:
            return 0.0, risk_amount, False

        # Verify margin requirement does not exceed available equity with leverage
        required_margin = notional / max(leverage, 1)
        if required_margin > account_equity:
            return 0.0, risk_amount, False

        return qty, risk_amount, True
