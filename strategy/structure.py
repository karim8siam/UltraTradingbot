"""
Market Structure & Trend Engine.
Detects swing pivots without lookahead, computes Daily & 4H trends, and verifies alignment.
"""

from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
import pandas as pd

from .indicators import calculate_ema_series


class TrendDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass
class SwingPoint:
    index: int          # Index where pivot occurred
    confirmed_index: int # Index where pivot became confirmed (index + swing_length)
    timestamp: int      # Timestamp of pivot candle
    price: float        # High or Low price
    is_high: bool       # True for Swing High, False for Swing Low


class SwingDetector:
    def __init__(self, swing_length: int = 2):
        self.swing_length = swing_length

    def find_swings(self, highs: np.ndarray, lows: np.ndarray, timestamps: Optional[np.ndarray] = None,
                    up_to_index: Optional[int] = None) -> List[SwingPoint]:
        """
        Find confirmed swing points up to `up_to_index` with strictly ZERO lookahead.
        A swing at index `i` is ONLY confirmed when bar `i + swing_length` is closed.
        """
        n = len(highs) if up_to_index is None else min(len(highs), up_to_index + 1)
        k = self.swing_length
        swings: List[SwingPoint] = []

        if n < (2 * k + 1):
            return swings

        # The latest bar that can be a confirmed pivot is n - 1 - k
        for i in range(k, n - k):
            # Check Swing High
            is_sh = True
            for offset in range(1, k + 1):
                if highs[i] <= highs[i - offset] or highs[i] <= highs[i + offset]:
                    is_sh = False
                    break

            if is_sh:
                ts = int(timestamps[i]) if timestamps is not None else i
                swings.append(SwingPoint(
                    index=i,
                    confirmed_index=i + k,
                    timestamp=ts,
                    price=float(highs[i]),
                    is_high=True
                ))

            # Check Swing Low
            is_sl = True
            for offset in range(1, k + 1):
                if lows[i] >= lows[i - offset] or lows[i] >= lows[i + offset]:
                    is_sl = False
                    break

            if is_sl:
                ts = int(timestamps[i]) if timestamps is not None else i
                swings.append(SwingPoint(
                    index=i,
                    confirmed_index=i + k,
                    timestamp=ts,
                    price=float(lows[i]),
                    is_high=False
                ))

        return sorted(swings, key=lambda s: s.index)


