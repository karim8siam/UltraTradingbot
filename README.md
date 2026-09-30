# UltraTradingBot Suite 🚀

Multi-Strategy Institutional Algorithmic Crypto Suite for 24/7 Uninterrupted Trading.

All engines operate **fully decoupled and isolated** — if one engine encounters network latency, rate limits, or crashes, the remaining engines continue trading without interruption.

---

## 🏗️ Architecture Overview

```
UltraTradingbot/
├── engines/
│   ├── engine_1_multiregime_ml/       # 5M/15M/1H Multi-Regime + ML Ensemble + Gemini AI
│   ├── engine_2_momentum_3candle/     # 15M 3-Candle Momentum & Volume Breakout
│   ├── engine_3_confluence_scalper/   # 10-Point Confluence Scalper (1.55x ATR, 1% Risk, 5x Lev)
│   ├── ...                            # Future Engines (SMC, Fibonacci, FVG, GFS, Swing)
├── screener/                          # Phase 2: 7-Day 60% Win-Rate Scanner (30 coins)
├── docker-compose.yml                 # Master 24/7 Multi-Service Orchestrator
├── .env.example                       # Central credentials & configs
└── README.md
```

---

## ⚡ Active Engines

### 1. Engine 1: Multi-Regime Institutional ML
* **Timeframes:** 5M Execution | 15M Market Structure | 1H BTC Macro Sentinel
* **Strategies:** Trend Pullback, Volatility Breakout, Range Mean-Reversion
* **Intelligence:** Random Forest + XGBoost Meta-Classifier + Google Gemini Quantitative Reasoner
* **Risk & Leverage:** 1% Risk per trade, 1:2 Risk/Reward, 5x Isolated Leverage, Server-Side SL/TP
* **Pairs:** 30 Tier-1 Binance Futures Pairs

### 2. Engine 2: 15M 3-Candle Momentum
* **Timeframe:** 15m
* **Strategy:** 3-Candle continuous directional momentum with body ratio (>50%) & opposite wick filter (<35%)
* **Hold Duration:** Fixed 30-minute hold (2 candles)
* **Risk & Leverage:** 0.1% margin fraction per trade, 5x Isolated Leverage
* **Max Concurrent Trades:** 4
* **Pairs:** Top 25 High-Liquidity USDT-M Futures Pairs

### 3. Engine 3: 10-Point Confluence Scalper
* **Timeframes:** 30m (Recommended) | 15m | 5m
* **Strategy:** 10-Point Confluence Checklist (RVOL, ADX Trend, 1H EMA200 Macro, 24h Session VWAP, EMA 9/21/50 Ribbon, MACD Momentum, RSI Corridor, ATR Expansion, Spread, Engulfing/Pinbar Trigger)
* **Execution Rule:** Minimum Confluence Score >= 8.0 / 10.0 Points
* **Formulas:** 1.55x ATR Stop-Loss & Take-Profit (0.55x ATR discarded due to fee drag)
* **Risk & Leverage:** Strictly <= 1.0% Risk per trade of portfolio equity, 5x Isolated Leverage
* **Max Hold Timeout:** 8 Candles (Auto market close)
* **Pairs:** Top 30 Clean High-Liquidity Crypto USDT Pairs (Stablecoins & Pegged Assets filtered out)

---

## 🚀 Quick Start (Local / VPS)

### Option A: Run with Docker Compose (Recommended for 24/7 Hosting)

```bash
# 1. Clone repository
git clone https://github.com/karim8siam/UltraTradingbot.git
cd UltraTradingbot

# 2. Copy and configure environment variables
cp .env.example .env

# 3. Start all engines in background
docker compose up -d

# 4. View logs for a specific engine
docker compose logs -f engine_1_multiregime_ml
docker compose logs -f engine_2_momentum_3candle

# 5. Stop all engines
docker compose down
```

### Option B: Run an Individual Engine Locally

```bash
# Run Engine 1
cd engines/engine_1_multiregime_ml
pip install -r requirements.txt
python bot.py

# Run Engine 2
cd engines/engine_2_momentum_3candle
pip install -r requirements.txt
python bot.py
```

---

## 🔒 Safety & Risk Protocol
* **Dry-Run Default:** Set `DRY_RUN=true` to test signals and execution without real money.
* **Server-Side Protection:** Stop Loss & Take Profit are mapped natively to Binance matching engines.
* **Decoupled Failure Domains:** Each engine runs in its own process/container with independent memory and state.
