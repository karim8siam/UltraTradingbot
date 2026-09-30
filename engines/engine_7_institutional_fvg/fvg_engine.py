"""
Fair Value Gap (FVG) Engine
Implements 15M 3-candle FVG detection, displacement verification, impulse sizing,
discount/premium valuation, invalidation, and expiration lifecycle.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple
from indicators import Candle, calculate_atr, calculate_average_body


class FVGType(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class FVGStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RETRACED = "RETRACED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    FILLED_NO_ENTRY = "FILLED_NO_ENTRY"
    TRADED = "TRADED"


@dataclass
class FVG:
    fvg_id: str
    symbol: str
    fvg_type: FVGType
    candle1: Candle
    candle2: Candle  # Displacement candle
    candle3: Candle
    created_timestamp: int
    created_index_15m: int
    fvg_low: float
    fvg_high: float
    fvg_mid: float
    fvg_size: float
    fvg_size_atr: float
    atr14_15m: float
    displacement_body: float
    avg_body_10: float
    body_percentage: float
    status: FVGStatus = FVGStatus.ACTIVE
    age_5m: int = 0
    in_discount_premium: bool = False
    retrace_entered_50: bool = False

    @property
    def is_bullish(self) -> bool:
        return self.fvg_type == FVGType.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.fvg_type == FVGType.BEARISH


def check_displacement(
    candle: Candle,
    prior_candles: List[Candle],
    is_bullish: bool,
    body_multiplier: float = 1.5,
    min_body_pct: float = 0.60,
    lookback: int = 10
) -> Tuple[bool, float, float, float]:
    """
    Checks Section 7 displacement criteria:
    - Direction matching
    - CurrentBody >= AverageBody * 1.5
    - BodyPercentage >= 0.60
    Returns: (is_displaced, current_body, avg_body, body_pct)
    """
    current_body = candle.body
    body_pct = candle.body_percentage

    if is_bullish and not candle.is_bullish:
        return False, current_body, 0.0, body_pct
    if not is_bullish and not candle.is_bearish:
        return False, current_body, 0.0, body_pct

    avg_body = calculate_average_body(prior_candles, lookback=lookback)
    if avg_body <= 0:
        return False, current_body, avg_body, body_pct

    is_strong_body = current_body >= (avg_body * body_multiplier)
    is_high_pct = body_pct >= min_body_pct

    return (is_strong_body and is_high_pct), current_body, avg_body, body_pct


def detect_fvgs_on_15m(
    candles_15m: List[Candle],
    symbol: str = "",
    min_fvg_atr: float = 0.05,
    impulse_min_atr: float = 1.5,
    body_multiplier: float = 1.5,
    min_body_pct: float = 0.60,
    lookback_body: int = 10
) -> List[FVG]:
    """
    Scans 15M candles and detects newly formed, fully closed 3-candle FVGs
    with displacement and impulse validation.
    """
    fvgs: List[FVG] = []
    n = len(candles_15m)
    if n < 14 + lookback_body + 3:
        return fvgs

    atr14 = calculate_atr(candles_15m, 14)
    if atr14 <= 0:
        return fvgs

    # Evaluate the most recent completed 3-candle pattern (Candles at n-3, n-2, n-1)
    # We can also scan the latest few bars if needed
    for i in range(13 + lookback_body, n):
        c1 = candles_15m[i - 2]
        c2 = candles_15m[i - 1]  # Middle displacement candle
        c3 = candles_15m[i]

        prior_candles = candles_15m[i - 2 - lookback_body : i - 2]

        # 1. Bullish FVG: c1.high < c3.low
        if c1.high < c3.low and c2.is_bullish:
            fvg_low = c1.high
            fvg_high = c3.low
            fvg_size = fvg_high - fvg_low
            fvg_size_atr = fvg_size / atr14

            # Check displacement
            disp_ok, c_body, a_body, b_pct = check_displacement(
                c2, prior_candles, is_bullish=True,
                body_multiplier=body_multiplier, min_body_pct=min_body_pct, lookback=lookback_body
            )

            # Check impulse move (displacement candle range >= impulse_min_atr * atr14 or leg size)
            impulse_ok = (c2.range >= (impulse_min_atr * atr14 * 0.6)) or (c_body >= (impulse_min_atr * atr14 * 0.5))

            if disp_ok and (fvg_size >= min_fvg_atr * atr14) and impulse_ok:
                fvg_id = f"FVG_BULL_{symbol}_{c3.timestamp}"
                fvg_mid = (fvg_high + fvg_low) / 2.0
                fvgs.append(FVG(
                    fvg_id=fvg_id,
                    symbol=symbol,
                    fvg_type=FVGType.BULLISH,
                    candle1=c1,
                    candle2=c2,
                    candle3=c3,
                    created_timestamp=c3.timestamp,
                    created_index_15m=i,
                    fvg_low=fvg_low,
                    fvg_high=fvg_high,
                    fvg_mid=fvg_mid,
                    fvg_size=fvg_size,
                    fvg_size_atr=fvg_size_atr,
                    atr14_15m=atr14,
                    displacement_body=c_body,
                    avg_body_10=a_body,
                    body_percentage=b_pct,
                ))

        # 2. Bearish FVG: c1.low > c3.high
        elif c1.low > c3.high and c2.is_bearish:
            fvg_low = c3.high
            fvg_high = c1.low
            fvg_size = fvg_high - fvg_low
            fvg_size_atr = fvg_size / atr14

            # Check displacement
            disp_ok, c_body, a_body, b_pct = check_displacement(
                c2, prior_candles, is_bullish=False,
                body_multiplier=body_multiplier, min_body_pct=min_body_pct, lookback=lookback_body
            )

            impulse_ok = (c2.range >= (impulse_min_atr * atr14 * 0.6)) or (c_body >= (impulse_min_atr * atr14 * 0.5))

            if disp_ok and (fvg_size >= min_fvg_atr * atr14) and impulse_ok:
                fvg_id = f"FVG_BEAR_{symbol}_{c3.timestamp}"
                fvg_mid = (fvg_high + fvg_low) / 2.0
                fvgs.append(FVG(
                    fvg_id=fvg_id,
                    symbol=symbol,
                    fvg_type=FVGType.BEARISH,
                    candle1=c1,
                    candle2=c2,
                    candle3=c3,
                    created_timestamp=c3.timestamp,
                    created_index_15m=i,
                    fvg_low=fvg_low,
                    fvg_high=fvg_high,
                    fvg_mid=fvg_mid,
                    fvg_size=fvg_size,
                    fvg_size_atr=fvg_size_atr,
                    atr14_15m=atr14,
                    displacement_body=c_body,
                    avg_body_10=a_body,
                    body_percentage=b_pct,
                ))

    return fvgs


def check_discount_premium(
    fvg: FVG,
    candles_1h: List[Candle],
    swing_length: int = 2
) -> bool:
    """
    Section 46: Discount / Premium check
    For LONG: Prefer FVGs below 50% equilibrium of latest 1H swing range.
    For SHORT: Prefer FVGs above 50% equilibrium.
    """
    if len(candles_1h) < 20:
        return False

    recent = candles_1h[-30:]
    range_high = max(c.high for c in recent)
    range_low = min(c.low for c in recent)
    equilibrium = (range_high + range_low) / 2.0

    if fvg.is_bullish:
        # Discount: FVG midpoint below equilibrium
        return fvg.fvg_mid < equilibrium
    else:
        # Premium: FVG midpoint above equilibrium
        return fvg.fvg_mid > equilibrium
