from dataclasses import dataclass
from typing import List

@dataclass
class EngineResult:
    side: str # "LONG" or "SHORT"
    score: float
    passed_rules: List[str]
    failed_rules: List[str]
    stop_loss: float
    take_profit: float
    entry_price: float
    atr: float
    should_trade: bool

class LongEngine:
    """Evaluates the 10-point scoring conditions for LONG Scalper."""
    
    @staticmethod
    def evaluate(ind: dict, sl_mult: float = 0.60, tp_mult: float = 0.60, threshold: float = 8.0) -> EngineResult:
        if not ind:
            return EngineResult("LONG", 0.0, [], [], 0, 0, 0, 0, False)
        
        passed = []
        failed = []
        
        close = ind["close"]
        prev_close = ind["prev_close"]
        open_p = ind["open"]
        prev_open = ind["prev_open"]
        high = ind["high"]
        low = ind["low"]
        atr = ind["atr"]
        
        # 1. RVOL Expansion: RVOL >= 1.20 (Balanced institutional volume threshold)
        if ind["rvol"] >= 1.20:
            passed.append("1. RVOL Expansion")
        else:
            failed.append("1. RVOL Expansion")
            
        # 2. Trend Strength: ADX(14) >= 25 AND (+DI > -DI)
        if ind["adx"] >= 25.0 and ind["plus_di"] > ind["minus_di"]:
            passed.append("2. Trend Strength (ADX & +DI)")
        else:
            failed.append("2. Trend Strength")
            
        # 3. Macro Alignment: Price > 1-Hour EMA(200)
        if ind["macro_ema200"] and close > ind["macro_ema200"]:
            passed.append("3. Macro EMA(200)")
        else:
            failed.append("3. Macro EMA(200)")
            
        # 4. VWAP Level: Close Price > Session VWAP
        if close > ind["vwap"]:
            passed.append("4. VWAP Level")
        else:
            failed.append("4. VWAP Level")
            
        # 5. Ribbon Alignment: EMA(9) > EMA(21) AND EMA(21) > EMA(50)
        if ind["ema9"] > ind["ema21"] and ind["ema21"] > ind["ema50"]:
            passed.append("5. Ribbon Alignment (9>21>50)")
        else:
            failed.append("5. Ribbon Alignment")
            
        # 6. MACD Momentum: MACD Line > Signal Line AND Histogram > 0 (Expanding)
        if ind["macd_line"] > ind["signal_line"] and ind["macd_hist"] > 0 and ind["macd_hist"] >= ind["prev_macd_hist"]:
            passed.append("6. MACD Momentum")
        else:
            failed.append("6. MACD Momentum")
            
        # 7. RSI Corridor: 52 <= RSI(14) <= 68
        if 52.0 <= ind["rsi"] <= 68.0:
            passed.append("7. RSI Corridor (52-68)")
        else:
            failed.append("7. RSI Corridor")
            
        # 8. ATR Expansion: Current ATR(14) > ATR_SMA(20)
        if atr > ind["atr_sma20"]:
            passed.append("8. ATR Expansion")
        else:
            failed.append("8. ATR Expansion")
            
        # 9. Orderbook Spread: (Ask - Bid) / Bid <= 0.0003
        if ind["spread"] <= 0.0003:
            passed.append("9. Tight Spread")
        else:
            failed.append("9. Tight Spread")
            
        # 10. Trigger Candle: Bullish Engulfing OR Pinbar closing in top 25% of bar
        is_bullish_engulf = (close > open_p) and (prev_close < prev_open) and (close >= prev_open) and (open_p <= prev_close)
        candle_range = high - low + 1e-10
        is_top_25_close = ((close - low) / candle_range) >= 0.75
        if is_bullish_engulf or is_top_25_close:
            passed.append("10. Trigger Candle (Engulf/Top 25%)")
        else:
            failed.append("10. Trigger Candle")
            
        score = float(len(passed))
        should_trade = score >= threshold
        sl = close - (sl_mult * atr)
        tp = close + (tp_mult * atr)
        
        return EngineResult(
            side="LONG",
            score=score,
            passed_rules=passed,
            failed_rules=failed,
            stop_loss=sl,
            take_profit=tp,
            entry_price=close,
            atr=atr,
            should_trade=should_trade
        )


