from typing import List, Tuple, Optional
from strategy.models import Candle, BiasType, SwingType, SwingPoint
from strategy.swing_detector import SwingDetector

class MarketStructure:
    def __init__(self, swing_length: int = 2):
        self.swing_detector = SwingDetector(swing_length=swing_length)

    def determine_bias(self, candles: List[Candle]) -> Tuple[BiasType, Optional[SwingPoint], Optional[SwingPoint]]:
        """
        Classify market structure as BULLISH, BEARISH, or NEUTRAL.
        Requires at least two confirmed swing highs and two confirmed swing lows.
        """
        swings = self.swing_detector.find_swings(candles)
        swing_highs = [s for s in swings if s.swing_type == SwingType.HIGH]
        swing_lows = [s for s in swings if s.swing_type == SwingType.LOW]

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return BiasType.NEUTRAL, (swing_highs[-1] if swing_highs else None), (swing_lows[-1] if swing_lows else None)

        latest_high = swing_highs[-1]
        prev_high = swing_highs[-2]
        latest_low = swing_lows[-1]
        prev_low = swing_lows[-2]

        is_bullish = (latest_high.price > prev_high.price) and (latest_low.price > prev_low.price)
        is_bearish = (latest_high.price < prev_high.price) and (latest_low.price < prev_low.price)

        if is_bullish:
            return BiasType.BULLISH, latest_high, latest_low
        elif is_bearish:
            return BiasType.BEARISH, latest_high, latest_low
        else:
            return BiasType.NEUTRAL, latest_high, latest_low

    def get_premium_discount_range(self, candles: List[Candle]) -> Optional[Tuple[float, float, float]]:
        """
        Returns (swing_low_price, swing_high_price, midpoint_50) from most recent confirmed 1H swing range.
        """
        swings = self.swing_detector.find_swings(candles)
        swing_highs = [s for s in swings if s.swing_type == SwingType.HIGH]
        swing_lows = [s for s in swings if s.swing_type == SwingType.LOW]

        if not swing_highs or not swing_lows:
            return None

        latest_high = swing_highs[-1].price
        latest_low = swing_lows[-1].price
        midpoint = (latest_high + latest_low) / 2.0
        return latest_low, latest_high, midpoint
