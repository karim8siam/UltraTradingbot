# UltraTradingbot — Binance USDT-M Futures FVG Trading Engine

An automated institutional Fair Value Gap (FVG) and Market Structure trading bot for Binance USDT-M Futures with automated risk management, predefined cloud SL/TP, and live background execution.

## 🚀 Key Features

- **Multi-Timeframe Market Structure**:
  - **4H**: Macro bias (Higher Highs / Lower Lows)
  - **1H**: Trend directional filter
  - **15M**: Institutional displacement Fair Value Gap (FVG) identification
  - **5M**: Pullback & Market Structure Shift (MSS) confirmation
- **Strict 1:2 Risk/Reward Ratio**:
  - Stop Loss ($1\text{R}$) placed at pullback structural swing point
  - Take Profit ($2\text{R}$) placed at exact $2\times$ risk distance ($1:2$ RR ratio)
  - Predefined cloud-side orders submitted directly to Binance exchange (`closePosition=True`)
- **Risk Management**:
  - **Risk per Trade**: Maximum 2% equity risk per trade
  - **Fixed Leverage**: 5x leverage
  - **Session Target Exit**: Closes open positions if total unrealized PnL reaches $\ge +2.0\%$
  - **Precision Handling**: Auto-snaps entry, SL, and TP prices to exchange tick and step sizes
- **Watchlist**:
  - Top 30 liquid Binance USDT-M Futures pairs

---

## 📋 30-Pair Watchlist

`BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `XRPUSDT`, `DOGEUSDT`, `ADAUSDT`, `AVAXUSDT`, `LINKUSDT`, `SUIUSDT`, `NEARUSDT`, `APTUSDT`, `LTCUSDT`, `BCHUSDT`, `DOTUSDT`, `POLUSDT`, `ETCUSDT`, `XLMUSDT`, `FILUSDT`, `INJUSDT`, `RENDERUSDT`, `1000PEPEUSDT`, `1000SHIBUSDT`, `1000BONKUSDT`, `1000FLOKIUSDT`, `TIAUSDT`, `SEIUSDT`, `FETUSDT`, `ARBUSDT`, `OPUSDT`.

---

## 🛠️ Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/karim8siam/UltraTradingbot.git
cd UltraTradingbot
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your Binance API credentials:
```bash
cp .env.example .env
```

Edit `.env`:
```ini
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
LIVE_TRADING=true
LIVE_TRADING_CONFIRMATION=true
EMERGENCY_STOP=false
```

### 3. Test Connection
```bash
python3 test_30_coins.py
```

### 4. Start Trading
Run the daemon:
```bash
python3 live_daemon.py
```
Or start in the background:
```bash
bash start_bot.sh
```

---

## 🛡️ Architecture & Components

- `live_daemon.py`: Continuous scanning loop, 24/7 background execution, session PnL monitoring.
- `order_executor.py`: Order submission, cloud SL/TP attachment (`closePosition=True`), and position synchronization.
- `risk_manager.py`: 2% equity risk sizing, Binance minNotional checks, 5x leverage limits.
- `fvg_state_machine.py`: Multi-timeframe FVG state lifecycle tracking.
- `setup_evaluator.py`: Multi-factor setup scoring (4H/1H alignment, FVG quality, RR validation).
- `binance_client.py`: High-performance REST client with endpoint failover, gzip decompression, and server time sync.

---

## ⚠️ Disclaimer
This software is for educational and research purposes. Cryptocurrency futures trading carries substantial financial risk. Use at your own discretion.
