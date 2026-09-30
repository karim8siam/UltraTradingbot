"""
Indicators and Mathematical Formulations
Implements ATR14 (Wilder's), 10-bar Body Size, Body Percentage, and Volatility Ratio.
Pure Python - Zero external dependencies.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Candle:
    timestamp: int  # Open timestamp (ms)
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int = 0  # Close timestamp (ms)

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body_percentage(self) -> float:
        r = self.range
        if r <= 0:
            return 0.0
        return self.body / r

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


def calculate_true_range(current: Candle, prev: Optional[Candle] = None) -> float:
    """True Range: max(high - low, abs(high - prev_close), abs(low - prev_close))."""
    if prev is None:
        return current.high - current.low
    return max(
        current.high - current.low,
        abs(current.high - prev.close),
        abs(current.low - prev.close)
    )


def calculate_atr_series(candles: List[Candle], period: int = 14) -> List[float]:
    """
    Computes Wilder's smoothed ATR series for a list of candles.
    Returns list of float of same length as candles (0.0 for warmup).
    """
    n = len(candles)
    if n == 0:
        return []
    
    tr_list = []
    for i in range(n):
        prev = candles[i - 1] if i > 0 else None
        tr_list.append(calculate_true_range(candles[i], prev))

    atr_series = [0.0] * n
    if n < period:
        # Fallback simple average if not enough candles
        avg = sum(tr_list) / max(1, n)
        return [avg] * n

    # Initial ATR is simple average of first `period` true ranges
    initial_atr = sum(tr_list[:period]) / period
    atr_series[period - 1] = initial_atr

    # Wilder's Smoothing: ATR = (prev_ATR * (period - 1) + current_TR) / period
    prev_atr = initial_atr
    for i in range(period, n):
        current_atr = (prev_atr * (period - 1) + tr_list[i]) / period
        atr_series[i] = current_atr
        prev_atr = current_atr

    # Backfill warmup bars with first valid ATR for convenience
    for i in range(period - 1):
        atr_series[i] = initial_atr

    return atr_series


def calculate_atr(candles: List[Candle], period: int = 14) -> float:
    """Returns the latest ATR(period) value."""
    series = calculate_atr_series(candles, period)
    return series[-1] if series else 0.0


def calculate_average_body(candles: List[Candle], lookback: int = 10, offset: int = 0) -> float:
    """
    Calculates mean(abs(Close - Open)) of previous completed candles.
    offset: 0 means up to the last candle in list, 1 means excluding the last candle.
    """
    end_idx = len(candles) - offset
    if end_idx <= 0:
        return 0.0
    start_idx = max(0, end_idx - lookback)
    subset = candles[start_idx:end_idx]
    if not subset:
        return 0.0
    return sum(c.body for c in subset) / len(subset)


def calculate_volatility_ratio(candles: List[Candle], period_fast: int = 14, period_slow: int = 50) -> float:
    """
    Computes CurrentATR14 / AverageATR50 (Section 42).
    """
    if len(candles) < period_slow:
        return 1.0
    atr_fast = calculate_atr(candles, period_fast)
    # Average of past 50 True Ranges or ATR50
    atr_slow = calculate_atr(candles, period_slow)
    if atr_slow <= 0:
        return 1.0
    return atr_fast / atr_slow
