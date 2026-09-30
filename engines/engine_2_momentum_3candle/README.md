# 🚀 UltraTradingbot - Engine 2: 15M 5-Candle Reversal Trading Bot

An automated cryptocurrency trading bot designed for **Binance USDT-M Futures**, featuring a 15-minute 5-candle momentum exhaustion reversal strategy, Doji-skipping candle quality filters, dynamic 0.1% money management, and a strict 45-minute (3-candle) time-based exit.

---

## 🌟 Strategy & Core Logic

1. **Market & Timeframe:**
   - **Exchange:** Binance USDT-M Futures (`fapi.binance.com`).
   - **Timeframe:** Strictly **15-Minute Candles (`15m`)**.
   - **Universe (Top 25 High-Win-Rate Pairs):** `LTCUSDT`, `ZKPUSDT`, `ETHUSDT`, `WIFUSDT`, `UNIUSDT`, `ZENUSDT`, `NVDAUSDT`, `ZKUSDT`, `ADAUSDT`, `CRCLUSDT`, `BICOUSDT`, `SOLUSDT`, `XAGUSDT`, `1000PEPEUSDT`, `FETUSDT`, `XAUUSDT`, `ARBUSDT`, `BZUSDT`, `APTUSDT`, `WLFIUSDT`, `TRXUSDT`, `DOGEUSDT`, `1000SHIBUSDT`, `CAKEUSDT`, `HYPEUSDT`.

2. **Entry Rules (5-Candle Exhaustion Reversal):**
   - **SHORT (Sell):** 5 consecutive healthy **Green candles** (Dojis skipped) + **RSI(14) $\ge$ 65.0**.
   - **LONG (Buy):** 5 consecutive healthy **Red candles** (Dojis skipped) + **RSI(14) $\le$ 35.0**.
   - **Doji / Unhealthy Pin Skipping:** Any candle with body $< 30\%$ of total range is skipped to count 5 pure directional candles.

3. **Money Management & Leverage:**
   - **Leverage:** **5x ISOLATED** (providing a safe 20% liquidation buffer).
   - **Position Sizing:** Dynamically allocated at **0.1% (0.001)** of your total live account balance per trade.
   - **Min Notional Floor:** Complies with Binance's minimum order requirement ($5.10 USDT).
   - **Max Concurrency:** Up to **3 open trades** active simultaneously.

4. **Exit Logic (No SL / No TP):**
   - **Time-Based Exit:** Market close after **exactly 45 minutes (3 candles)** from trade entry.
   - **No Price-Based TP/SL:** Purely timeframe-driven reversal capture.
   - **Resilient Retry Loop:** Automatically retries close orders if network latency occurs.

---

## ⚡ Quick Start

### 1. Clone & Configure
```bash
git clone https://github.com/karim8siam/UltraTradingbot.git
cd UltraTradingbot/engines/engine_2_momentum_3candle
cp .env.example .env
```
Edit `.env` with your Binance API Key and Secret:
```env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
DRY_RUN=false
```

### 2. Start the Bot
```bash
python3 bot.py
```
