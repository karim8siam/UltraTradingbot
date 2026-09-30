# Binance Futures — Automated Fibonacci Pullback Trading Bot

A deterministic, multi-timeframe Fibonacci Retracement & Trend Pullback trading engine built for Binance USDT-M Futures.

---

## 🚀 Strategy Architecture

1. **Higher-Timeframe Trend Alignment (4H & 1H):**
   - 4H and 1H trends must be non-neutral and in 100% agreement (`BULLISH` or `BEARISH`) using deterministic swing structure (`SWING_LENGTH = 2`).
2. **Impulse Wave Confirmation (15M):**
   - Requires a confirmed 15M impulse leg with magnitude $\ge 2.0 \times \text{ATR}_{14}(15\text{M})$ in the HTF trend direction.
3. **Fibonacci Retracement Zone (5M):**
   - Pullback into the primary 38.2%–61.8% zone (preferred Golden Pocket: 50.0%–61.8%).
   - Invalidation guard at 78.6% (cancels setup if breached).
4. **Structure Shift & Displacement Trigger (5M):**
   - 5M structure shift breaking the local pullback swing with a displacement candle ($\text{Body} \ge 1.5 \times \text{AvgBody}_{10}$ and $\text{Body\%} \ge 60\%$).
5. **Precision Risk Geometry & Sizing:**
   - 50% displacement candle body limit entry.
   - Structural Stop Loss at pullback extreme $\pm 0.10 \times \text{ATR}$.
   - Dynamic Take Profit targeting prior impulse extreme / 1.272 extension ($\text{Reward/Risk} \ge 2.0$).
   - Strict 1.0% account equity risk per trade at 5X leverage.

---

## 📂 Project Structure

```
.
├── config/             # Configuration, default parameters & environment parser
├── core/               # Pure math, indicators, swings, Fibonacci, risk geometry, state machine
├── market_data/        # Binance REST API client & multi-timeframe candle buffers
├── execution/          # Idempotent limit order submission, safety stops & live gates
├── risk/               # Portfolio risk manager (1% risk, limits, cooldowns)
├── storage/            # SQLite trade ledger & setup rejection logger
├── backtest/           # Backtest engine, metric calculator & Fibonacci zone analyzer
├── ui/                 # Live ANSI terminal dashboard
├── tests/              # Comprehensive unit test suite
├── main.py             # Main entrypoint
└── .env.example        # Environment configuration template
```

---

## 🛠️ Quick Start

### 1. Prerequisites
- Python 3.9+
- Binance Futures Account (or Testnet Account)

### 2. Setup Environment
```bash
git clone https://github.com/karim8siam/UltraTradingbot.git
cd UltraTradingbot

# Copy environment template
cp .env.example .env
```

### 3. Run Unit Tests
```bash
python3 -m unittest tests/test_strategy.py -v
```

### 4. Run Backtest
```bash
python3 run_backtest.py
```

### 5. Start in Dry-Run / Paper Trading Mode
```bash
# Single scan (dry-run)
python3 main.py --mode dry-run --once

# Continuous live monitoring (testnet/paper)
python3 main.py --mode dry-run
```

---

## 🔒 Safety & Live Trading

Live trading is **disabled by default**. To activate live trading, both flags in `.env` must be explicitly configured:
```ini
BINANCE_TESTNET=false
LIVE_TRADING=true
LIVE_TRADING_CONFIRMATION=true
DRY_RUN=false
```

---

## 📄 License
MIT License
