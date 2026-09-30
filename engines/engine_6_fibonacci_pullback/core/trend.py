"""
Deterministic Multi-Timeframe Trend Classification (4H & 1H)
Section 6 & 7 Specification
"""

from typing import List, Tuple
from core.types import Candle, TrendType, SwingPoint
from core.swings import SwingDetector


class TrendDetector:
    def __init__(self, swing_detector: SwingDetector = None):
        self.swing_detector = swing_detector or SwingDetector()

    def classify_trend(self, candles: List[Candle], timeframe: str = "") -> Tuple[TrendType, List[SwingPoint], List[SwingPoint]]:
        """
        Classifies trend based on consecutive swing highs and swing lows:
        - Bullish: Recent Swing High > Previous Swing High AND Recent Swing Low > Previous Swing Low
        - Bearish: Recent Swing High < Previous Swing High AND Recent Swing Low < Previous Swing Low
        - Otherwise: Neutral
        """
        highs, lows = self.swing_detector.get_recent_swings(candles, timeframe, max_count=5)

        if len(highs) < 2 or len(lows) < 2:
            return TrendType.NEUTRAL, highs, lows

        recent_high = highs[-1]
        prev_high = highs[-2]
        recent_low = lows[-1]
        prev_low = lows[-2]

        is_higher_high = recent_high.price > prev_high.price
        is_higher_low = recent_low.price > prev_low.price

        is_lower_high = recent_high.price < prev_high.price
        is_lower_low = recent_low.price < prev_low.price

        if is_higher_high and is_higher_low:
            return TrendType.BULLISH, highs, lows
        elif is_lower_high and is_lower_low:
            return TrendType.BEARISH, highs, lows
        else:
            return TrendType.NEUTRAL, highs, lows

    def check_htf_alignment(
        self, candles_4h: List[Candle], candles_1h: List[Candle]
    ) -> Tuple[TrendType, TrendType, bool]:
        """
        Checks if 4H and 1H trends are in full alignment.
        Returns (bias_4h, bias_1h, is_aligned).
        """
        bias_4h, _, _ = self.classify_trend(candles_4h, "4h")
        bias_1h, _, _ = self.classify_trend(candles_1h, "1h")

        is_aligned = (bias_4h == bias_1h) and (bias_4h != TrendType.NEUTRAL)
        return bias_4h, bias_1h, is_aligned
