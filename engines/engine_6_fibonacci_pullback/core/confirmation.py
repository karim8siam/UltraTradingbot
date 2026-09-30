"""
5M Structure Shift & Displacement Confirmation Engine
Sections 16, 17, 18, 19 Specification
"""

from typing import List, Optional, Tuple
from core.types import Candle, PositionSide
from core.indicators import calculate_average_body
from core.swings import SwingDetector
from config.constants import (
    AVG_BODY_PERIOD,
    DISPLACEMENT_BODY_MULTIPLIER,
    MIN_BODY_PERCENTAGE,
)


class ConfirmationEngine:
    def __init__(
        self,
        avg_body_period: int = AVG_BODY_PERIOD,
        body_multiplier: float = DISPLACEMENT_BODY_MULTIPLIER,
        min_body_percentage: float = MIN_BODY_PERCENTAGE,
    ):
        self.avg_body_period = avg_body_period
        self.body_multiplier = body_multiplier
        self.min_body_percentage = min_body_percentage
        self.swing_detector = SwingDetector(swing_length=2)

    def check_displacement(
        self, candles_5m: List[Candle], candle_idx: int = -1
    ) -> Tuple[bool, float, float]:
        if candle_idx < 0:
            target_idx = len(candles_5m) + candle_idx
        else:
            target_idx = candle_idx

        if target_idx < self.avg_body_period:
            return False, 0.0, 0.0

        target_candle = candles_5m[target_idx]
        avg_body = calculate_average_body(candles_5m, self.avg_body_period, target_idx)
        if avg_body <= 0.0:
            return False, 0.0, 0.0

        current_body = target_candle.body_size
        body_pct = target_candle.body_percentage

        is_large_enough = current_body >= (avg_body * self.body_multiplier)
        is_clean_body = body_pct >= self.min_body_percentage

        return (is_large_enough and is_clean_body), current_body, avg_body

    def check_bullish_confirmation(
        self,
        candles_5m: List[Candle],
        pullback_start_idx: int,
        impulse_high: float = float('inf'),
    ) -> Tuple[bool, bool, Optional[float], Optional[Candle], int]:
        if len(candles_5m) <= pullback_start_idx + 2:
            return False, False, None, None, -1

        pullback_candles = candles_5m[pullback_start_idx:]
        latest_idx = len(candles_5m) - 1
        latest_candle = candles_5m[latest_idx]

        # Confirmation must occur before price exceeds the original impulse high
        if latest_candle.close >= impulse_high or not latest_candle.is_bullish:
            return False, False, None, None, -1

        # Identify local lower highs during the pullback prior to the lowest low (excluding index 0 impulse peak)
        lowest_idx = min(range(len(pullback_candles)), key=lambda k: pullback_candles[k].low)
        if lowest_idx > 1:
            recent_lh = max(c.high for c in pullback_candles[1:lowest_idx])
        elif len(pullback_candles) > 2:
            recent_lh = pullback_candles[1].high
        else:
            recent_lh = pullback_candles[0].high * 0.999

        structure_shift = latest_candle.close > recent_lh

        is_disp, _, _ = self.check_displacement(candles_5m, latest_idx)
        displacement = is_disp and latest_candle.is_bullish

        return structure_shift, displacement, recent_lh, latest_candle, latest_idx

    def check_bearish_confirmation(
        self,
        candles_5m: List[Candle],
        pullback_start_idx: int,
        impulse_low: float = float('-inf'),
    ) -> Tuple[bool, bool, Optional[float], Optional[Candle], int]:
        if len(candles_5m) <= pullback_start_idx + 2:
            return False, False, None, None, -1

        pullback_candles = candles_5m[pullback_start_idx:]
        latest_idx = len(candles_5m) - 1
        latest_candle = candles_5m[latest_idx]

        # Confirmation must occur before price exceeds the original impulse low
        if latest_candle.close <= impulse_low or not latest_candle.is_bearish:
            return False, False, None, None, -1

        # Identify local higher lows during the pullback prior to the highest high (excluding index 0 impulse trough)
        highest_idx = max(range(len(pullback_candles)), key=lambda k: pullback_candles[k].high)
        if highest_idx > 1:
            recent_hl = min(c.low for c in pullback_candles[1:highest_idx])
        elif len(pullback_candles) > 2:
            recent_hl = pullback_candles[1].low
        else:
            recent_hl = pullback_candles[0].low * 1.001

        structure_shift = latest_candle.close < recent_hl

        is_disp, _, _ = self.check_displacement(candles_5m, latest_idx)
        displacement = is_disp and latest_candle.is_bearish

        return structure_shift, displacement, recent_hl, latest_candle, latest_idx
