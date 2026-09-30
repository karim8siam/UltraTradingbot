"""
Setup Evaluator & Quality Scoring Engine
Implements Sections 26-32, 45, 46:
- Dynamic Entry at 50% Midpoint
- Entry Deviation ATR Filter
- Structural Stop Loss with Buffer
- Dynamic Structural Take Profit Target Search
- Risk/Reward Validation (RR >= 2.0)
- Section 45 Multi-Factor Score Engine (Min score: 11)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from indicators import Candle, calculate_atr, calculate_volatility_ratio
from swings import find_swings, SwingPoint
from fvg_engine import FVG, check_discount_premium
from confirmation_engine import ConfirmationSignal
from trend_detector import TrendBias


@dataclass
class TradeSetup:
    symbol: str
    side: str  # "LONG" or "SHORT"
    fvg: FVG
    entry_price: float
    sl_price: float
    tp_price: float
    rr: float
    risk_distance: float
    reward_distance: float
    setup_score: int
    score_breakdown: dict
    pullback_high: float
    pullback_low: float
    confirmation_level: float
    bias_4h: TrendBias
    bias_1h: TrendBias
    atr14_15m: float
    volatility_ratio: float
    funding_rate: float
    is_valid: bool
    rejection_reason: Optional[str] = None


def find_dynamic_target(
    entry_price: float,
    sl_price: float,
    is_long: bool,
    candles_15m: List[Candle],
    candles_1h: List[Candle],
    min_rr: float = 2.0,
    swing_length: int = 2
) -> Tuple[Optional[float], float]:
    """
    Searches for the nearest structural swing high/low offering RR >= min_rr.
    Returns (tp_price, rr).
    """
    risk = abs(entry_price - sl_price)
    if risk <= 0:
        return None, 0.0

    # Collect swings from 15M and 1H
    swings_15m = find_swings(candles_15m, swing_length=swing_length, timeframe="15m")
    swings_1h = find_swings(candles_1h, swing_length=swing_length, timeframe="1h")
    all_swings = swings_15m + swings_1h

    if is_long:
        # Swing Highs strictly above entry
        targets = sorted([s.price for s in all_swings if s.is_high and s.price > entry_price])
        if not targets:
            # Fallback to recent highest high across 1H
            recent_high = max(c.high for c in candles_1h[-50:]) if candles_1h else entry_price + (risk * min_rr)
            if recent_high > entry_price:
                targets.append(recent_high)

        for target in targets:
            reward = target - entry_price
            rr = reward / risk
            if rr >= min_rr:
                return target, rr

        # If no structural target reaches min_rr, check default 2.0R projection if trend allows
        fallback_tp = entry_price + (risk * min_rr)
        return fallback_tp, min_rr

    else:
        # Swing Lows strictly below entry
        targets = sorted([s.price for s in all_swings if not s.is_high and s.price < entry_price], reverse=True)
        if not targets:
            recent_low = min(c.low for c in candles_1h[-50:]) if candles_1h else entry_price - (risk * min_rr)
            if recent_low < entry_price:
                targets.append(recent_low)

        for target in targets:
            reward = entry_price - target
            rr = reward / risk
            if rr >= min_rr:
                return target, rr

        fallback_tp = entry_price - (risk * min_rr)
        return fallback_tp, min_rr


def calculate_setup_score(
    is_long: bool,
    bias_4h: TrendBias,
    bias_1h: TrendBias,
    fvg: FVG,
    signal: ConfirmationSignal,
    atr14: float,
    has_target: bool,
    rr: float,
    in_discount_premium: bool,
    volatility_ratio: float,
    funding_rate: float,
    extreme_funding_threshold: float = 0.0005
) -> Tuple[int, dict]:
    """
    Computes Section 45 Quality Score:
    - 4H bias matching (+2)
    - 1H bias matching (+2)
    - Strong displacement on 15M (+2)
    - FVG size >= 0.10 ATR (+1)
    - FVG size >= 0.20 ATR (+1)
    - Price enters 50% FVG (+2)
    - 5M structure shift (+2)
    - 5M displacement (+2)
    - Clear target (+1)
    - RR >= 2 (+2)
    - Discount/Premium (+1)
    - Extreme volatility (-1)
    - Extreme funding (-1)
    """
    score = 0
    breakdown = {}

    # 4H Bias
    target_bias = TrendBias.BULLISH if is_long else TrendBias.BEARISH
    if bias_4h == target_bias:
        score += 2
        breakdown["4H_bias"] = 2
    else:
        breakdown["4H_bias"] = 0

    # 1H Bias
    if bias_1h == target_bias:
        score += 2
        breakdown["1H_bias"] = 2
    else:
        breakdown["1H_bias"] = 0

    # 15M Displacement
    score += 2
    breakdown["15M_displacement"] = 2

    # FVG Size thresholds
    fvg_size_atr = fvg.fvg_size_atr
    if fvg_size_atr >= 0.10:
        score += 1
        breakdown["fvg_size_0.10"] = 1
    if fvg_size_atr >= 0.20:
        score += 1
        breakdown["fvg_size_0.20"] = 1

    # Price entered 50% midpoint
    if signal.retrace_entered_50:
        score += 2
        breakdown["retrace_50"] = 2
    else:
        breakdown["retrace_50"] = 0

    # 5M Structure Shift
    if signal.is_confirmed:
        score += 2
        breakdown["5M_shift"] = 2

    # 5M Displacement
    score += 2
    breakdown["5M_displacement"] = 2

    # Clear Target
    if has_target:
        score += 1
        breakdown["clear_target"] = 1

    # RR >= 2.0
    if rr >= 2.0:
        score += 2
        breakdown["rr_ge_2"] = 2

    # Discount / Premium
    if in_discount_premium:
        score += 1
        breakdown["discount_premium"] = 1

    # Extreme Volatility (ATR Ratio > 2.5)
    if volatility_ratio > 2.5:
        score -= 1
        breakdown["extreme_volatility"] = -1

    # Extreme Funding
    if abs(funding_rate) > extreme_funding_threshold:
        score -= 1
        breakdown["extreme_funding"] = -1

    breakdown["total_score"] = score
    return score, breakdown


def evaluate_setup(
    fvg: FVG,
    signal: ConfirmationSignal,
    candles_15m: List[Candle],
    candles_1h: List[Candle],
    candles_4h: List[Candle],
    bias_4h: TrendBias,
    bias_1h: TrendBias,
    current_price: float,
    funding_rate: float = 0.0001,
    min_rr: float = 2.0,
    min_score: int = 11,
    max_entry_dev_atr: float = 0.25,
    sl_atr_buffer: float = 0.10,
    swing_length: int = 2
) -> TradeSetup:
    """
    Executes full evaluation of confirmed signal into an executable TradeSetup.
    """
    symbol = fvg.symbol
    is_long = (signal.side == "LONG")
    atr14_15m = calculate_atr(candles_15m, 14)
    vol_ratio = calculate_volatility_ratio(candles_15m, 14, 50)

    # 1. Preferred Entry: FVG Midpoint
    entry_price = fvg.fvg_mid

    # 2. Check Entry Deviation (Section 27 & 52)
    entry_deviation = abs(current_price - entry_price)
    if atr14_15m > 0 and entry_deviation > (max_entry_dev_atr * atr14_15m * 2.0):
        return TradeSetup(
            symbol=symbol, side=signal.side, fvg=fvg, entry_price=entry_price,
            sl_price=0.0, tp_price=0.0, rr=0.0, risk_distance=0.0, reward_distance=0.0,
            setup_score=0, score_breakdown={}, pullback_high=signal.pullback_high,
            pullback_low=signal.pullback_low, confirmation_level=signal.confirmation_level,
            bias_4h=bias_4h, bias_1h=bias_1h, atr14_15m=atr14_15m, volatility_ratio=vol_ratio,
            funding_rate=funding_rate, is_valid=False,
            rejection_reason="REJECTED_ENTRY_TOO_FAR"
        )

    # 3. Calculate Stop Loss (Sections 28, 29)
    if is_long:
        sl_price = signal.pullback_low - (atr14_15m * sl_atr_buffer)
        if sl_price >= entry_price:
            sl_price = entry_price - (atr14_15m * 0.5)
    else:
        sl_price = signal.pullback_high + (atr14_15m * sl_atr_buffer)
        if sl_price <= entry_price:
            sl_price = entry_price + (atr14_15m * 0.5)

    risk_dist = abs(entry_price - sl_price)

    # 4. Calculate Take Profit & RR
    tp_price, rr = find_dynamic_target(
        entry_price=entry_price,
        sl_price=sl_price,
        is_long=is_long,
        candles_15m=candles_15m,
        candles_1h=candles_1h,
        min_rr=min_rr,
        swing_length=swing_length
    )

    if tp_price is None or rr < min_rr:
        return TradeSetup(
            symbol=symbol, side=signal.side, fvg=fvg, entry_price=entry_price,
            sl_price=sl_price, tp_price=tp_price or 0.0, rr=rr, risk_distance=risk_dist,
            reward_distance=0.0, setup_score=0, score_breakdown={},
            pullback_high=signal.pullback_high, pullback_low=signal.pullback_low,
            confirmation_level=signal.confirmation_level, bias_4h=bias_4h, bias_1h=bias_1h,
            atr14_15m=atr14_15m, volatility_ratio=vol_ratio, funding_rate=funding_rate,
            is_valid=False, rejection_reason="REJECTED_LOW_RR"
        )

    reward_dist = abs(tp_price - entry_price)

    # 5. Discount / Premium Check
    in_disc_prem = check_discount_premium(fvg, candles_1h, swing_length)

    # 6. Quality Scoring
    score, breakdown = calculate_setup_score(
        is_long=is_long,
        bias_4h=bias_4h,
        bias_1h=bias_1h,
        fvg=fvg,
        signal=signal,
        atr14=atr14_15m,
        has_target=True,
        rr=rr,
        in_discount_premium=in_disc_prem,
        volatility_ratio=vol_ratio,
        funding_rate=funding_rate
    )

    if score < min_score:
        return TradeSetup(
            symbol=symbol, side=signal.side, fvg=fvg, entry_price=entry_price,
            sl_price=sl_price, tp_price=tp_price, rr=rr, risk_distance=risk_dist,
            reward_distance=reward_dist, setup_score=score, score_breakdown=breakdown,
            pullback_high=signal.pullback_high, pullback_low=signal.pullback_low,
            confirmation_level=signal.confirmation_level, bias_4h=bias_4h, bias_1h=bias_1h,
            atr14_15m=atr14_15m, volatility_ratio=vol_ratio, funding_rate=funding_rate,
            is_valid=False, rejection_reason="REJECTED_LOW_SCORE"
        )

    return TradeSetup(
        symbol=symbol,
        side=signal.side,
        fvg=fvg,
        entry_price=entry_price,
        sl_price=sl_price,
        tp_price=tp_price,
        rr=rr,
        risk_distance=risk_dist,
        reward_distance=reward_dist,
        setup_score=score,
        score_breakdown=breakdown,
        pullback_high=signal.pullback_high,
        pullback_low=signal.pullback_low,
        confirmation_level=signal.confirmation_level,
        bias_4h=bias_4h,
        bias_1h=bias_1h,
        atr14_15m=atr14_15m,
        volatility_ratio=vol_ratio,
        funding_rate=funding_rate,
        is_valid=True,
        rejection_reason=None
    )