class ShortEngine:
    """Evaluates the 10-point scoring conditions for SHORT Scalper."""
    
    @staticmethod
    def evaluate(ind: dict, sl_mult: float = 0.60, tp_mult: float = 0.60, threshold: float = 8.0) -> EngineResult:
        if not ind:
            return EngineResult("SHORT", 0.0, [], [], 0, 0, 0, 0, False)
        
        passed = []
        failed = []
        
        close = ind["close"]
        prev_close = ind["prev_close"]
        open_p = ind["open"]
        prev_open = ind["prev_open"]
        high = ind["high"]
        low = ind["low"]
        atr = ind["atr"]
        
        # 1. RVOL Expansion: RVOL >= 1.20 (Balanced institutional volume threshold)
        if ind["rvol"] >= 1.20:
            passed.append("1. RVOL Expansion")
        else:
            failed.append("1. RVOL Expansion")
            
        # 2. Trend Strength: ADX(14) >= 25 AND (-DI > +DI)
        if ind["adx"] >= 25.0 and ind["minus_di"] > ind["plus_di"]:
            passed.append("2. Trend Strength (ADX & -DI)")
        else:
            failed.append("2. Trend Strength")
            
        # 3. Macro Alignment: Price < 1-Hour EMA(200)
        if ind["macro_ema200"] and close < ind["macro_ema200"]:
            passed.append("3. Macro EMA(200)")
        else:
            failed.append("3. Macro EMA(200)")
            
        # 4. VWAP Level: Close Price < Session VWAP
        if close < ind["vwap"]:
            passed.append("4. VWAP Level")
        else:
            failed.append("4. VWAP Level")
            
        # 5. Ribbon Alignment: EMA(9) < EMA(21) AND EMA(21) < EMA(50)
        if ind["ema9"] < ind["ema21"] and ind["ema21"] < ind["ema50"]:
            passed.append("5. Ribbon Alignment (9<21<50)")
        else:
            failed.append("5. Ribbon Alignment")
            
        # 6. MACD Momentum: MACD Line < Signal Line AND Histogram < 0 (Falling)
        if ind["macd_line"] < ind["signal_line"] and ind["macd_hist"] < 0 and ind["macd_hist"] <= ind["prev_macd_hist"]:
            passed.append("6. MACD Momentum")
        else:
            failed.append("6. MACD Momentum")
            
        # 7. RSI Corridor: 32 <= RSI(14) <= 48
        if 32.0 <= ind["rsi"] <= 48.0:
            passed.append("7. RSI Corridor (32-48)")
        else:
            failed.append("7. RSI Corridor")
            
        # 8. ATR Expansion: Current ATR(14) > ATR_SMA(20)
        if atr > ind["atr_sma20"]:
            passed.append("8. ATR Expansion")
        else:
            failed.append("8. ATR Expansion")
            
        # 9. Orderbook Spread: (Ask - Bid) / Bid <= 0.0003
        if ind["spread"] <= 0.0003:
            passed.append("9. Tight Spread")
        else:
            failed.append("9. Tight Spread")
            
        # 10. Trigger Candle: Bearish Engulfing OR Pinbar closing in bottom 25% of bar
        is_bearish_engulf = (close < open_p) and (prev_close > prev_open) and (close <= prev_open) and (open_p >= prev_close)
        candle_range = high - low + 1e-10
        is_bottom_25_close = ((close - low) / candle_range) <= 0.25
        if is_bearish_engulf or is_bottom_25_close:
            passed.append("10. Trigger Candle (Engulf/Bottom 25%)")
        else:
            failed.append("10. Trigger Candle")
            
        score = float(len(passed))
        should_trade = score >= threshold
        sl = close + (sl_mult * atr)
        tp = close - (tp_mult * atr)
        
        return EngineResult(
            side="SHORT",
            score=score,
            passed_rules=passed,
            failed_rules=failed,
            stop_loss=sl,
            take_profit=tp,
            entry_price=close,
            atr=atr,
            should_trade=should_trade
        )
