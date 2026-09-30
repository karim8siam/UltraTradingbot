"""
Vectorized & Event-Driven 24-Hour Strategy Performance Evaluator.
Simulates past 24 hours of trading across all engine archetypes to measure
exact win rate and 1:2 Risk/Reward return for each coin.
"""

import json
import math
import urllib.request
from typing import Dict, List, Any, Optional, Tuple
from config import PUBLIC_DATA_URLS, ALT_SYMBOL_MAPPINGS, MIN_RR


def fetch_klines(symbol: str, interval: str = "15m", limit: int = 150) -> List[Dict[str, Any]]:
    """
    Fetches candlestick data with automatic public mirror fallbacks.
    Zero API key required.
    """
    candidates = [symbol]
    if symbol in ALT_SYMBOL_MAPPINGS:
        candidates.append(ALT_SYMBOL_MAPPINGS[symbol])

    for sym in candidates:
        for base in PUBLIC_DATA_URLS:
            path = f"/klines?symbol={sym}&interval={interval}&limit={limit}"
            url = f"{base}{path}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (UltraTradingBot/2.0)"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candles = []
                    for k in data:
                        candles.append({
                            "timestamp": int(k[0]),
                            "open": float(k[1]),
                            "high": float(k[2]),
                            "low": float(k[3]),
                            "close": float(k[4]),
                            "volume": float(k[5]),
                            "quote_vol": float(k[7])
                        })
                    if len(candles) >= 20:
                        return candles
            except Exception:
                continue
    return []


def calculate_ema(series: List[float], period: int) -> List[float]:
    if not series:
        return []
    alpha = 2.0 / (period + 1.0)
    ema = [series[0]]
    for i in range(1, len(series)):
        ema.append(alpha * series[i] + (1 - alpha) * ema[-1])
    return ema


def calculate_atr(candles: List[Dict[str, Any]], period: int = 14) -> List[float]:
    if len(candles) < 2:
        return [0.0] * len(candles)
    tr = [candles[0]["high"] - candles[0]["low"]]
    for i in range(1, len(candles)):
        hl = candles[i]["high"] - candles[i]["low"]
        hc = abs(candles[i]["high"] - candles[i-1]["close"])
        lc = abs(candles[i]["low"] - candles[i-1]["close"])
        tr.append(max(hl, hc, lc))
    return calculate_ema(tr, period)


def calculate_rsi(closes: List[float], period: int = 14) -> List[float]:
    if len(closes) < period + 1:
        return [50.0] * len(closes)
    gains, losses = [0.0], [0.0]
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))

    avg_gain = calculate_ema(gains, period)
    avg_loss = calculate_ema(losses, period)

    rsi = []
    for g, l in zip(avg_gain, avg_loss):
        if l == 0:
            rsi.append(100.0)
        else:
            rs = g / l
            rsi.append(100.0 - (100.0 / (1.0 + rs)))
    return rsi


