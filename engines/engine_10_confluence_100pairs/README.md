# 🚀 UltraTradingBot - Engine 10: 100-Pair 10/10 Confluence Futures Engine

An automated, institutional-grade Binance USDT-M Futures trading engine designed to scan **100 Tier-1 cryptocurrency pairs** concurrently with a strict 10/10 technical confluence filter and 1:2 Risk to Reward bracket execution.

---

## 🌟 Architecture & Strategy Rules

1. **Multi-Timeframe Structure:**
   * **Primary Execution:** 5-Minute Candles (`5m`)
   * **Intermediate Structure:** 15-Minute Candles (`15m`)
   * **Macro Trend Sentinel:** 1-Hour Candles (`1h`)

2. **Execution Gate:**
   * Strict **10.0 / 10.0 Points (100% Confluence)** required for order generation.
   * Scans across 100 Binance Futures pairs simultaneously.

3. **Risk & Money Management:**
   * **Risk Per Trade:** 1.0% of portfolio equity
   * **Leverage:** 5x Isolated Margin
   * **Risk/Reward:** Strict **1:2 Risk/Reward Ratio** (`SL = 0.60x ATR`, `TP = 1.20x ATR`)
   * **Server-Side Protection:** Native Binance STOP_MARKET and TAKE_PROFIT_MARKET orders.

---

## ⚡ Quick Start

```bash
cd engines/engine_10_confluence_100pairs
pip install -r requirements.txt
python3 main.py
```
