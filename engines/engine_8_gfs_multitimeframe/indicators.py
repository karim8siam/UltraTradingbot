"""
Mathematical Indicators and Price Action Engine for GFS Strategy
Pure deterministic calculations on strictly closed candles (Zero lookahead bias).
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Candle:
    timestamp: int       # Open timestamp ms
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int      # Close timestamp ms
    is_closed: bool = True

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return max(self.high - self.low, 1e-9)

    @property
    def body_percentage(self) -> float:
        return self.body / self.range

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


@dataclass
class SwingPoint:
    index: int
    timestamp: int
    price: float
    is_high: bool        # True for Swing High, False for Swing Low
    confirmed_at_index: int  # index where swing was confirmed (i + SWING_LENGTH)


def calculate_ema(closes: List[float], period: int) -> List[float]:
    """
    Calculates Exponential Moving Average across a series of closes.
    Initializes with SMA of first 'period' values.
    """
    if len(closes) < period:
        return [0.0] * len(closes)

    multiplier = 2.0 / (period + 1)
    ema_values = [0.0] * len(closes)

    # Initial SMA
    sma = sum(closes[:period]) / period
    ema_values[period - 1] = sma

    for i in range(period, len(closes)):
        ema_values[i] = (closes[i] * multiplier) + (ema_values[i - 1] * (1.0 - multiplier))

    return ema_values


def calculate_ema_slope(ema_values: List[float], index: int = -1) -> Tuple[float, str]:
    """
    Calculates slope of EMA between the specified candle and the previous closed candle.
    Returns (slope_delta, 'BULLISH' | 'BEARISH' | 'FLAT')
    """
    if len(ema_values) < 2:
        return 0.0, 'FLAT'

    idx = index if index >= 0 else len(ema_values) + index
    if idx <= 0 or idx >= len(ema_values):
        return 0.0, 'FLAT'

    current = ema_values[idx]
    prev = ema_values[idx - 1]

    if current == 0.0 or prev == 0.0:
        return 0.0, 'FLAT'

    diff = current - prev
    if diff > 0:
        return diff, 'BULLISH'
    elif diff < 0:
        return diff, 'BEARISH'
    return 0.0, 'FLAT'


def calculate_atr(candles: List[Candle], period: int = 14) -> List[float]:
    """
    Calculates Average True Range using Wilder's smoothing.
    """
    n = len(candles)
    if n == 0:
        return []
    if n < period:
        return [c.range for c in candles]

    tr_list = []
    for i in range(n):
        if i == 0:
            tr = candles[i].high - candles[i].low
        else:
            prev_close = candles[i - 1].close
            tr = max(
                candles[i].high - candles[i].low,
                abs(candles[i].high - prev_close),
                abs(candles[i].low - prev_close)
            )
        tr_list.append(tr)

    atr_list = [0.0] * n
    # Initial SMA for first period
    first_atr = sum(tr_list[:period]) / period
    atr_list[period - 1] = first_atr

    for i in range(period, n):
        atr_list[i] = (atr_list[i - 1] * (period - 1) + tr_list[i]) / period

    return atr_list


def calculate_atr_ratio(atr_series: List[float], current_idx: int = -1, lookback: int = 50) -> float:
    """
    Calculates current ATR / Average ATR over lookback period.
    """
    idx = current_idx if current_idx >= 0 else len(atr_series) + current_idx
    if idx < 0 or idx >= len(atr_series):
        return 1.0

    current_atr = atr_series[idx]
    if current_atr <= 0:
        return 1.0

    start_idx = max(0, idx - lookback + 1)
    slice_atr = [a for a in atr_series[start_idx:idx + 1] if a > 0]
    if not slice_atr:
        return 1.0

    avg_atr = sum(slice_atr) / len(slice_atr)
    return current_atr / avg_atr if avg_atr > 0 else 1.0


def find_swings(candles: List[Candle], swing_length: int = 2, max_index: Optional[int] = None) -> List[SwingPoint]:
    """
    Finds Swing Highs and Swing Lows with zero lookahead bias.
    A swing at candle i requires swing_length candles before (i-2, i-1)
    and swing_length candles after (i+1, i+2) to be strictly lower (for High) or higher (for Low).
    The swing is confirmed only at index i + swing_length.
    """
    swings: List[SwingPoint] = []
    limit = len(candles) if max_index is None else min(len(candles), max_index + 1)

    for i in range(swing_length, limit - swing_length):
        confirmation_idx = i + swing_length
        if confirmation_idx >= limit:
            break

        c_i = candles[i]

        # Check Swing High
        is_swing_high = True
        for offset in range(1, swing_length + 1):
            if not (c_i.high > candles[i - offset].high and c_i.high > candles[i + offset].high):
                is_swing_high = False
                break

        if is_swing_high:
            swings.append(SwingPoint(
                index=i,
                timestamp=c_i.timestamp,
                price=c_i.high,
                is_high=True,
                confirmed_at_index=confirmation_idx
            ))

        # Check Swing Low
        is_swing_low = True
        for offset in range(1, swing_length + 1):
            if not (c_i.low < candles[i - offset].low and c_i.low < candles[i + offset].low):
                is_swing_low = False
                break

        if is_swing_low:
            swings.append(SwingPoint(
                index=i,
                timestamp=c_i.timestamp,
                price=c_i.low,
                is_high=False,
                confirmed_at_index=confirmation_idx
            ))

    swings.sort(key=lambda s: s.index)
    return swings


def check_displacement(
    candles: List[Candle],
    candle_idx: int,
    is_long: bool,
    body_multiplier: float = 1.25,
    min_body_pct: float = 0.55,
    lookback: int = 10
) -> Tuple[bool, Dict[str, float]]:
    """
    Checks if confirmation candle has significant momentum/displacement:
    1. Bullish/Bearish candle alignment
    2. Body >= AverageBody(previous 10 closed candles) * body_multiplier
    3. BodyPercentage >= min_body_pct
    """
    if candle_idx < lookback or candle_idx >= len(candles):
        return False, {'current_body': 0.0, 'avg_body': 0.0, 'body_pct': 0.0}

    target = candles[candle_idx]
    prev_bodies = [candles[j].body for j in range(candle_idx - lookback, candle_idx)]
    avg_body = sum(prev_bodies) / len(prev_bodies) if prev_bodies else 1e-9

    current_body = target.body
    body_pct = target.body_percentage

    stats = {
        'current_body': current_body,
        'avg_body': avg_body,
        'body_pct': body_pct,
        'required_body': avg_body * body_multiplier,
        'is_direction_aligned': target.is_bullish if is_long else target.is_bearish
    }

    if is_long:
        if not target.is_bullish:
            return False, stats
    else:
        if not target.is_bearish:
            return False, stats

    if current_body < (avg_body * body_multiplier):
        return False, stats

    if body_pct < min_body_pct:
        return False, stats

    return True, stats