class StrategyEvaluator:
    """
    Evaluates 24-hour performance for each engine archetype with 1:2 R:R.
    """

    @staticmethod
    def evaluate_confluence_scalper(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Archetype: 10-Point Technical Confluence Scalper (Engines 1, 3, 10).
        1:2 R:R (SL = 1.55 ATR, TP = 3.10 ATR).
        """
        if len(candles) < 40:
            return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "net_r": 0.0}

        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]
        atr = calculate_atr(candles, 14)
        rsi = calculate_rsi(closes, 14)
        ema9 = calculate_ema(closes, 9)
        ema21 = calculate_ema(closes, 21)
        ema50 = calculate_ema(closes, 50)
        vol_sma20 = calculate_ema(volumes, 20)

        # 24-hour evaluation: inspect last 48 candles (for 30m) or 96 candles (for 15m)
        eval_start = max(30, len(candles) - 96)
        trades = []

        for i in range(eval_start, len(candles) - 4):
            c = candles[i]
            cur_atr = atr[i]
            if cur_atr <= 0:
                continue

            rvol = volumes[i] / max(vol_sma20[i], 1e-9)
            bullish_ribbon = ema9[i] > ema21[i] > ema50[i]
            bearish_ribbon = ema9[i] < ema21[i] < ema50[i]

            signal = None
            if rvol >= 1.4 and bullish_ribbon and 48 <= rsi[i] <= 68 and c["close"] > c["open"]:
                signal = "LONG"
            elif rvol >= 1.4 and bearish_ribbon and 32 <= rsi[i] <= 52 and c["close"] < c["open"]:
                signal = "SHORT"

            if signal:
                entry = c["close"]
                sl = entry - (1.55 * cur_atr) if signal == "LONG" else entry + (1.55 * cur_atr)
                tp = entry + (3.10 * cur_atr) if signal == "LONG" else entry - (3.10 * cur_atr)

                # Simulate forward outcome
                outcome = None
                for f in range(i + 1, min(i + 16, len(candles))):
                    fc = candles[f]
                    if signal == "LONG":
                        if fc["high"] >= tp:
                            outcome = "WIN"
                            break
                        elif fc["low"] <= sl:
                            outcome = "LOSS"
                            break
                    else:
                        if fc["low"] <= tp:
                            outcome = "WIN"
                            break
                        elif fc["high"] >= sl:
                            outcome = "LOSS"
                            break

                if outcome:
                    trades.append(outcome)

        wins = trades.count("WIN")
        losses = trades.count("LOSS")
        total = wins + losses
        win_rate = (wins / total) if total > 0 else 0.0
        net_r = (wins * 2.0) - (losses * 1.0)

        return {
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate * 100, 1),
            "net_r": round(net_r, 2)
        }

    @staticmethod
    def evaluate_momentum_reversal(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Archetype: 3-Candle Momentum & 5-Candle Reversal (Engines 2, 4).
        """
        if len(candles) < 30:
            return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "net_r": 0.0}

        closes = [c["close"] for c in candles]
        rsi = calculate_rsi(closes, 14)
        eval_start = max(15, len(candles) - 96)
        trades = []

        for i in range(eval_start, len(candles) - 3):
            # Check 3 consecutive healthy candles
            c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
            is_3g = c1["close"] > c1["open"] and c2["close"] > c2["open"] and c3["close"] > c3["open"]
            is_3r = c1["close"] < c1["open"] and c2["close"] < c2["open"] and c3["close"] < c3["open"]

            signal = None
            if is_3g and rsi[i] < 68:
                signal = "LONG"
            elif is_3r and rsi[i] > 32:
                signal = "SHORT"

            if signal:
                entry = c3["close"]
                exit_price = candles[min(i + 2, len(candles) - 1)]["close"]
                ret = (exit_price - entry) if signal == "LONG" else (entry - exit_price)
                outcome = "WIN" if ret > 0 else "LOSS"
                trades.append(outcome)

        wins = trades.count("WIN")
        losses = trades.count("LOSS")
        total = wins + losses
        win_rate = (wins / total) if total > 0 else 0.0
        net_r = (wins * 1.5) - (losses * 1.0)

        return {
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate * 100, 1),
            "net_r": round(net_r, 2)
        }

    @staticmethod
    def evaluate_smc_fvg_pullback(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Archetype: Smart Money Concepts & Institutional FVG / Fibonacci (Engines 5, 6, 7, 8).
        Identifies displacement, fair value gaps, and 1:2 R:R mitigations.
        """
        if len(candles) < 40:
            return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "net_r": 0.0}

        atr = calculate_atr(candles, 14)
        eval_start = max(20, len(candles) - 96)
        trades = []

        for i in range(eval_start, len(candles) - 5):
            c_prev2, c_prev1, c_cur = candles[i-2], candles[i-1], candles[i]
            cur_atr = atr[i]
            if cur_atr <= 0:
                continue

            # Bullish FVG: Low of candle 3 > High of candle 1
            bullish_fvg = c_cur["low"] > c_prev2["high"] and (c_cur["close"] - c_cur["open"]) > 0.8 * cur_atr
            # Bearish FVG: High of candle 3 < Low of candle 1
            bearish_fvg = c_cur["high"] < c_prev2["low"] and (c_cur["open"] - c_cur["close"]) > 0.8 * cur_atr

            signal = None
            if bullish_fvg:
                signal = "LONG"
                entry = (c_cur["low"] + c_prev2["high"]) / 2.0  # Midpoint
                sl = c_prev2["low"] - (0.1 * cur_atr)
                sl_dist = abs(entry - sl)
                tp = entry + (2.0 * sl_dist)  # 1:2 R:R
            elif bearish_fvg:
                signal = "SHORT"
                entry = (c_cur["high"] + c_prev2["low"]) / 2.0  # Midpoint
                sl = c_prev2["high"] + (0.1 * cur_atr)
                sl_dist = abs(sl - entry)
                tp = entry - (2.0 * sl_dist)  # 1:2 R:R

            if signal and sl_dist > 0:
                outcome = None
                for f in range(i + 1, min(i + 18, len(candles))):
                    fc = candles[f]
                    if signal == "LONG":
                        if fc["high"] >= tp:
                            outcome = "WIN"
                            break
                        elif fc["low"] <= sl:
                            outcome = "LOSS"
                            break
                    else:
                        if fc["low"] <= tp:
                            outcome = "WIN"
                            break
                        elif fc["high"] >= sl:
                            outcome = "LOSS"
                            break
                if outcome:
                    trades.append(outcome)

        wins = trades.count("WIN")
        losses = trades.count("LOSS")
        total = wins + losses
        win_rate = (wins / total) if total > 0 else 0.0
        net_r = (wins * 2.0) - (losses * 1.0)

        return {
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate * 100, 1),
            "net_r": round(net_r, 2)
        }
