"""
GFS Strategy Engine (Grandfather -> Father -> Son)
1D -> 4H -> 15M Multi-Timeframe Algorithmic Rule Engine
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple

from config import (
    DAILY_EMA_FAST, DAILY_EMA_SLOW,
    FOUR_HOUR_EMA_FAST, FOUR_HOUR_EMA_SLOW,
    SON_ATR_PERIOD, SON_ATR_AVG_PERIOD,
    SWING_LENGTH, DISPLACEMENT_BODY_MULTIPLIER, MIN_BODY_PERCENTAGE,
    DISPLACEMENT_LOOKBACK, ENTRY_RETRACEMENT_RATIO,
    MAX_ENTRY_DEVIATION_ATR, SL_ATR_BUFFER, MIN_RR, MIN_SETUP_SCORE,
    MAX_SETUP_AGE, MAX_ATR_RATIO
)
from indicators import (
    Candle, SwingPoint, calculate_ema, calculate_ema_slope,
    calculate_atr, calculate_atr_ratio, find_swings, check_displacement
)


class TrendDirection(Enum):
    BULLISH = 'BULLISH'
    BEARISH = 'BEARISH'
    NEUTRAL = 'NEUTRAL'


class SetupState(Enum):
    IDLE = 'IDLE'
    WAITING_FOR_PULLBACK = 'WAITING_FOR_PULLBACK'
    IN_PULLBACK_ZONE = 'IN_PULLBACK_ZONE'
    MONITORING_15M = 'MONITORING_15M'
    STRUCTURE_BROKEN = 'STRUCTURE_BROKEN'
    READY_FOR_ENTRY = 'READY_FOR_ENTRY'
    INVALIDATED = 'INVALIDATED'
    EXPIRED = 'EXPIRED'


@dataclass
class GFSSetup:
    symbol: str
    direction: TrendDirection     # BULLISH (Long) or BEARISH (Short)
    timestamp: int
    daily_trend: TrendDirection
    daily_ema50: float
    daily_ema200: float
    four_hour_trend: TrendDirection
    four_hour_ema20: float
    four_hour_ema50: float
    pullback_zone_valid: bool
    structure_level: float        # Broken 15M Swing Level
    pullback_extreme: float       # Pullback Low (Long) or High (Short)
    confirmation_candle_idx: int
    atr14_15m: float
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    setup_score: int
    score_breakdown: Dict[str, int] = field(default_factory=dict)
    rejection_reason: Optional[str] = None
    age_candles: int = 0
    is_valid: bool = True


class GFSStrategyEngine:
    """
    Deterministic, closed-candle multi-timeframe GFS Strategy Evaluator.
    """

    def __init__(self):
        pass

    def evaluate_1d_trend(self, daily_candles: List[Candle], index: int = -1) -> Tuple[TrendDirection, float, float, str]:
        """
        Grandfather (1D) Trend Rule:
        Bullish: EMA50 > EMA200 AND Close > EMA50 AND EMA50 slope positive
        Bearish: EMA50 < EMA200 AND Close < EMA50 AND EMA50 slope negative
        Else: NEUTRAL
        """
        if len(daily_candles) < DAILY_EMA_SLOW:
            return TrendDirection.NEUTRAL, 0.0, 0.0, 'INSUFFICIENT_1D_DATA'

        closes = [c.close for c in daily_candles]
        ema50_series = calculate_ema(closes, DAILY_EMA_FAST)
        ema200_series = calculate_ema(closes, DAILY_EMA_SLOW)

        idx = index if index >= 0 else len(daily_candles) + index
        if idx < DAILY_EMA_SLOW or idx >= len(daily_candles):
            return TrendDirection.NEUTRAL, 0.0, 0.0, 'INDEX_OUT_OF_BOUNDS'

        ema50 = ema50_series[idx]
        ema200 = ema200_series[idx]
        candle = daily_candles[idx]
        slope_val, slope_dir = calculate_ema_slope(ema50_series, idx)

        if ema50 > ema200 and candle.close > ema50 and slope_dir == 'BULLISH':
            return TrendDirection.BULLISH, ema50, ema200, 'OK'
        elif ema50 < ema200 and candle.close < ema50 and slope_dir == 'BEARISH':
            return TrendDirection.BEARISH, ema50, ema200, 'OK'
        else:
            return TrendDirection.NEUTRAL, ema50, ema200, 'DAILY_EMA_NEUTRAL'

    def evaluate_4h_trend(self, four_hour_candles: List[Candle], index: int = -1) -> Tuple[TrendDirection, float, float, str]:
        """
        Father (4H) Trend Rule:
        Bullish: EMA20 > EMA50 AND Close > EMA20 AND EMA20 slope positive
        Bearish: EMA20 < EMA50 AND Close < EMA20 AND EMA20 slope negative
        Else: NEUTRAL
        """
        if len(four_hour_candles) < FOUR_HOUR_EMA_SLOW:
            return TrendDirection.NEUTRAL, 0.0, 0.0, 'INSUFFICIENT_4H_DATA'

        closes = [c.close for c in four_hour_candles]
        ema20_series = calculate_ema(closes, FOUR_HOUR_EMA_FAST)
        ema50_series = calculate_ema(closes, FOUR_HOUR_EMA_SLOW)

        idx = index if index >= 0 else len(four_hour_candles) + index
        if idx < FOUR_HOUR_EMA_SLOW or idx >= len(four_hour_candles):
            return TrendDirection.NEUTRAL, 0.0, 0.0, 'INDEX_OUT_OF_BOUNDS'

        ema20 = ema20_series[idx]
        ema50 = ema50_series[idx]
        candle = four_hour_candles[idx]
        slope_val, slope_dir = calculate_ema_slope(ema20_series, idx)

        if ema20 > ema50 and candle.close > ema20 and slope_dir == 'BULLISH':
            return TrendDirection.BULLISH, ema20, ema50, 'OK'
        elif ema20 < ema50 and candle.close < ema50 and slope_dir == 'BEARISH':
            return TrendDirection.BEARISH, ema20, ema50, 'OK'
        else:
            return TrendDirection.NEUTRAL, ema20, ema50, 'FOUR_HOUR_EMA_NEUTRAL'

    def check_4h_pullback_zone(
        self,
        four_hour_candles: List[Candle],
        trend: TrendDirection,
        index: int = -1
    ) -> Tuple[bool, bool, float, float]:
        """
        4H Pullback Zone:
        Long: Price enters EMA20-EMA50 zone (Low <= EMA20).
              Must NOT close below EMA50 (if Close < EMA50 -> Invalidated).
        Short: Price enters EMA20-EMA50 zone (High >= EMA20).
               Must NOT close above EMA50 (if Close > EMA50 -> Invalidated).
        Returns: (in_zone, is_invalidated, ema20, ema50)
        """
        if len(four_hour_candles) < FOUR_HOUR_EMA_SLOW:
            return False, False, 0.0, 0.0

        closes = [c.close for c in four_hour_candles]
        ema20_series = calculate_ema(closes, FOUR_HOUR_EMA_FAST)
        ema50_series = calculate_ema(closes, FOUR_HOUR_EMA_SLOW)

        idx = index if index >= 0 else len(four_hour_candles) + index
        if idx < 0 or idx >= len(four_hour_candles):
            return False, False, 0.0, 0.0

        ema20 = ema20_series[idx]
        ema50 = ema50_series[idx]
        candle = four_hour_candles[idx]

        if trend == TrendDirection.BULLISH:
            # Invalidation: 4H closed below EMA50
            if candle.close < ema50:
                return False, True, ema20, ema50
            # Pullback zone reached: low penetrated EMA20 or traded between EMA20 and EMA50
            in_zone = candle.low <= ema20 and candle.low >= (ema50 * 0.995)
            return in_zone, False, ema20, ema50

        elif trend == TrendDirection.BEARISH:
            # Invalidation: 4H closed above EMA50
            if candle.close > ema50:
                return False, True, ema20, ema50
            # Pullback zone reached: high penetrated EMA20 or traded between EMA20 and EMA50
            in_zone = candle.high >= ema20 and candle.high <= (ema50 * 1.005)
            return in_zone, False, ema20, ema50

        return False, False, ema20, ema50

    def find_4h_target(
        self,
        four_hour_candles: List[Candle],
        direction: TrendDirection,
        entry_price: float,
        stop_loss: float,
        min_rr: float = MIN_RR
    ) -> Tuple[Optional[float], float]:
        """
        Searches 4H swing structure for meaningful Take Profit targets giving RR >= min_rr.
        Long: Target previous significant 4H swing highs > entry_price.
        Short: Target previous significant 4H swing lows < entry_price.
        """
        h4_window = four_hour_candles[-100:] if len(four_hour_candles) > 100 else four_hour_candles
        swings = find_swings(h4_window, swing_length=SWING_LENGTH)
        stop_dist = abs(entry_price - stop_loss)
        if stop_dist <= 0:
            return None, 0.0

        if direction == TrendDirection.BULLISH:
            # Filter swing highs above entry price, ordered chronologically or by level
            candidate_highs = [s for s in swings if s.is_high and s.price > entry_price]
            # Reverse to inspect most recent structural highs first
            for swing in reversed(candidate_highs):
                reward = swing.price - entry_price
                rr = reward / stop_dist
                if rr >= min_rr:
                    return swing.price, rr

            # If recent swings don't satisfy RR, search highest historical swing high in range
            valid_swings = sorted([s.price for s in candidate_highs if (s.price - entry_price) / stop_dist >= min_rr])
            if valid_swings:
                target = valid_swings[0]
                return target, (target - entry_price) / stop_dist

        elif direction == TrendDirection.BEARISH:
            # Filter swing lows below entry price
            candidate_lows = [s for s in swings if (not s.is_high) and s.price < entry_price]
            for swing in reversed(candidate_lows):
                reward = entry_price - swing.price
                rr = reward / stop_dist
                if rr >= min_rr:
                    return swing.price, rr

            valid_swings = sorted([s.price for s in candidate_lows if (entry_price - s.price) / stop_dist >= min_rr], reverse=True)
            if valid_swings:
                target = valid_swings[0]
                return target, (entry_price - target) / stop_dist

        return None, 0.0

    def calculate_setup_score(
        self,
        daily_trend: TrendDirection,
        four_hour_trend: TrendDirection,
        in_pullback_zone: bool,
        structure_break_confirmed: bool,
        displacement_confirmed: bool,
        entry_price: float,
        four_hour_ema50: float,
        four_hour_target: Optional[float],
        rr: float,
        daily_candles: List[Candle],
        atr_ratio: float,
        funding_rate: float = 0.0
    ) -> Tuple[int, Dict[str, int]]:
        """
        GFS Quantitative Scoring System:
        - 1D trend aligned: +2
        - 4H trend aligned: +2
        - 4H pullback reaches EMA20-50: +2
        - 15M structure break: +2
        - 15M displacement: +2
        - Entry near 4H EMA50: +1
        - Clear 4H target: +1
        - RR >= 2.0: +2
        - Strong 1D trend: +1
        - Extreme volatility (ATR ratio > 2.0): -1
        - Extreme funding (|funding| > 0.0005): -1
        """
        score = 0
        breakdown = {}

        if daily_trend in (TrendDirection.BULLISH, TrendDirection.BEARISH):
            score += 2
            breakdown['1D_TREND'] = 2

        if four_hour_trend == daily_trend:
            score += 2
            breakdown['4H_TREND'] = 2

        if in_pullback_zone:
            score += 2
            breakdown['4H_PULLBACK_ZONE'] = 2

        if structure_break_confirmed:
            score += 2
            breakdown['15M_STRUCTURE_BREAK'] = 2

        if displacement_confirmed:
            score += 2
            breakdown['15M_DISPLACEMENT'] = 2

        # Entry near 4H EMA50 (within 1.5%)
        if four_hour_ema50 > 0 and abs(entry_price - four_hour_ema50) / four_hour_ema50 < 0.015:
            score += 1
            breakdown['NEAR_4H_EMA50'] = 1

        if four_hour_target is not None:
            score += 1
            breakdown['CLEAR_4H_TARGET'] = 1

        if rr >= MIN_RR:
            score += 2
            breakdown['VALID_RR'] = 2

        # Strong 1D trend check
        if len(daily_candles) >= 50:
            last_d = daily_candles[-1]
            d_closes = [c.close for c in daily_candles]
            d_ema50 = calculate_ema(d_closes, DAILY_EMA_FAST)[-1]
            if daily_trend == TrendDirection.BULLISH and last_d.close > (d_ema50 * 1.01):
                score += 1
                breakdown['STRONG_1D_TREND'] = 1
            elif daily_trend == TrendDirection.BEARISH and last_d.close < (d_ema50 * 0.99):
                score += 1
                breakdown['STRONG_1D_TREND'] = 1

        if atr_ratio > 2.0:
            score -= 1
            breakdown['HIGH_VOLATILITY_PENALTY'] = -1

        if abs(funding_rate) > 0.0005:
            score -= 1
            breakdown['EXTREME_FUNDING_PENALTY'] = -1

        return score, breakdown

    def evaluate_15m_entry_setup(
        self,
        symbol: str,
        daily_candles: List[Candle],
        four_hour_candles: List[Candle],
        son_candles: List[Candle],
        funding_rate: float = 0.0
    ) -> Tuple[Optional[GFSSetup], str]:
        """
        Master Evaluation of GFS Signal at the latest closed 15M candle.
        """
        if len(daily_candles) < DAILY_EMA_SLOW:
            return None, 'REJECTED_INSUFFICIENT_1D_DATA'
        if len(four_hour_candles) < FOUR_HOUR_EMA_SLOW:
            return None, 'REJECTED_INSUFFICIENT_4H_DATA'
        if len(son_candles) < max(SON_ATR_AVG_PERIOD, DISPLACEMENT_LOOKBACK + 5):
            return None, 'REJECTED_INSUFFICIENT_15M_DATA'

        # 1. Evaluate Grandfather (1D)
        daily_trend, d_ema50, d_ema200, d_reason = self.evaluate_1d_trend(daily_candles)
        if daily_trend == TrendDirection.NEUTRAL:
            return None, 'REJECTED_DAILY_NEUTRAL'

        # 2. Evaluate Father (4H)
        four_hour_trend, h4_ema20, h4_ema50, h4_reason = self.evaluate_4h_trend(four_hour_candles)
        if four_hour_trend == TrendDirection.NEUTRAL:
            return None, 'REJECTED_4H_NEUTRAL'
        if daily_trend != four_hour_trend:
            return None, 'REJECTED_4H_MISALIGNED'

        # 3. Evaluate 4H Pullback Zone
        in_zone, is_invalidated, _, _ = self.check_4h_pullback_zone(four_hour_candles, four_hour_trend)
        if is_invalidated:
            return None, 'REJECTED_PULLBACK_INVALIDATED'
        if not in_zone:
            return None, 'REJECTED_NO_4H_PULLBACK'

        # 4. Evaluate 15M Son ATR & Volatility Filter
        atr_series = calculate_atr(son_candles, period=SON_ATR_PERIOD)
        atr14 = atr_series[-1]
        atr_ratio = calculate_atr_ratio(atr_series, -1, lookback=SON_ATR_AVG_PERIOD)
        if atr_ratio > MAX_ATR_RATIO:
            return None, 'REJECTED_HIGH_VOLATILITY'

        # 5. Evaluate 15M Swing Structure & Market Structure Shift (MSS)
        son_window = son_candles[-100:] if len(son_candles) > 100 else son_candles
        swings_15m = find_swings(son_window, swing_length=SWING_LENGTH)
        if len(swings_15m) < 4:
            return None, 'REJECTED_NO_15M_SWINGS'

        latest_closed_idx = len(son_candles) - 1
        latest_candle = son_candles[latest_closed_idx]

        # Check Displacement on confirmation candle
        is_long = (daily_trend == TrendDirection.BULLISH)
        disp_ok, disp_stats = check_displacement(
            son_candles,
            latest_closed_idx,
            is_long=is_long,
            body_multiplier=DISPLACEMENT_BODY_MULTIPLIER,
            min_body_pct=MIN_BODY_PERCENTAGE,
            lookback=DISPLACEMENT_LOOKBACK
        )
        if not disp_ok:
            return None, 'REJECTED_WEAK_15M_DISPLACEMENT'

        # Long Structure Break:
        if is_long:
            # Find recent lower high in 15M
            recent_highs = [s for s in swings_15m if s.is_high and s.confirmed_at_index < latest_closed_idx]
            if not recent_highs:
                return None, 'REJECTED_NO_15M_CONFIRMATION'

            latest_lh = recent_highs[-1]
            # Confirmation candle must close above that lower high
            if latest_candle.close <= latest_lh.price:
                return None, 'REJECTED_NO_15M_STRUCTURE_BREAK'

            # Pullback structural low
            recent_lows = [s for s in swings_15m if (not s.is_high) and s.index >= latest_lh.index - 5 and s.confirmed_at_index <= latest_closed_idx]
            if recent_lows:
                pullback_extreme = min([s.price for s in recent_lows] + [latest_candle.low])
            else:
                pullback_extreme = min([c.low for c in son_candles[-10:]])

            # Entry = 50% retracement of confirmation candle range
            planned_entry = latest_candle.low + (latest_candle.range * ENTRY_RETRACEMENT_RATIO)
            stop_loss = pullback_extreme - (atr14 * SL_ATR_BUFFER)

            # Check Stop Loss validity
            if stop_loss >= planned_entry:
                return None, 'REJECTED_INVALID_SL'

            # 4H Take Profit Target & RR
            tp_target, rr = self.find_4h_target(four_hour_candles, daily_trend, planned_entry, stop_loss, min_rr=MIN_RR)
            if tp_target is None or rr < MIN_RR:
                return None, 'REJECTED_LOW_RR'

            # Check deviation
            if abs(latest_candle.close - planned_entry) > (atr14 * MAX_ENTRY_DEVIATION_ATR):
                # If close is slightly above planned entry, entry limit can still be placed at planned_entry
                pass

            # Setup Score
            score, breakdown = self.calculate_setup_score(
                daily_trend=daily_trend,
                four_hour_trend=four_hour_trend,
                in_pullback_zone=in_zone,
                structure_break_confirmed=True,
                displacement_confirmed=True,
                entry_price=planned_entry,
                four_hour_ema50=h4_ema50,
                four_hour_target=tp_target,
                rr=rr,
                daily_candles=daily_candles,
                atr_ratio=atr_ratio,
                funding_rate=funding_rate
            )

            if score < MIN_SETUP_SCORE:
                return None, 'REJECTED_LOW_SCORE'

            setup = GFSSetup(
                symbol=symbol,
                direction=TrendDirection.BULLISH,
                timestamp=latest_candle.timestamp,
                daily_trend=daily_trend,
                daily_ema50=d_ema50,
                daily_ema200=d_ema200,
                four_hour_trend=four_hour_trend,
                four_hour_ema20=h4_ema20,
                four_hour_ema50=h4_ema50,
                pullback_zone_valid=True,
                structure_level=latest_lh.price,
                pullback_extreme=pullback_extreme,
                confirmation_candle_idx=latest_closed_idx,
                atr14_15m=atr14,
                entry_price=round(planned_entry, 6),
                stop_loss=round(stop_loss, 6),
                take_profit=round(tp_target, 6),
                risk_reward=round(rr, 2),
                setup_score=score,
                score_breakdown=breakdown,
                rejection_reason=None,
                age_candles=0,
                is_valid=True
            )
            return setup, 'APPROVED'

        # Short Structure Break:
        else:
            recent_lows = [s for s in swings_15m if (not s.is_high) and s.confirmed_at_index < latest_closed_idx]
            if not recent_lows:
                return None, 'REJECTED_NO_15M_CONFIRMATION'

            latest_hl = recent_lows[-1]
            if latest_candle.close >= latest_hl.price:
                return None, 'REJECTED_NO_15M_STRUCTURE_BREAK'

            # Pullback structural high
            recent_highs = [s for s in swings_15m if s.is_high and s.index >= latest_hl.index - 5 and s.confirmed_at_index <= latest_closed_idx]
            if recent_highs:
                pullback_extreme = max([s.price for s in recent_highs] + [latest_candle.high])
            else:
                pullback_extreme = max([c.high for c in son_candles[-10:]])

            planned_entry = latest_candle.high - (latest_candle.range * ENTRY_RETRACEMENT_RATIO)
            stop_loss = pullback_extreme + (atr14 * SL_ATR_BUFFER)

            if stop_loss <= planned_entry:
                return None, 'REJECTED_INVALID_SL'

            tp_target, rr = self.find_4h_target(four_hour_candles, daily_trend, planned_entry, stop_loss, min_rr=MIN_RR)
            if tp_target is None or rr < MIN_RR:
                return None, 'REJECTED_LOW_RR'

            score, breakdown = self.calculate_setup_score(
                daily_trend=daily_trend,
                four_hour_trend=four_hour_trend,
                in_pullback_zone=in_zone,
                structure_break_confirmed=True,
                displacement_confirmed=True,
                entry_price=planned_entry,
                four_hour_ema50=h4_ema50,
                four_hour_target=tp_target,
                rr=rr,
                daily_candles=daily_candles,
                atr_ratio=atr_ratio,
                funding_rate=funding_rate
            )

            if score < MIN_SETUP_SCORE:
                return None, 'REJECTED_LOW_SCORE'

            setup = GFSSetup(
                symbol=symbol,
                direction=TrendDirection.BEARISH,
                timestamp=latest_candle.timestamp,
                daily_trend=daily_trend,
                daily_ema50=d_ema50,
                daily_ema200=d_ema200,
                four_hour_trend=four_hour_trend,
                four_hour_ema20=h4_ema20,
                four_hour_ema50=h4_ema50,
                pullback_zone_valid=True,
                structure_level=latest_hl.price,
                pullback_extreme=pullback_extreme,
                confirmation_candle_idx=latest_closed_idx,
                atr14_15m=atr14,
                entry_price=round(planned_entry, 6),
                stop_loss=round(stop_loss, 6),
                take_profit=round(tp_target, 6),
                risk_reward=round(rr, 2),
                setup_score=score,
                score_breakdown=breakdown,
                rejection_reason=None,
                age_candles=0,
                is_valid=True
            )
            return setup, 'APPROVED'
