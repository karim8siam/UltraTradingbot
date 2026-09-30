from typing import List, Dict, Any, Optional
import config

class Momentum3CandleStrategy:
    """
    15-Minute 5-Candle Momentum Exhaustion Reversal Strategy:
    - Counts 5 consecutive healthy same-color candles (skipping Dojis & unhealthy pin bars).
    - 5 Healthy Green Candles + RSI >= 65.0 -> SHORT (SELL)
    - 5 Healthy Red Candles + RSI <= 35.0 -> LONG (BUY)
    - Zero SL / Zero TP: Exits unconditionally after 3 candles (45 minutes).
    """

    @staticmethod
    def calculate_rsi(closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0.0))
            losses.append(max(-diff, 0.0))
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def is_healthy_candle(candle: Dict[str, Any]) -> bool:
        """
        Check if candle is healthy (not a Doji and not an unhealthy long-wick pin).
        Body must be >= 30% of total candle range.
        """
        open_p = float(candle["open"])
        close_p = float(candle["close"])
        high_p = float(candle["high"])
        low_p = float(candle["low"])

        total_range = high_p - low_p
        if total_range <= 0:
            return False

        body = abs(close_p - open_p)
        body_ratio = body / total_range
        price_move_pct = body / open_p

        # Reject Dojis (body < 30%) and flat noise (move < 0.05%)
        return bool(body_ratio >= config.MIN_BODY_RATIO and price_move_pct >= config.MIN_CANDLE_RANGE_PCT)

    @classmethod
    def evaluate_klines(cls, klines: List[Dict[str, Any]]) -> Optional[str]:
        """
        Evaluates closed klines.
        Skips Dojis and finds the last 5 healthy directional candles.
        Returns:
            "BUY" for Long (5 Red + RSI <= 35)
            "SELL" for Short (5 Green + RSI >= 65)
            None otherwise
        """
        if len(klines) < 10:
            return None

        # Ignore unclosed last candle, look at closed history
        closed_klines = klines[:-1]
        closes = [float(k["close"]) for k in closed_klines]
        rsi = cls.calculate_rsi(closes, config.RSI_PERIOD)

        # Look at window of last 8 closed candles
        recent_window = closed_klines[-8:]
        
        # Filter out Dojis & unhealthy pins
        healthy_candles = [c for c in recent_window if cls.is_healthy_candle(c)]
        
        if len(healthy_candles) < 5:
            return None

        # Take the last 5 healthy candles
        target_5 = healthy_candles[-5:]
        
        # Latest closed candle must be healthy and part of the sequence
        if not cls.is_healthy_candle(closed_klines[-1]):
            return None

        is_5g = all(float(c["close"]) > float(c["open"]) for c in target_5)
        is_5r = all(float(c["close"]) < float(c["open"]) for c in target_5)

        # 5 Green Candles + Overbought RSI -> SHORT
        if is_5g and rsi >= config.RSI_OVERBOUGHT:
            return "SELL"

        # 5 Red Candles + Oversold RSI -> LONG
        if is_5r and rsi <= config.RSI_OVERSOLD:
            return "BUY"

        return None
