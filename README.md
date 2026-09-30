# UltraTradingBot 🚀

AI-Powered Binance Futures Trading Engine with Multi-Layer Institutional Intelligence.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              👑 1-Hour Bitcoin Sentinel              │
│         (Macro Trend Authority for All Pairs)       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ 5M Execution│──│15M Structure │──│ ML Ensemble │ │
│  │   Engine    │  │ Order Blocks │  │ RF+XGBoost  │ │
│  └─────────────┘  └──────────────┘  └────────────┘ │
│                         │                           │
│              ┌──────────────────────┐               │
│              │  Gemini AI Reasoner  │               │
│              │  (Final Gate Review) │               │
│              └──────────────────────┘               │
│                         │                           │
│              ┌──────────────────────┐               │
│              │  Binance Execution   │               │
│              │  1% Risk | 1:2 R:R   │               │
│              │  Server-Side SL/TP   │               │
│              └──────────────────────┘               │
└─────────────────────────────────────────────────────┘
```

## Features

- **30 Whitelisted Pairs** — Comprehensive Binance Futures coverage
- **1:2 Risk/Reward Ratio** — Double profit target vs stop loss
- **1% Risk Per Trade** — Strict portfolio risk management
- **5x Isolated Leverage** — Conservative leverage with isolated margin
- **7-Gate Trade Approval Pipeline**:
  1. Technical Confluence Score ≥ 81/100
  2. 15-Minute Macro Trend Alignment
  3. 1-Hour Bitcoin Sovereign Sentinel
  4. 5M Altcoin-BTC Divergence Guard
  5. ML Dual-Ensemble (Random Forest + XGBoost) ≥ 58-62%
  6. Google Gemini AI Quantitative Reasoning ≥ 58-62%
  7. Final Consensus (ALL gates must approve)
- **Server-Side SL/TP** — Native Binance STOP_MARKET & TAKE_PROFIT_MARKET orders for 24/7 offline protection
- **Maker-First Execution** — Post-Only GTX limit orders for 60% fee savings
- **Telegram Alerts** — Real-time trade notifications
- **Google Sheets Sync** — Live portfolio tracking

## Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/karim8siam/UltraTradingbot.git
cd UltraTradingbot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Run
```bash
python bot.py
```

## Configuration

| Parameter | Default | Description |
|---|---|---|
| `DEFAULT_TIMEFRAME` | `5m` | Execution candle timeframe |
| `HIGHER_TIMEFRAME` | `15m` | Institutional structure timeframe |
| `BTC_SENTINEL_TIMEFRAME` | `1h` | Bitcoin macro trend timeframe |
| `RISK_PER_TRADE_PERCENT` | `1.0` | Max risk per trade (% of balance) |
| `DEFAULT_LEVERAGE` | `5` | Isolated leverage multiplier |
| `MAX_OPEN_TRADES` | `30` | Maximum simultaneous positions |
| `PAUSE_NEW_TRADES` | `false` | Emergency pause toggle |

## Risk Management

- **1% Maximum Risk** per trade — hard-capped with assertion guard
- **1:2 Risk/Reward** — Take Profit = 2× Stop Loss distance
- **Server-Side Protection** — SL and TP live on Binance's matching engine 24/7
- **Anti-Whipsaw Cooldown** — 5-minute lockout after stop-out per symbol
- **Losing Streak Halving** — 2 consecutive losses auto-cuts risk to 0.5%
- **10% Drawdown** — Protection mode (risk capped to 0.5%)
- **20% Drawdown** — Emergency halt (complete bot suspension)
- **3% Daily Loss** — Kill switch stops all new entries

## File Structure

```
├── bot.py                    # Main trading loop
├── config.py                 # All configuration & parameters
├── strategy.py               # Technical analysis & signal generation
├── execution.py              # Order execution & position management
├── risk_manager.py           # Position sizing & risk guardrails
├── data_fetcher.py           # OHLCV & balance data from Binance
├── btc_sentinel.py           # 1-Hour Bitcoin macro trend sentinel
├── merge_engine.py           # ML + AI decision fusion
├── gemini_reasoner.py        # Google Gemini AI trade evaluation
├── ml_brain.py               # Random Forest + XGBoost ensemble
├── database.py               # SQLite trade journal
├── telegram_notifier.py      # Telegram alert integration
├── recovery_state_engine.py  # Drawdown recovery state machine
├── .env.example              # Environment template
└── requirements.txt          # Python dependencies
```

## License

Private — All rights reserved.
