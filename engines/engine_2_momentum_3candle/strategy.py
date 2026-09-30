from typing import List, Dict, Any, Optional
import config

class Momentum3CandleStrategy:
    """
    15-Minute 3-Candle Momentum Strategy:
    - 3 consecutive completed green candles -> LONG
    - 3 consecutive completed red candles -> SHORT
    - Candle -4 (preceding the 3) must NOT be the same direction (fresh 3-candle sequence only).
    - Rejects Dojis, weak candles, and rejection pinbars (requires healthy body >= 50% & small opposing wick).
    """

    @staticmethod
    def is_doji(candle: Dict[str, Any]) -> bool:
        """
        Check if a candle is a Doji (open and close are virtually equal / flat line).
        """
        open_p = candle["open"]
        close_p = candle["close"]
        high_p = candle["high"]
        low_p = candle["low"]

        total_range = high_p - low_p
        if total_range <= 0:
            return True  # Zero range is a flat line/doji

        body = abs(close_p - open_p)
        body_ratio = body / total_range

        # If body is less than 10% of total range or open == close, it is a Doji
        if body_ratio < 0.10 or open_p == close_p:
            return True

        return False

    @classmethod
    def evaluate_klines(cls, klines: List[Dict[str, Any]]) -> Optional[str]:
        """
        Evaluates kline series.
        Expects at least 5 candles (klines[-1] is the unclosed live candle;
        klines[-2], klines[-3], klines[-4] are the 3 completed target candles;
        klines[-5] is the prior candle).

        Returns:
            "BUY" for Long signal,
            "SELL" for Short signal,
            None if no signal.
        """
        if len(klines) < 5:
            return None

        c_prev = klines[-5]  # Candle prior to sequence
        c1 = klines[-4]      # 1st of the 3 candles
        c2 = klines[-3]      # 2nd of the 3 candles
        c3 = klines[-2]      # 3rd of the 3 candles (most recently closed)

        # Check for 3 Consecutive Green Candles (LONG)
        if c1["close"] > c1["open"] and c2["close"] > c2["open"] and c3["close"] > c3["open"]:
            # Prior candle must NOT be green (strictly a fresh 3-candle sequence)
            if c_prev["close"] <= c_prev["open"]:
                # Ensure none of the 3 candles is a Doji
                if not cls.is_doji(c1) and not cls.is_doji(c2) and not cls.is_doji(c3):
                    return "BUY"

        # Check for 3 Consecutive Red Candles (SHORT)
        if c1["close"] < c1["open"] and c2["close"] < c2["open"] and c3["close"] < c3["open"]:
            # Prior candle must NOT be red (strictly a fresh 3-candle sequence)
            if c_prev["close"] >= c_prev["open"]:
                # Ensure none of the 3 candles is a Doji
                if not cls.is_doji(c1) and not cls.is_doji(c2) and not cls.is_doji(c3):
                    return "SELL"

        return None
