from typing import List, Optional
from strategy.models import Candle, LiquidityLevel, SweepEvent, TradeSide, BiasType

def calculate_atr(candles: List[Candle], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    tr_list = []
    for i in range(1, len(candles)):
        c = candles[i]
        prev_c = candles[i - 1]
        tr = max(
            c.high - c.low,
            abs(c.high - prev_c.close),
            abs(c.low - prev_c.close)
        )
        tr_list.append(tr)
    
    if len(tr_list) < period:
        return sum(tr_list) / len(tr_list) if tr_list else 0.0
    
    return sum(tr_list[-period:]) / period

class SweepDetector:
    def __init__(self, atr_period: int = 14):
        self.atr_period = atr_period

    def detect_sweep(self, candles_15m: List[Candle], sell_side_levels: List[LiquidityLevel], 
                     buy_side_levels: List[LiquidityLevel], bias_4h: BiasType, 
                     bias_1h: BiasType) -> Optional[SweepEvent]:
        """
        Detects 15M liquidity sweep according to deterministic SMC rules.
        Evaluates the latest closed 15M candle.
        """
        if len(candles_15m) < 2:
            return None

        current_c = candles_15m[-1]
        atr14 = calculate_atr(candles_15m, self.atr_period)

        # 1. LONG SETUP: 4H & 1H Bullish, Sell-Side Liquidity Sweep
        if bias_4h == BiasType.BULLISH and bias_1h == BiasType.BULLISH:
            for lvl in sell_side_levels:
                # Candle low goes below level AND candle close closes back above level
                if current_c.low < lvl.price and current_c.close > lvl.price:
                    return SweepEvent(
                        timestamp=current_c.timestamp,
                        side=TradeSide.LONG,
                        liquidity_level=lvl,
                        sweep_high=current_c.high,
                        sweep_low=current_c.low,
                        sweep_candle_close=current_c.close,
                        atr_14=atr14
                    )

        # 2. SHORT SETUP: 4H & 1H Bearish, Buy-Side Liquidity Sweep
        elif bias_4h == BiasType.BEARISH and bias_1h == BiasType.BEARISH:
            for lvl in buy_side_levels:
                # Candle high goes above level AND candle close closes back below level
                if current_c.high > lvl.price and current_c.close < lvl.price:
                    return SweepEvent(
                        timestamp=current_c.timestamp,
                        side=TradeSide.SHORT,
                        liquidity_level=lvl,
                        sweep_high=current_c.high,
                        sweep_low=current_c.low,
                        sweep_candle_close=current_c.close,
                        atr_14=atr14
                    )

        return None
