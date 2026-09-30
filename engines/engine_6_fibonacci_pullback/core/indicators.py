"""
Technical Indicators & Mathematical Calculations
Pure Python implementations for deterministic execution.
"""

from typing import List
from core.types import Candle


def calculate_true_range(current: Candle, previous: Candle) -> float:
    """Calculates True Range (TR) between current and previous candle."""
    hl = current.high - current.low
    hc = abs(current.high - previous.close)
    lc = abs(current.low - previous.close)
    return max(hl, hc, lc)


def calculate_atr(candles: List[Candle], period: int = 14) -> List[float]:
    """
    Calculates Average True Range (ATR) using Wilder's smoothing method.
    Returns list of ATR values corresponding to each candle (0.0 for candles before period).
    """
    n = len(candles)
    if n < period + 1:
        return [0.0] * n

    atr_values = [0.0] * n
    tr_values = [0.0] * n

    tr_values[0] = candles[0].high - candles[0].low
    for i in range(1, n):
        tr_values[i] = calculate_true_range(candles[i], candles[i - 1])

    # Initial simple average of first TRs
    initial_atr = sum(tr_values[1 : period + 1]) / period
    atr_values[period] = initial_atr

    # Wilder's smoothing
    for i in range(period + 1, n):
        atr_values[i] = (atr_values[i - 1] * (period - 1) + tr_values[i]) / period

    return atr_values


def get_latest_atr(candles: List[Candle], period: int = 14) -> float:
    """Returns the latest confirmed ATR value from closed candles."""
    atr_list = calculate_atr(candles, period)
    return atr_list[-1] if atr_list else 0.0


def calculate_average_body(candles: List[Candle], period: int = 10, end_index: int = -1) -> float:
    """
    Calculates Average Body: mean(abs(Close - Open)) of previous completed candles.
    end_index defaults to -1 (most recent candle index before the current one).
    """
    if end_index < 0:
        end_idx = len(candles) + end_index
    else:
        end_idx = end_index

    start_idx = max(0, end_idx - period)
    subset = candles[start_idx:end_idx]
    if not subset:
        return 0.0

    total_body = sum(c.body_size for c in subset)
    return total_body / len(subset)


def calculate_atr_ratio(candles: List[Candle], atr_period: int = 14, avg_period: int = 50) -> float:
    """
    Volatility filter calculation: CurrentATR / AverageATR(50)
    """
    atr_series = calculate_atr(candles, atr_period)
    if len(atr_series) < avg_period + atr_period:
        return 1.0

    current_atr = atr_series[-1]
    if current_atr <= 0.0:
        return 1.0

    recent_atrs = [v for v in atr_series[-avg_period:] if v > 0.0]
    if not recent_atrs:
        return 1.0

    avg_atr = sum(recent_atrs) / len(recent_atrs)
    if avg_atr <= 0.0:
        return 1.0

    return current_atr / avg_atr
