# Engine 3: 10-Point Confluence Scalper 🎯

Institutional 10-point confluence scoring scalper with strict 1% risk per trade, 5x isolated leverage, and multi-indicator confirmation across the Top 30 clean crypto USDT pairs.

---

## ⚡ Key Rules & Parameters

* **Universe**: Top 30 High-Liquidity USDT Pairs (excluding stablecoins & pegged tokens).
* **Execution Timeframes**: 30m (Recommended) | 15m | 5m.
* **Risk per Trade**: Max **1.0%** of total portfolio equity.
* **Leverage**: **5x Isolated Leverage** (dynamically sized based on ATR Stop-Loss distance).
* **Confluence Threshold**: Score $\ge$ **8.0 out of 10.0 Points** ($\ge 80\%$ confluence) required for entry.
* **Position Formulas**:
  * **Long Position**:
    $$\text{Take-Profit} = \text{Entry} + (1.55 \times \text{ATR})$$
    $$\text{Stop-Loss} = \text{Entry} - (1.55 \times \text{ATR})$$
  * **Short Position**:
    $$\text{Take-Profit} = \text{Entry} - (1.55 \times \text{ATR})$$
    $$\text{Stop-Loss} = \text{Entry} + (1.55 \times \text{ATR})$$
  *(Note: 0.55x ATR setup was discarded due to fee friction).*
* **Max Hold Timeout**: Auto market close at 8 candles if neither TP nor SL is hit.

---

## 📋 The 10-Point Scoring Checklist

| # | Condition | Long Engine Rule (1.0 Pt) | Short Engine Rule (1.0 Pt) |
|---|---|---|---|
| **1** | **RVOL Expansion** | Current Volume / 20-period Volume SMA $\ge 1.8$ | Current Volume / 20-period Volume SMA $\ge 1.8$ |
| **2** | **Trend Strength** | ADX(14) $\ge 25$ **AND** $+DI > -DI$ | ADX(14) $\ge 25$ **AND** $-DI > +DI$ |
| **3** | **Macro Alignment** | Price > 1-Hour EMA(200) | Price < 1-Hour EMA(200) |
| **4** | **VWAP Level** | Close Price > Session 24h VWAP | Close Price < Session 24h VWAP |
| **5** | **Ribbon Alignment** | $\text{EMA}(9) > \text{EMA}(21) > \text{EMA}(50)$ | $\text{EMA}(9) < \text{EMA}(21) < \text{EMA}(50)$ |
| **6** | **MACD Momentum** | $\text{MACD} > \text{Signal}$ & $\text{Hist} > 0$ (Expanding) | $\text{MACD} < \text{Signal}$ & $\text{Hist} < 0$ (Falling) |
| **7** | **RSI Corridor** | $52 \le \text{RSI}(14) \le 68$ | $32 \le \text{RSI}(14) \le 48$ |
| **8** | **ATR Expansion** | Current $\text{ATR}(14) > \text{SMA}(\text{ATR}, 20)$ | Current $\text{ATR}(14) > \text{SMA}(\text{ATR}, 20)$ |
| **9** | **Orderbook Spread** | $(\text{Ask} - \text{Bid}) / \text{Bid} \le 0.0003$ | $(\text{Ask} - \text{Bid}) / \text{Bid} \le 0.0003$ |
| **10** | **Trigger Candle** | Bullish Engulfing **OR** Pinbar in top 25% | Bearish Engulfing **OR** Pinbar in bottom 25% |

---

## 🚀 Quick Usage

### 1. Instant Market Scanner
Scan the Top 30 pairs right now to view active scores and setups:
```bash
python quick_scan.py
```

### 2. Historical Backtester
Run backtests with custom timeframes and multipliers:
```bash
# Default 30m backtest
python backtester.py --timeframe 30m

# 15m backtest
python backtester.py --timeframe 15m

# Asymmetric R:R (SL 1.0 ATR, TP 1.8 ATR)
python backtester.py --timeframe 30m --sl_mult 1.0 --tp_mult 1.8
```

### 3. Start 24/7 Trading Bot
```bash
# Paper trading (default)
python bot.py

# Live trading: Set DRY_RUN=false in .env with your Binance API keys
python bot.py
```
