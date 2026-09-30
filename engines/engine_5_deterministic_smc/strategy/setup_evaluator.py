from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from strategy.models import (
    Candle, BiasType, TradeSide, LiquidityLevel, SweepEvent, 
    MSSEvent, FVGEvent, SMCSetup
)
from strategy.sweep_detector import calculate_atr

def calculate_atr_series(candles: List[Candle], period: int = 14) -> List[float]:
    if len(candles) < period + 1:
        return [0.0] * len(candles)
    atr_values = [0.0] * len(candles)
    tr_list = [0.0]
    for i in range(1, len(candles)):
        c = candles[i]
        prev_c = candles[i - 1]
        tr = max(
            c.high - c.low,
            abs(c.high - prev_c.close),
            abs(c.low - prev_c.close)
        )
        tr_list.append(tr)
    
    # Calculate simple rolling ATR
    for i in range(period, len(candles)):
        atr_values[i] = sum(tr_list[i - period + 1 : i + 1]) / period
    return atr_values

class SetupEvaluator:
    def __init__(self, min_rr: float = 2.0, min_score: int = 11, 
                 sl_atr_multiplier: float = 0.10, max_atr_ratio: float = 2.5,
                 allowed_sessions: Optional[List[Tuple[int, int]]] = None,
                 min_stop_distance_pct: float = 0.002):
        self.min_rr = min_rr
        self.min_score = min_score
        self.sl_atr_multiplier = sl_atr_multiplier
        self.max_atr_ratio = max_atr_ratio
        self.allowed_sessions = allowed_sessions or [(7, 11), (13, 17)]
        self.min_stop_distance_pct = min_stop_distance_pct

    def is_session_allowed(self, timestamp_ms: int) -> bool:
        dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
        hour = dt.hour
        for start_h, end_h in self.allowed_sessions:
            if start_h <= hour < end_h:
                return True
        return False

    def check_volatility(self, candles_15m: List[Candle]) -> Tuple[bool, float, float]:
        """
        Calculates ATR(14) / SMA(ATR, 50).
        Returns (is_acceptable, current_atr, atr_ratio)
        """
        if len(candles_15m) < 65:
            current_atr = calculate_atr(candles_15m, 14)
            return True, current_atr, 1.0

        atr_series = calculate_atr_series(candles_15m, 14)
        valid_atrs = [v for v in atr_series if v > 0]
        if len(valid_atrs) < 50:
            return True, atr_series[-1], 1.0

        current_atr = valid_atrs[-1]
        avg_atr_50 = sum(valid_atrs[-50:]) / 50.0
        atr_ratio = (current_atr / avg_atr_50) if avg_atr_50 > 0 else 1.0

        is_acceptable = atr_ratio <= self.max_atr_ratio
        return is_acceptable, current_atr, atr_ratio

    def evaluate_target_liquidity(self, side: TradeSide, entry_price: float, 
                                 buy_side: List[LiquidityLevel], 
                                 sell_side: List[LiquidityLevel]) -> Optional[LiquidityLevel]:
        """
        Finds the nearest significant opposing liquidity level in the trade direction.
        For LONG: nearest buy-side level above entry.
        For SHORT: nearest sell-side level below entry.
        """
        if side == TradeSide.LONG:
            candidates = [lvl for lvl in buy_side if lvl.price > entry_price]
            if not candidates:
                return None
            # Return nearest level above entry
            return min(candidates, key=lambda lvl: lvl.price)
        else:
            candidates = [lvl for lvl in sell_side if lvl.price < entry_price]
            if not candidates:
                return None
            # Return nearest level below entry
            return max(candidates, key=lambda lvl: lvl.price)

    def evaluate_setup(self, symbol: str, bias_4h: BiasType, bias_1h: BiasType,
                       bias_15m: BiasType, sweep: SweepEvent, mss: MSSEvent,
                       fvg: FVGEvent, candles_15m: List[Candle],
                       buy_side: List[LiquidityLevel], sell_side: List[LiquidityLevel],
                       range_1h_midpoint: Optional[float], funding_rate: float = 0.0) -> Tuple[Optional[SMCSetup], str]:
        """
        Performs full deterministic SMC setup evaluation, calculation, and scoring.
        Returns (setup, rejection_reason)
        """
        # 1. Trading Session Check
        if not self.is_session_allowed(fvg.timestamp):
            return None, "REJECTED_OUTSIDE_SESSION"

        # 2. Volatility Filter Check
        vol_ok, current_atr, atr_ratio = self.check_volatility(candles_15m)
        if not vol_ok:
            return None, f"REJECTED_HIGH_VOLATILITY (ATR ratio: {atr_ratio:.2f} > {self.max_atr_ratio})"

        # 3. Direction & Bias Alignment
        side = sweep.side
        if side == TradeSide.LONG:
            if bias_4h != BiasType.BULLISH or bias_1h != BiasType.BULLISH:
                return None, "REJECTED_NO_HTF_BIAS"
            if not mss.is_bullish or not fvg.is_bullish:
                return None, "REJECTED_STRUCTURE_MISMATCH"
        else:
            if bias_4h != BiasType.BEARISH or bias_1h != BiasType.BEARISH:
                return None, "REJECTED_NO_HTF_BIAS"
            if mss.is_bullish or fvg.is_bullish:
                return None, "REJECTED_STRUCTURE_MISMATCH"

        # 4. Dynamic Entry Price (50% FVG Midpoint)
        entry_price = fvg.midpoint

        # 5. Dynamic Stop Loss
        atr_buffer = current_atr * self.sl_atr_multiplier
        if side == TradeSide.LONG:
            stop_loss = sweep.sweep_low - atr_buffer
            if stop_loss >= entry_price:
                return None, "REJECTED_INVALID_SL"
            risk_dist = entry_price - stop_loss
        else:
            stop_loss = sweep.sweep_high + atr_buffer
            if stop_loss <= entry_price:
                return None, "REJECTED_INVALID_SL"
            risk_dist = stop_loss - entry_price

        if risk_dist <= 0:
            return None, "REJECTED_ZERO_RISK_DISTANCE"

        # Check minimum stop distance to eliminate micro-fee drag
        stop_dist_pct = risk_dist / entry_price
        if stop_dist_pct < self.min_stop_distance_pct:
            return None, f"REJECTED_STOP_TOO_TIGHT ({stop_dist_pct*100:.3f}% < {self.min_stop_distance_pct*100:.2f}%)"

        # 6. Dynamic Take Profit (Target Liquidity)
        target_liq = self.evaluate_target_liquidity(side, entry_price, buy_side, sell_side)
        if not target_liq:
            return None, "REJECTED_NO_TARGET_LIQUIDITY"

        take_profit = target_liq.price
        if side == TradeSide.LONG:
            reward_dist = take_profit - entry_price
        else:
            reward_dist = entry_price - take_profit

        if reward_dist <= 0:
            return None, "REJECTED_TARGET_BEHIND_ENTRY"

        # 7. Risk / Reward Calculation
        rr = reward_dist / risk_dist
        if rr < self.min_rr:
            return None, f"REJECTED_LOW_RR ({rr:.2f} < {self.min_rr})"

        # 8. Premium / Discount Determination
        in_discount = False
        in_premium = False
        if range_1h_midpoint is not None:
            if side == TradeSide.LONG and entry_price < range_1h_midpoint:
                in_discount = True
            elif side == TradeSide.SHORT and entry_price > range_1h_midpoint:
                in_premium = True

        # 9. Setup Scoring (Section 34)
        score = 0
        # 4H Bias
        if (side == TradeSide.LONG and bias_4h == BiasType.BULLISH) or (side == TradeSide.SHORT and bias_4h == BiasType.BEARISH):
            score += 2
        # 1H Bias
        if (side == TradeSide.LONG and bias_1h == BiasType.BULLISH) or (side == TradeSide.SHORT and bias_1h == BiasType.BEARISH):
            score += 2
        # Sweep confirmed
        score += 2
        # Strong Displacement confirmed
        score += 1
        # MSS confirmed
        score += 2
        # Valid FVG
        score += 1
        # Location (Discount for Long / Premium for Short)
        if (side == TradeSide.LONG and in_discount) or (side == TradeSide.SHORT and in_premium):
            score += 1
        # Clear target liquidity
        if target_liq is not None:
            score += 1
        # RR >= 2.0
        if rr >= 2.0:
            score += 2
        # Volatility penalty
        if atr_ratio > 2.0:
            score -= 1
        # Extreme funding penalty
        if abs(funding_rate) > 0.001:  # > 0.1% per 8h
            score -= 1

        if score < self.min_score:
            return None, f"REJECTED_LOW_SCORE ({score} < {self.min_score})"

        # Setup approved
        setup = SMCSetup(
            symbol=symbol,
            side=side,
            timestamp=fvg.timestamp,
            bias_4h=bias_4h,
            bias_1h=bias_1h,
            bias_15m=bias_15m,
            sweep_event=sweep,
            mss_event=mss,
            fvg_event=fvg,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            target_liquidity=target_liq,
            risk_amount=0.0,      # Calculated by RiskManager
            position_size=0.0,    # Calculated by RiskManager
            leverage=5,
            rr=rr,
            setup_score=score,
            atr=current_atr,
            funding_rate=funding_rate,
            in_discount=in_discount,
            in_premium=in_premium,
            created_at_iso=datetime.fromtimestamp(fvg.timestamp / 1000.0, tz=timezone.utc).isoformat()
        )
        return setup, "APPROVED"
