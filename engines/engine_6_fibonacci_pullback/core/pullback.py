"""
Pullback Detection & Invalidation Logic
Sections 14, 15, 39, 40 Specification
"""

from typing import List, Optional, Tuple
from core.types import Candle, FibLevels, FibZoneCategory, PositionSide


class PullbackDetector:
    def __init__(self):
        pass

    def evaluate_pullback(
        self,
        candles_5m: List[Candle],
        fib_levels: FibLevels,
        start_candle_index: int,
    ) -> Tuple[bool, bool, bool, float, float, Optional[FibZoneCategory]]:
        """
        Evaluates the pullback since impulse completion (start_candle_index):
        Returns:
            - is_in_valid_zone (bool): reached at least 38.2% and not invalidated
            - is_preferred_zone (bool): reached 50.0%-61.8%
            - is_invalidated (bool): closed beyond 78.6% retracement
            - pullback_low (float): lowest low recorded during pullback
            - pullback_high (float): highest high recorded during pullback
            - zone_category (FibZoneCategory)
        """
        if not candles_5m or start_candle_index >= len(candles_5m):
            return False, False, False, 0.0, 0.0, None

        subset = candles_5m[start_candle_index:]
        if not subset:
            return False, False, False, 0.0, 0.0, None

        pullback_low = min(c.low for c in subset)
        pullback_high = max(c.high for c in subset)

        if fib_levels.is_bullish:
            # Bullish pullback moves down from impulse high
            # Invalidation: Close < 78.6% Fib
            for c in subset:
                if c.close < fib_levels.fib_786:
                    return False, False, True, pullback_low, pullback_high, None

            # Reached at least 38.2% Fib (pullback_low <= fib_382)
            reached_primary = pullback_low <= fib_levels.fib_382
            # Reached preferred zone (pullback_low <= fib_500)
            reached_preferred = pullback_low <= fib_levels.fib_500 and pullback_low >= fib_levels.fib_618

            current_price = subset[-1].close
            zone_category = fib_levels.get_zone_category(pullback_low)

            return reached_primary, reached_preferred, False, pullback_low, pullback_high, zone_category

        else:
            # Bearish pullback moves up from impulse low
            # Invalidation: Close > 78.6% Fib
            for c in subset:
                if c.close > fib_levels.fib_786:
                    return False, False, True, pullback_low, pullback_high, None

            # Reached at least 38.2% Fib (pullback_high >= fib_382)
            reached_primary = pullback_high >= fib_levels.fib_382
            # Reached preferred zone (pullback_high >= fib_500)
            reached_preferred = pullback_high >= fib_levels.fib_500 and pullback_high <= fib_levels.fib_618

            current_price = subset[-1].close
            zone_category = fib_levels.get_zone_category(pullback_high)

            return reached_primary, reached_preferred, False, pullback_low, pullback_high, zone_category
