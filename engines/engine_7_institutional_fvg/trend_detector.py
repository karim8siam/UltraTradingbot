"""
Multi-Timeframe Trend Detector
Implements Section 9, 11, 12 Market Structure Bias for 4H and 1H candles
with deterministic structural trend persistence (Dow Theory / SMC).
"""

from enum import Enum
from typing import List, Optional, Tuple
from indicators import Candle
from swings import find_swings, SwingPoint


class TrendBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


def detect_market_structure_bias(
    candles: List[Candle],
    swing_length: int = 2,
    timeframe: str = ""
) -> Tuple[TrendBias, Optional[SwingPoint], Optional[SwingPoint], Optional[SwingPoint], Optional[SwingPoint]]:
    """
    Evaluates market structure from confirmed swings:
    - Bullish: Sequences of Higher Highs and Higher Lows (persists until broken)
    - Bearish: Sequences of Lower Highs and Lower Lows (persists until broken)
    - Neutral otherwise
    """
    swings = find_swings(candles, swing_length=swing_length, timeframe=timeframe)
    highs = [s for s in swings if s.is_high]
    lows = [s for s in swings if not s.is_high]

    if len(highs) < 2 or len(lows) < 2:
        # Fallback to general slope if early in history
        if len(candles) >= 10:
            if candles[-1].close > candles[0].close:
                return TrendBias.BULLISH, None, None, None, None
            else:
                return TrendBias.BEARISH, None, None, None, None
        return TrendBias.NEUTRAL, None, None, None, None

    latest_high = highs[-1]
    prev_high = highs[-2]
    latest_low = lows[-1]
    prev_low = lows[-2]

    # Deterministic Structural Direction
    if latest_high.price > prev_high.price and latest_low.price >= prev_low.price:
        return TrendBias.BULLISH, latest_high, prev_high, latest_low, prev_low
    elif latest_high.price <= prev_high.price and latest_low.price < prev_low.price:
        return TrendBias.BEARISH, latest_high, prev_high, latest_low, prev_low
    elif latest_high.price > prev_high.price and candles[-1].close > prev_high.price:
        return TrendBias.BULLISH, latest_high, prev_high, latest_low, prev_low
    elif latest_low.price < prev_low.price and candles[-1].close < prev_low.price:
        return TrendBias.BEARISH, latest_high, prev_high, latest_low, prev_low
    else:
        # Check last established trend
        if latest_high.price > prev_high.price:
            return TrendBias.BULLISH, latest_high, prev_high, latest_low, prev_low
        elif latest_low.price < prev_low.price:
            return TrendBias.BEARISH, latest_high, prev_high, latest_low, prev_low
        return TrendBias.NEUTRAL, latest_high, prev_high, latest_low, prev_low


def evaluate_htf_alignment(
    candles_4h: List[Candle],
    candles_1h: List[Candle],
    swing_length: int = 2
) -> Tuple[Optional[str], TrendBias, TrendBias]:
    """
    Returns:
    (aligned_direction, bias_4h, bias_1h)
    aligned_direction is 'LONG', 'SHORT', or None.
    """
    bias_4h, _, _, _, _ = detect_market_structure_bias(candles_4h, swing_length, "4h")
    bias_1h, _, _, _, _ = detect_market_structure_bias(candles_1h, swing_length, "1h")

    if bias_4h == TrendBias.BULLISH and bias_1h == TrendBias.BULLISH:
        return "LONG", bias_4h, bias_1h
    elif bias_4h == TrendBias.BEARISH and bias_1h == TrendBias.BEARISH:
        return "SHORT", bias_4h, bias_1h
    else:
        return None, bias_4h, bias_1h
