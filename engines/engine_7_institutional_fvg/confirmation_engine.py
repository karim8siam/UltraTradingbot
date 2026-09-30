"""
5M Lower-Timeframe Confirmation Engine
Implements Sections 21, 22, 23:
- Pullback swing detection inside FVG
- Structure Shift (Close beyond level - no intrawick)
- 5M Displacement validation on shift candle
- Pullback Structural Low / High extraction for Stop Loss
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from indicators import Candle, calculate_average_body
from fvg_engine import FVG, check_displacement
from swings import find_swings, SwingPoint


@dataclass
class ConfirmationSignal:
    is_confirmed: bool
    side: str  # "LONG" or "SHORT"
    fvg: FVG
    shift_candle: Candle
    shift_index_5m: int
    pullback_high: float
    pullback_low: float
    confirmation_level: float
    displacement_body: float
    body_percentage: float
    retrace_entered_50: bool


def check_5m_confirmation(
    fvg: FVG,
    candles_5m: List[Candle],
    swing_length: int = 2,
    body_multiplier: float = 1.5,
    min_body_pct: float = 0.60,
    lookback_body: int = 10
) -> Optional[ConfirmationSignal]:
    """
    Evaluates whether 5M candles since FVG creation have retraced into the FVG
    and produced a valid structure shift with displacement.
    """
    if len(candles_5m) < 15:
        return None

    # Filter candles that occurred AFTER or at the FVG creation timestamp
    subsequent_candles = [c for c in candles_5m if c.timestamp >= fvg.created_timestamp]
    if len(subsequent_candles) < 3:
        return None

    # Check FVG age on 5M (Section 44)
    if len(subsequent_candles) > 50:
        return None

    # Step 1: Check retracement into FVG boundaries
    has_entered_fvg = False
    has_reached_50_mid = False
    retrace_start_idx = -1

    for idx, c in enumerate(subsequent_candles):
        if fvg.is_bullish:
            # Bullish retracement: Low enters zone (<= FVG_HIGH)
            if c.low <= fvg.fvg_high:
                has_entered_fvg = True
                if retrace_start_idx == -1:
                    retrace_start_idx = idx
                if c.low <= fvg.fvg_mid:
                    has_reached_50_mid = True
            # Invalidation: Close below FVG_LOW (Section 19)
            if c.close < fvg.fvg_low:
                return None
        else:
            # Bearish retracement: High enters zone (>= FVG_LOW)
            if c.high >= fvg.fvg_low:
                has_entered_fvg = True
                if retrace_start_idx == -1:
                    retrace_start_idx = idx
                if c.high >= fvg.fvg_mid:
                    has_reached_50_mid = True
            # Invalidation: Close above FVG_HIGH (Section 19)
            if c.close > fvg.fvg_high:
                return None

    if not has_entered_fvg or retrace_start_idx == -1:
        return None

    # Candles from retracement onward
    retrace_candles = subsequent_candles[retrace_start_idx:]
    if len(retrace_candles) < 3:
        return None

    # Step 2: Identify 5M pullback swings during the retracement
    swings_5m = find_swings(subsequent_candles, swing_length=swing_length, timeframe="5m")

    # Step 3: Check structure shift on the latest closed 5M candle
    latest_5m = subsequent_candles[-1]
    # Use full 5M history for accurate 10-bar average body calculation
    prior_candles = candles_5m[-1 - lookback_body : -1] if len(candles_5m) > lookback_body else candles_5m[:-1]

    if fvg.is_bullish:
        # For LONG: Find the most recent pullback swing high
        pullback_highs = [s for s in swings_5m if s.is_high and s.timestamp >= fvg.created_timestamp]
        if not pullback_highs:
            # Fallback to local highest high during retracement prior to current candle
            if len(subsequent_candles) >= 3:
                pullback_level = max(c.high for c in subsequent_candles[:-1])
            else:
                return None
        else:
            pullback_level = pullback_highs[-1].price

        # Structural low for Stop Loss: lowest low during pullback
        pullback_low = min(c.low for c in subsequent_candles)

        # Bullish Structure Shift: Candle CLOSE > pullback level
        if latest_5m.close > pullback_level and latest_5m.is_bullish:
            # Check 5M displacement
            disp_ok, c_body, a_body, b_pct = check_displacement(
                latest_5m, prior_candles, is_bullish=True,
                body_multiplier=body_multiplier, min_body_pct=min_body_pct, lookback=lookback_body
            )
            if disp_ok:
                return ConfirmationSignal(
                    is_confirmed=True,
                    side="LONG",
                    fvg=fvg,
                    shift_candle=latest_5m,
                    shift_index_5m=len(subsequent_candles) - 1,
                    pullback_high=pullback_level,
                    pullback_low=pullback_low,
                    confirmation_level=pullback_level,
                    displacement_body=c_body,
                    body_percentage=b_pct,
                    retrace_entered_50=has_reached_50_mid
                )

    else:
        # For SHORT: Find most recent pullback swing low
        pullback_lows = [s for s in swings_5m if not s.is_high and s.timestamp >= fvg.created_timestamp]
        if not pullback_lows:
            if len(subsequent_candles) >= 3:
                pullback_level = min(c.low for c in subsequent_candles[:-1])
            else:
                return None
        else:
            pullback_level = pullback_lows[-1].price

        # Structural high for Stop Loss: highest high during pullback
        pullback_high = max(c.high for c in subsequent_candles)

        # Bearish Structure Shift: Candle CLOSE < pullback level
        if latest_5m.close < pullback_level and latest_5m.is_bearish:
            # Check 5M displacement
            disp_ok, c_body, a_body, b_pct = check_displacement(
                latest_5m, prior_candles, is_bullish=False,
                body_multiplier=body_multiplier, min_body_pct=min_body_pct, lookback=lookback_body
            )
            if disp_ok:
                return ConfirmationSignal(
                    is_confirmed=True,
                    side="SHORT",
                    fvg=fvg,
                    shift_candle=latest_5m,
                    shift_index_5m=len(subsequent_candles) - 1,
                    pullback_high=pullback_high,
                    pullback_low=pullback_level,
                    confirmation_level=pullback_level,
                    displacement_body=c_body,
                    body_percentage=b_pct,
                    retrace_entered_50=has_reached_50_mid
                )

    return None
