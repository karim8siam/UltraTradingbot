# UltraTradingbot - Binance Futures 15M 3-Candle Momentum Trading Bot

An automated cryptocurrency trading bot designed for **Binance USDT-M Futures**, featuring a 15-minute 3-candle momentum price action strategy, dynamic money management, and a strict 30-minute time-based exit.

---

## 🚀 Strategy & Core Logic

1. **Market & Timeframe:**
   - **Exchange:** Binance USDT-M Futures (`fapi.binance.com`).
   - **Timeframe:** Strictly **15-Minute Candles (`15m`)**.
   - **Pairs (Top 25):** `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `DOGEUSDT`, `ADAUSDT`, `TRXUSDT`, `AVAXUSDT`, `LINKUSDT`, `SUIUSDT`, `NEARUSDT`, `APTUSDT`, `DOTUSDT`, `LTCUSDT`, `BCHUSDT`, `PEPEUSDT`, `SHIBUSDT`, `UNIUSDT`, `FETUSDT`, `TAOUSDT`, `OPUSDT`, `ARBUSDT`, `INJUSDT`, `TIAUSDT`.

2. **Entry Rules:**
   - **LONG (Buy):** 3 consecutive completed **Green candles** (none is a Doji), preceded by a non-green candle (fresh sequence only).
   - **SHORT (Sell):** 3 consecutive completed **Red candles** (none is a Doji), preceded by a non-red candle (fresh sequence only).
   - **4th/5th Candle Filter:** Rejects extended sequences (4th, 5th, 6th candles) to prevent entering overextended trends.
   - **Doji Filter:** Automatically filters out flat/zero-body Doji candles.

3. **Money Management & Leverage:**
   - **Leverage:** **5x** (Configured on all pairs in **ISOLATED** margin mode).
   - **Position Sizing:** Dynamically allocated at **0.1% (0.001)** of your total live account balance per trade.
   - **Min Notional Floor:** Complies with Binance's minimum order requirement ($5.10 USDT).
   - **Max Concurrency:** Up to **4 open trades** active simultaneously.

4. **Exit Logic:**
   - **Time-Based Exit:** Market close after **exactly 30 minutes (2 candles)** from trade entry.
   - **No Price-Based TP/SL:** Purely timeframe-driven momentum capture.
   - **Resilient Retry Loop:** Automatically retries close orders if network latency or API rate limits occur until confirmed by Binance.

---

## 📁 Project Structure

```
binance_bot/
├── .env.example          # Environment variables template
├── config.py             # Strategy parameters, symbols, sizing, leverage
├── binance_client.py     # Binance USDT-M Futures REST API client (with auto clock sync)
├── strategy.py           # 3-Candle momentum detection & Doji filtering logic
├── risk_manager.py       # Dynamic position sizing & concurrency limit manager
├── bot.py                # Main live monitoring & 30-min auto-exit engine
├── test_strategy.py      # Unit test suite
├── start_bot.sh          # Quick start script
├── install_service.sh    # macOS background LaunchAgent installer
└── stop_service.sh       # macOS background service stopper
```

---

## ⚡ Quick Start

### 1. Clone & Configure
```bash
git clone https://github.com/karim8siam/UltraTradingbot.git
cd UltraTradingbot
cp .env.example .env
```
Edit `.env` with your Binance API Key and Secret:
```env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
DRY_RUN=false
```

### 2. Run Unit Tests
```bash
python3 test_strategy.py
```

### 3. Start the Bot
```bash
python3 bot.py
```

---

## 🔒 Security Notice
- Keep your API Keys in `.env` and never commit them to version control.
- Ensure **Withdrawals are DISABLED** on your Binance API Key settings.
