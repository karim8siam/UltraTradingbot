from typing import List, Optional
from strategy.models import Candle, SwingPoint, SwingType

class SwingDetector:
    def __init__(self, swing_length: int = 2):
        self.swing_length = swing_length

    def find_swings(self, candles: List[Candle]) -> List[SwingPoint]:
        """
        Deterministic swing detection without future lookahead.
        A swing at index i requires swing_length closed candles before and after it.
        Therefore, for candles up to len(candles)-1, index i can only be confirmed if i <= len(candles) - 1 - swing_length.
        """
        swings: List[SwingPoint] = []
        n = len(candles)
        if n < (self.swing_length * 2 + 1):
            return swings

        # Only process up to n - 1 - swing_length to ensure closed future confirmation
        max_eval_idx = n - 1 - self.swing_length

        for i in range(self.swing_length, max_eval_idx + 1):
            current_c = candles[i]
            
            # Check Swing High
            is_high = True
            for offset in range(1, self.swing_length + 1):
                if current_c.high <= candles[i - offset].high or current_c.high <= candles[i + offset].high:
                    is_high = False
                    break
            
            if is_high:
                swings.append(SwingPoint(
                    index=i,
                    timestamp=current_c.timestamp,
                    price=current_c.high,
                    swing_type=SwingType.HIGH,
                    confirmed=True
                ))
                continue  # Bar cannot be both swing high and swing low simultaneously

            # Check Swing Low
            is_low = True
            for offset in range(1, self.swing_length + 1):
                if current_c.low >= candles[i - offset].low or current_c.low >= candles[i + offset].low:
                    is_low = False
                    break

            if is_low:
                swings.append(SwingPoint(
                    index=i,
                    timestamp=current_c.timestamp,
                    price=current_c.low,
                    swing_type=SwingType.LOW,
                    confirmed=True
                ))

        return swings

    def get_latest_swings(self, candles: List[Candle]) -> (Optional[SwingPoint], Optional[SwingPoint]):
        """
        Returns (latest_swing_high, latest_swing_low)
        """
        swings = self.find_swings(candles)
        latest_high = None
        latest_low = None
        for s in reversed(swings):
            if s.swing_type == SwingType.HIGH and latest_high is None:
                latest_high = s
            elif s.swing_type == SwingType.LOW and latest_low is None:
                latest_low = s
            if latest_high and latest_low:
                break
        return latest_high, latest_low
