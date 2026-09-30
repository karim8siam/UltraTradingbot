"""
1H Structure Confirmation, Displacement, Entry Price, Stop Loss, and Take Profit Engine.
"""

from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np

from .indicators import calculate_average_body, is_displacement_candle
from .structure import SwingDetector, SwingPoint
from .impulse_pullback import PullbackZone


@dataclass
class ConfirmationSignal:
    is_confirmed: bool
    is_bullish: bool
    confirmation_candle_index: int
    confirmation_high: float
    confirmation_low: float
    confirmation_close: float
    broken_level: float
    entry_price: float
    stop_loss: float
    target_tp1: float
    target_tp2: Optional[float]
    risk_distance: float
    reward_distance: float
    rr_ratio: float
    displacement_metrics: Dict[str, Any]
    rejection_reason: Optional[str] = None


class ConfirmationEngine:
    def __init__(self, min_rr: float = 2.5, swing_length: int = 2,
                 sl_atr_buffer: float = 0.10, timeout_bars: int = 6):
        self.min_rr = min_rr
        self.swing_length = swing_length
        self.sl_atr_buffer = sl_atr_buffer
        self.timeout_bars = timeout_bars
        self.swing_detector = SwingDetector(swing_length=swing_length)

    def evaluate_1h_confirmation(self, one_h_opens: np.ndarray, one_h_highs: np.ndarray,
                                 one_h_lows: np.ndarray, one_h_closes: np.ndarray,
                                 pullback: PullbackZone, four_h_swings: List[SwingPoint],
                                 is_bullish: bool) -> ConfirmationSignal:
        """
        Sections 20-32:
        Evaluates 1H structure break, displacement, entry limit price, structural SL, and TP targets.
        """
        n = len(one_h_closes)
        if n < 15:
            return ConfirmationSignal(
                is_confirmed=False, is_bullish=is_bullish, confirmation_candle_index=-1,
                confirmation_high=0, confirmation_low=0, confirmation_close=0, broken_level=0,
                entry_price=0, stop_loss=0, target_tp1=0, target_tp2=None, risk_distance=0,
                reward_distance=0, rr_ratio=0, displacement_metrics={}, rejection_reason="REJECTED_NO_1H_CONFIRMATION"
            )

        # Detect 1H swings
        swings_1h = self.swing_detector.find_swings(one_h_highs, one_h_lows)
        curr_open = float(one_h_opens[-1])
        curr_high = float(one_h_highs[-1])
        curr_low = float(one_h_lows[-1])
        curr_close = float(one_h_closes[-1])

        # Avg body of preceding 10 1H candles
        avg_body_10 = calculate_average_body(one_h_opens[:-1], one_h_closes[:-1], period=10)

        # Displacement test on current 1H candle
        has_displacement, disp_metrics = is_displacement_candle(
            open_price=curr_open, high=curr_high, low=curr_low, close=curr_close,
            avg_body=avg_body_10, is_bullish=is_bullish
        )

        if not has_displacement:
            return ConfirmationSignal(
                is_confirmed=False, is_bullish=is_bullish, confirmation_candle_index=n - 1,
                confirmation_high=curr_high, confirmation_low=curr_low, confirmation_close=curr_close,
                broken_level=0, entry_price=0, stop_loss=0, target_tp1=0, target_tp2=None,
                risk_distance=0, reward_distance=0, rr_ratio=0, displacement_metrics=disp_metrics,
                rejection_reason="REJECTED_WEAK_DISPLACEMENT"
            )

        if is_bullish:
            # Section 21: Long Confirmation - find 1H lower high formed during pullback
            sh_1h = [s for s in swings_1h if s.is_high and s.price < pullback.current_pullback_high]
            if not sh_1h:
                # If no formal swing high yet, use highest high of recent 3 candles
                recent_sh = float(np.max(one_h_highs[-4:-1])) if n >= 4 else curr_high
            else:
                recent_sh = sh_1h[-1].price

            # Close must break above the most recent lower high
            if curr_close <= recent_sh:
                return ConfirmationSignal(
                    is_confirmed=False, is_bullish=True, confirmation_candle_index=n - 1,
                    confirmation_high=curr_high, confirmation_low=curr_low, confirmation_close=curr_close,
                    broken_level=recent_sh, entry_price=0, stop_loss=0, target_tp1=0, target_tp2=None,
                    risk_distance=0, reward_distance=0, rr_ratio=0, displacement_metrics=disp_metrics,
                    rejection_reason="REJECTED_NO_1H_CONFIRMATION"
                )

            # Section 26: 50% midpoint entry
            entry_price = curr_low + ((curr_high - curr_low) * 0.50)

            # Section 28: Long Stop Loss = PullbackLow - (ATR14_4H * 0.10)
            sl_buffer = pullback.impulse.atr14 * self.sl_atr_buffer
            stop_loss = pullback.current_pullback_low - sl_buffer
            risk_dist = entry_price - stop_loss

            if risk_dist <= 0:
                return ConfirmationSignal(
                    is_confirmed=False, is_bullish=True, confirmation_candle_index=n - 1,
                    confirmation_high=curr_high, confirmation_low=curr_low, confirmation_close=curr_close,
                    broken_level=recent_sh, entry_price=entry_price, stop_loss=stop_loss,
                    target_tp1=0, target_tp2=None, risk_distance=risk_dist, reward_distance=0,
                    rr_ratio=0, displacement_metrics=disp_metrics, rejection_reason="REJECTED_STRUCTURE_INVALIDATED"
                )

            # Section 30, 31: Targets from 4H structure
            potential_targets = [s.price for s in four_h_swings if s.is_high and s.price > entry_price]
            if not potential_targets:
                # Use impulse high as primary
                potential_targets = [pullback.impulse.end_price]

            target_tp1 = 0.0
            target_tp2 = None
            valid_rr = False
            best_rr = 0.0

            for tp in potential_targets:
                reward = tp - entry_price
                rr = reward / risk_dist
                if rr >= self.min_rr:
                    target_tp1 = tp
                    best_rr = rr
                    valid_rr = True
                    # Find secondary target if available
                    idx = potential_targets.index(tp)
                    if idx + 1 < len(potential_targets):
                        target_tp2 = potential_targets[idx + 1]
                    break

            if not valid_rr:
                # If target is too close, calculate extended target
                target_tp1 = entry_price + (risk_dist * self.min_rr)
                best_rr = self.min_rr
                valid_rr = True

            reward_dist = target_tp1 - entry_price

            return ConfirmationSignal(
                is_confirmed=True,
                is_bullish=True,
                confirmation_candle_index=n - 1,
                confirmation_high=curr_high,
                confirmation_low=curr_low,
                confirmation_close=curr_close,
                broken_level=recent_sh,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_tp1=target_tp1,
                target_tp2=target_tp2,
                risk_distance=risk_dist,
                reward_distance=reward_dist,
                rr_ratio=best_rr,
                displacement_metrics=disp_metrics,
                rejection_reason=None
            )

        else:
            # Section 22: Short Confirmation - find 1H higher low formed during pullback
            sl_1h = [s for s in swings_1h if (not s.is_high) and s.price > pullback.current_pullback_low]
            if not sl_1h:
                recent_sl = float(np.min(one_h_lows[-4:-1])) if n >= 4 else curr_low
            else:
                recent_sl = sl_1h[-1].price

            # Close must break below the most recent higher low
            if curr_close >= recent_sl:
                return ConfirmationSignal(
                    is_confirmed=False, is_bullish=False, confirmation_candle_index=n - 1,
                    confirmation_high=curr_high, confirmation_low=curr_low, confirmation_close=curr_close,
                    broken_level=recent_sl, entry_price=0, stop_loss=0, target_tp1=0, target_tp2=None,
                    risk_distance=0, reward_distance=0, rr_ratio=0, displacement_metrics=disp_metrics,
                    rejection_reason="REJECTED_NO_1H_CONFIRMATION"
                )

            # Section 26: 50% midpoint entry
            entry_price = curr_high - ((curr_high - curr_low) * 0.50)

            # Section 29: Short Stop Loss = PullbackHigh + (ATR14_4H * 0.10)
            sl_buffer = pullback.impulse.atr14 * self.sl_atr_buffer
            stop_loss = pullback.current_pullback_high + sl_buffer
            risk_dist = stop_loss - entry_price

            if risk_dist <= 0:
                return ConfirmationSignal(
                    is_confirmed=False, is_bullish=False, confirmation_candle_index=n - 1,
                    confirmation_high=curr_high, confirmation_low=curr_low, confirmation_close=curr_close,
                    broken_level=recent_sl, entry_price=entry_price, stop_loss=stop_loss,
                    target_tp1=0, target_tp2=None, risk_distance=risk_dist, reward_distance=0,
                    rr_ratio=0, displacement_metrics=disp_metrics, rejection_reason="REJECTED_STRUCTURE_INVALIDATED"
                )

            potential_targets = [s.price for s in four_h_swings if (not s.is_high) and s.price < entry_price]
            if not potential_targets:
                potential_targets = [pullback.impulse.end_price]

            target_tp1 = 0.0
            target_tp2 = None
            valid_rr = False
            best_rr = 0.0

            for tp in potential_targets:
                reward = entry_price - tp
                rr = reward / risk_dist
                if rr >= self.min_rr:
                    target_tp1 = tp
                    best_rr = rr
                    valid_rr = True
                    idx = potential_targets.index(tp)
                    if idx + 1 < len(potential_targets):
                        target_tp2 = potential_targets[idx + 1]
                    break

            if not valid_rr:
                target_tp1 = entry_price - (risk_dist * self.min_rr)
                best_rr = self.min_rr
                valid_rr = True

            reward_dist = entry_price - target_tp1

            return ConfirmationSignal(
                is_confirmed=True,
                is_bullish=False,
                confirmation_candle_index=n - 1,
                confirmation_high=curr_high,
                confirmation_low=curr_low,
                confirmation_close=curr_close,
                broken_level=recent_sl,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_tp1=target_tp1,
                target_tp2=target_tp2,
                risk_distance=risk_dist,
                reward_distance=reward_dist,
                rr_ratio=best_rr,
                displacement_metrics=disp_metrics,
                rejection_reason=None
            )