class MarketStructureEngine:
    def __init__(self, swing_length: int = 2, daily_ema_fast: int = 50, daily_ema_slow: int = 200,
                 four_h_ema_fast: int = 20, four_h_ema_slow: int = 50):
        self.swing_length = swing_length
        self.daily_ema_fast = daily_ema_fast
        self.daily_ema_slow = daily_ema_slow
        self.four_h_ema_fast = four_h_ema_fast
        self.four_h_ema_slow = four_h_ema_slow
        self.swing_detector = SwingDetector(swing_length=swing_length)

    def evaluate_daily_trend(self, daily_closes: np.ndarray) -> Tuple[TrendDirection, Dict[str, Any]]:
        """
        Section 6: Daily Trend
        BULLISH: EMA50 > EMA200 AND Daily Close > EMA50 AND EMA50 slope positive.
        BEARISH: EMA50 < EMA200 AND Daily Close < EMA50 AND EMA50 slope negative.
        Otherwise: NEUTRAL.
        """
        if len(daily_closes) < self.daily_ema_slow + 2:
            return TrendDirection.NEUTRAL, {"reason": "Insufficient daily data"}

        ema50 = calculate_ema_series(daily_closes, self.daily_ema_fast)
        ema200 = calculate_ema_series(daily_closes, self.daily_ema_slow)

        curr_close = daily_closes[-1]
        curr_ema50 = ema50[-1]
        prev_ema50 = ema50[-2]
        curr_ema200 = ema200[-1]

        ema50_slope = curr_ema50 - prev_ema50

        info = {
            "daily_close": float(curr_close),
            "daily_ema50": float(curr_ema50),
            "daily_ema200": float(curr_ema200),
            "ema50_slope": float(ema50_slope)
        }

        if (curr_ema50 > curr_ema200) and (curr_close > curr_ema50) and (ema50_slope > 0):
            return TrendDirection.BULLISH, info
        elif (curr_ema50 < curr_ema200) and (curr_close < curr_ema50) and (ema50_slope < 0):
            return TrendDirection.BEARISH, info
        else:
            return TrendDirection.NEUTRAL, info

    def evaluate_daily_structure(self, daily_highs: np.ndarray, daily_lows: np.ndarray,
                                 daily_timestamps: Optional[np.ndarray] = None) -> Tuple[TrendDirection, Dict[str, Any]]:
        """
        Sections 7, 8, 9: Daily Market Structure using confirmed swing highs and lows.
        Bullish: Latest swing high > prev swing high AND Latest swing low > prev swing low.
        Bearish: Latest swing high < prev swing high AND Latest swing low < prev swing low.
        """
        swings = self.swing_detector.find_swings(daily_highs, daily_lows, daily_timestamps)
        swing_highs = [s for s in swings if s.is_high]
        swing_lows = [s for s in swings if not s.is_high]

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return TrendDirection.NEUTRAL, {
                "reason": "Need at least 2 confirmed swing highs and 2 confirmed swing lows",
                "swing_highs_count": len(swing_highs),
                "swing_lows_count": len(swing_lows)
            }

        latest_sh, prev_sh = swing_highs[-1], swing_highs[-2]
        latest_sl, prev_sl = swing_lows[-1], swing_lows[-2]

        info = {
            "latest_sh": latest_sh.price,
            "prev_sh": prev_sh.price,
            "latest_sl": latest_sl.price,
            "prev_sl": prev_sl.price,
            "higher_high": latest_sh.price > prev_sh.price,
            "higher_low": latest_sl.price > prev_sl.price,
            "lower_high": latest_sh.price < prev_sh.price,
            "lower_low": latest_sl.price < prev_sl.price
        }

        if (latest_sh.price > prev_sh.price) and (latest_sl.price > prev_sl.price):
            return TrendDirection.BULLISH, info
        elif (latest_sh.price < prev_sh.price) and (latest_sl.price < prev_sl.price):
            return TrendDirection.BEARISH, info
        else:
            return TrendDirection.NEUTRAL, info

    def evaluate_4h_trend(self, four_h_closes: np.ndarray) -> Tuple[TrendDirection, Dict[str, Any]]:
        """
        Section 12: 4H Trend
        Bullish: EMA20 > EMA50 AND 4H Close > EMA20 AND EMA20 slope positive.
        Bearish: EMA20 < EMA50 AND 4H Close < EMA20 AND EMA20 slope negative.
        """
        if len(four_h_closes) < self.four_h_ema_slow + 2:
            return TrendDirection.NEUTRAL, {"reason": "Insufficient 4H data"}

        ema20 = calculate_ema_series(four_h_closes, self.four_h_ema_fast)
        ema50 = calculate_ema_series(four_h_closes, self.four_h_ema_slow)

        curr_close = four_h_closes[-1]
        curr_ema20 = ema20[-1]
        prev_ema20 = ema20[-2]
        curr_ema50 = ema50[-1]

        ema20_slope = curr_ema20 - prev_ema20

        info = {
            "4h_close": float(curr_close),
            "4h_ema20": float(curr_ema20),
            "4h_ema50": float(curr_ema50),
            "ema20_slope": float(ema20_slope)
        }

        if (curr_ema20 > curr_ema50) and (curr_close > curr_ema20) and (ema20_slope > 0):
            return TrendDirection.BULLISH, info
        elif (curr_ema20 < curr_ema50) and (curr_close < curr_ema20) and (ema20_slope < 0):
            return TrendDirection.BEARISH, info
        else:
            return TrendDirection.NEUTRAL, info

    def check_trend_alignment(self, daily_trend: TrendDirection, daily_structure: TrendDirection,
                              four_h_trend: TrendDirection) -> Optional[str]:
        """
        Sections 10, 11, 13:
        LONG requires: Daily Trend Bullish + Daily Structure Bullish + 4H Trend Bullish.
        SHORT requires: Daily Trend Bearish + Daily Structure Bearish + 4H Trend Bearish.
        Returns: "LONG", "SHORT", or None
        """
        if daily_trend == TrendDirection.BULLISH and daily_structure == TrendDirection.BULLISH and four_h_trend == TrendDirection.BULLISH:
            return "LONG"
        elif daily_trend == TrendDirection.BEARISH and daily_structure == TrendDirection.BEARISH and four_h_trend == TrendDirection.BEARISH:
            return "SHORT"
        return None
