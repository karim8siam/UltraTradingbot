"""
Deterministic 15M Impulse Leg Detection
Sections 8, 9, 10 Specification
"""

from typing import List, Optional
from core.types import Candle, ImpulseLeg, PositionSide, SwingPoint, TrendType
from core.swings import SwingDetector
from core.indicators import get_latest_atr
from config.constants import IMPULSE_MIN_ATR, ATR_PERIOD


class ImpulseDetector:
    def __init__(
        self,
        swing_detector: SwingDetector = None,
        min_atr_multiplier: float = IMPULSE_MIN_ATR,
        atr_period: int = ATR_PERIOD,
    ):
        self.swing_detector = swing_detector or SwingDetector()
        self.min_atr_multiplier = min_atr_multiplier
        self.atr_period = atr_period

    def detect_impulse(
        self,
        symbol: str,
        candles_15m: List[Candle],
        bias_4h: TrendType,
        bias_1h: TrendType,
    ) -> Optional[ImpulseLeg]:
        """
        Identifies a valid 15M impulse leg consistent with HTF bias:
        - Bullish: 4H & 1H Bullish, Low -> High swing where High > Low, High index > Low index, (High - Low) >= 2.0 * ATR14
        - Bearish: 4H & 1H Bearish, High -> Low swing where Low < High, Low index > High index, (High - Low) >= 2.0 * ATR14
        """
        if bias_4h != bias_1h or bias_4h == TrendType.NEUTRAL:
            return None

        if len(candles_15m) < self.atr_period + 10:
            return None

        atr14 = get_latest_atr(candles_15m, self.atr_period)
        if atr14 <= 0.0:
            return None

        min_move = atr14 * self.min_atr_multiplier

        all_swings = self.swing_detector.find_all_swings(candles_15m, "15m")
        if len(all_swings) < 2:
            return None

        if bias_4h == TrendType.BULLISH:
            # Look for recent Swing Low -> higher Swing High
            lows = [s for s in all_swings if s.is_low]
            highs = [s for s in all_swings if s.is_high]
            if not lows or not highs:
                return None

            recent_low = lows[-1]
            # Find the swing high that formed after this low
            valid_highs = [h for h in highs if h.index > recent_low.index]
            if not valid_highs:
                return None

            recent_high = valid_highs[-1]
            move_size = recent_high.price - recent_low.price

            if move_size >= min_move:
                return ImpulseLeg(
                    symbol=symbol,
                    side=PositionSide.LONG,
                    start_swing=recent_low,
                    end_swing=recent_high,
                    high=recent_high.price,
                    low=recent_low.price,
                    size=move_size,
                    atr14=atr14,
                    timestamp=recent_high.timestamp,
                )

        elif bias_4h == TrendType.BEARISH:
            # Look for recent Swing High -> lower Swing Low
            highs = [s for s in all_swings if s.is_high]
            lows = [s for s in all_swings if s.is_low]
            if not highs or not lows:
                return None

            recent_high = highs[-1]
            valid_lows = [l for l in lows if l.index > recent_high.index]
            if not valid_lows:
                return None

            recent_low = valid_lows[-1]
            move_size = recent_high.price - recent_low.price

            if move_size >= min_move:
                return ImpulseLeg(
                    symbol=symbol,
                    side=PositionSide.SHORT,
                    start_swing=recent_high,
                    end_swing=recent_low,
                    high=recent_high.price,
                    low=recent_low.price,
                    size=move_size,
                    atr14=atr14,
                    timestamp=recent_low.timestamp,
                )

        return None
