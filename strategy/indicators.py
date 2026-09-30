"""
Deterministic Indicators Engine.
Provides zero-lookahead calculations for EMA, ATR, ADX, Average Body, and Candle Displacement.
"""

from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import pandas as pd


def calculate_ema_series(prices: np.ndarray, period: int) -> np.ndarray:
    """Calculate Exponential Moving Average series without future leakage."""
    if len(prices) == 0:
        return np.array([])
    if len(prices) < period:
        ema = np.full(len(prices), np.nan)
        return ema

    ema = np.full(len(prices), np.nan)
    # First EMA initialized with SMA of first `period` bars
    ema[period - 1] = np.mean(prices[:period])
    alpha = 2.0 / (period + 1.0)

    for i in range(period, len(prices)):
        ema[i] = (prices[i] * alpha) + (ema[i - 1] * (1.0 - alpha))

    return ema


def calculate_ema(prices: np.ndarray, period: int) -> float:
    """Calculate latest EMA value."""
    series = calculate_ema_series(prices, period)
    return float(series[-1]) if len(series) > 0 and not np.isnan(series[-1]) else 0.0


def calculate_atr_series(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Calculate Average True Range (Wilder's RMA) series."""
    n = len(closes)
    if n == 0:
        return np.array([])
    if n < period + 1:
        return np.full(n, np.nan)

    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)

    atr = np.full(n, np.nan)
    atr[period] = np.mean(tr[1:period + 1])
    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr


def calculate_adx_series(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate ADX, +DI, and -DI series using standard Wilder's smoothing.
    Returns: (ADX, plus_di, minus_di)
    """
    n = len(closes)
    if n < (period * 2):
        return np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)

    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]

        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        else:
            plus_dm[i] = 0

        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move
        else:
            minus_dm[i] = 0

        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)

    # Smoothed TR, +DM, -DM
    smooth_tr = np.zeros(n)
    smooth_plus_dm = np.zeros(n)
    smooth_minus_dm = np.zeros(n)

    smooth_tr[period] = np.sum(tr[1:period + 1])
    smooth_plus_dm[period] = np.sum(plus_dm[1:period + 1])
    smooth_minus_dm[period] = np.sum(minus_dm[1:period + 1])

    for i in range(period + 1, n):
        smooth_tr[i] = smooth_tr[i - 1] - (smooth_tr[i - 1] / period) + tr[i]
        smooth_plus_dm[i] = smooth_plus_dm[i - 1] - (smooth_plus_dm[i - 1] / period) + plus_dm[i]
        smooth_minus_dm[i] = smooth_minus_dm[i - 1] - (smooth_minus_dm[i - 1] / period) + minus_dm[i]

    plus_di = np.full(n, np.nan)
    minus_di = np.full(n, np.nan)
    dx = np.zeros(n)

    for i in range(period, n):
        if smooth_tr[i] > 0:
            plus_di[i] = 100.0 * (smooth_plus_dm[i] / smooth_tr[i])
            minus_di[i] = 100.0 * (smooth_minus_dm[i] / smooth_tr[i])
        else:
            plus_di[i] = 0
            minus_di[i] = 0

        di_sum = plus_di[i] + minus_di[i]
        di_diff = abs(plus_di[i] - minus_di[i])
        dx[i] = 100.0 * (di_diff / di_sum) if di_sum > 0 else 0

    adx = np.full(n, np.nan)
    adx_start = period * 2
    if n > adx_start:
        adx[adx_start] = np.mean(dx[period:adx_start + 1])
        for i in range(adx_start + 1, n):
            adx[i] = ((adx[i - 1] * (period - 1)) + dx[i]) / period

    return adx, plus_di, minus_di


def calculate_average_body(opens: np.ndarray, closes: np.ndarray, period: int = 10) -> float:
    """Calculate average candle body size of the previous `period` closed candles."""
    if len(opens) < period:
        return 0.0
    bodies = np.abs(closes[-period:] - opens[-period:])
    return float(np.mean(bodies))


def calculate_volume_sma(volumes: np.ndarray, period: int = 20) -> float:
    """Calculate SMA of volume over the previous `period` closed candles."""
    if len(volumes) < period:
        return 0.0
    return float(np.mean(volumes[-period:]))


def is_displacement_candle(open_price: float, high: float, low: float, close: float,
                           avg_body: float, is_bullish: bool,
                           multiplier: float = 1.25, min_body_pct: float = 0.55) -> Tuple[bool, Dict[str, Any]]:
    """
    Validates Section 23: 1H Displacement Requirements:
    LONG: Close > Open, Body >= AvgBody10 * 1.25, Body / Range >= 0.55
    SHORT: Close < Open, Body >= AvgBody10 * 1.25, Body / Range >= 0.55
    """
    total_range = high - low
    body = abs(close - open_price)

    if total_range <= 0:
        return False, {"body": body, "range": total_range, "body_pct": 0.0, "reason": "Zero candle range"}

    body_pct = body / total_range
    is_body_large = (avg_body > 0) and (body >= (avg_body * multiplier))
    is_pct_valid = body_pct >= min_body_pct

    direction_valid = (close > open_price) if is_bullish else (close < open_price)
    is_valid = direction_valid and is_body_large and is_pct_valid

    metrics = {
        "body": body,
        "avg_body": avg_body,
        "body_multiple": (body / avg_body) if avg_body > 0 else 0.0,
        "body_pct": body_pct,
        "direction_valid": direction_valid,
        "is_body_large": is_body_large,
        "is_pct_valid": is_pct_valid
    }
    return is_valid, metrics


def check_volatility_filter(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                            max_atr_ratio: float = 2.5) -> Tuple[bool, float, float]:
    """
    Validates Section 41: Volatility filter:
    CurrentATR / AverageATR50 <= max_atr_ratio (2.5)
    Returns: (is_pass, current_atr, atr_ratio)
    """
    atr_series = calculate_atr_series(highs, lows, closes, period=14)
    valid_atr = atr_series[~np.isnan(atr_series)]
    if len(valid_atr) < 50:
        return True, float(valid_atr[-1]) if len(valid_atr) > 0 else 0.0, 1.0

    current_atr = float(valid_atr[-1])
    avg_atr_50 = float(np.mean(valid_atr[-50:]))
    atr_ratio = (current_atr / avg_atr_50) if avg_atr_50 > 0 else 1.0

    is_pass = atr_ratio <= max_atr_ratio
    return is_pass, current_atr, atr_ratio
