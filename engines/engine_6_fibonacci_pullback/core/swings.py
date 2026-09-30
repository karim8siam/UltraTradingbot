"""
Deterministic Swing High & Swing Low Detection (SWING_LENGTH=2)
Section 5 Specification
"""

from typing import List, Optional, Tuple
from core.types import Candle, SwingPoint
from config.constants import SWING_LENGTH


class SwingDetector:
    def __init__(self, swing_length: int = SWING_LENGTH):
        self.swing_length = swing_length

    def find_all_swings(self, candles: List[Candle], timeframe: str = "") -> List[SwingPoint]:
        """
        Scans all confirmed closed candles for Swing Highs and Swing Lows.
        A candle at index i is confirmed when there are at least swing_length candles after it.
        """
        swings: List[SwingPoint] = []
        n = len(candles)
        k = self.swing_length

        if n < (2 * k + 1):
            return swings

        for i in range(k, n - k):
            c = candles[i]

            # Swing High Check
            is_high = True
            for offset in range(1, k + 1):
                if not (c.high > candles[i - offset].high and c.high > candles[i + offset].high):
                    is_high = False
                    break

            # Swing Low Check
            is_low = True
            for offset in range(1, k + 1):
                if not (c.low < candles[i - offset].low and c.low < candles[i + offset].low):
                    is_low = False
                    break

            if is_high or is_low:
                swings.append(
                    SwingPoint(
                        index=i,
                        timestamp=c.timestamp,
                        price=c.high if is_high else c.low,
                        is_high=is_high,
                        is_low=is_low,
                        timeframe=timeframe,
                    )
                )

        return swings

    def get_recent_swings(
        self, candles: List[Candle], timeframe: str = "", max_count: int = 10
    ) -> Tuple[List[SwingPoint], List[SwingPoint]]:
        """
        Returns the most recent confirmed swing highs and swing lows.
        """
        all_swings = self.find_all_swings(candles, timeframe)
        highs = [s for s in all_swings if s.is_high][-max_count:]
        lows = [s for s in all_swings if s.is_low][-max_count:]
        return highs, lows
