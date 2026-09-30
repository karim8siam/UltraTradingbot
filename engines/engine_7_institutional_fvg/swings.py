"""
Deterministic Swing Detector
Implements Section 10 rules with SWING_LENGTH=2 and zero look-ahead bias.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from indicators import Candle


@dataclass
class SwingPoint:
    index: int
    timestamp: int
    price: float
    is_high: bool  # True if Swing High, False if Swing Low
    timeframe: str = ""


def find_swings(candles: List[Candle], swing_length: int = 2, timeframe: str = "") -> List[SwingPoint]:
    """
    Identifies confirmed swing highs and swing lows.
    A swing at index `i` is confirmed once candle `i + swing_length` is closed.
    Ensures zero look-ahead bias.
    """
    n = len(candles)
    swings: List[SwingPoint] = []
    
    # Needs at least (2 * swing_length + 1) candles
    if n < (2 * swing_length + 1):
        return swings

    # The maximum index that can be confirmed is n - 1 - swing_length
    max_eval_idx = n - 1 - swing_length

    for i in range(swing_length, max_eval_idx + 1):
        c_curr = candles[i]
        
        # Check Swing High
        is_swing_high = True
        for offset in range(1, swing_length + 1):
            if not (c_curr.high > candles[i - offset].high and c_curr.high > candles[i + offset].high):
                is_swing_high = False
                break
        
        if is_swing_high:
            swings.append(SwingPoint(
                index=i,
                timestamp=c_curr.timestamp,
                price=c_curr.high,
                is_high=True,
                timeframe=timeframe
            ))

        # Check Swing Low
        is_swing_low = True
        for offset in range(1, swing_length + 1):
            if not (c_curr.low < candles[i - offset].low and c_curr.low < candles[i + offset].low):
                is_swing_low = False
                break

        if is_swing_low:
            swings.append(SwingPoint(
                index=i,
                timestamp=c_curr.timestamp,
                price=c_curr.low,
                is_high=False,
                timeframe=timeframe
            ))

    return swings


def get_latest_swings(candles: List[Candle], swing_length: int = 2, timeframe: str = "") -> Tuple[Optional[SwingPoint], Optional[SwingPoint], Optional[SwingPoint], Optional[SwingPoint]]:
    """
    Returns:
    (latest_swing_high, prev_swing_high, latest_swing_low, prev_swing_low)
    """
    swings = find_swings(candles, swing_length=swing_length, timeframe=timeframe)
    highs = [s for s in swings if s.is_high]
    lows = [s for s in swings if not s.is_high]

    latest_high = highs[-1] if len(highs) >= 1 else None
    prev_high = highs[-2] if len(highs) >= 2 else None

    latest_low = lows[-1] if len(lows) >= 1 else None
    prev_low = lows[-2] if len(lows) >= 2 else None

    return latest_high, prev_high, latest_low, prev_low
