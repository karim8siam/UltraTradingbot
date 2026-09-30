# Binance USDT-M Futures — Deterministic SMC Automated Trading Bot

A high-performance, strictly deterministic Smart Money Concepts (SMC) trading bot and backtesting engine for Binance USDT-M Futures. Built in Python with zero subjective visual interpretations or AI discretion.

---

## Key Features

1. **Deterministic SMC Engine**:
   - **Top 20 Supported Pairs**: BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK, SUI, NEAR, PEPE, SHIB, APT, LTC, TON, WIF, BCH, FET, TIA.
   - **Swing Detection**: Confirmed swing highs & lows (`SWING_LENGTH=2`, no lookahead).
   - **Market Structure**: 4H major bias & 1H confirmation (`BULLISH` = HH + HL, `BEARISH` = LH + LL).
   - **Liquidity & Sweeps**: Real-time identification of previous swings, Equal Highs/Lows (0.1% tolerance), PDH/PDL with Binance UTC boundaries, and 15M liquidity sweeps.
   - **Displacement & MSS**: 1.5x average body with >=60% body ratio, and 5M candle close breaks past structural levels.
   - **FVG & Midpoint Entry**: 3-candle Fair Value Gap detection and 50% midpoint limit retracement.
   - **Dynamic SL & Target TP**: Dynamic SL at `SweepLow/High ± (0.10 * ATR14)` and opposing target liquidity (`RR >= 2.0`).
   - **Weighted Setup Scoring**: Multi-factor scoring requiring >= 11 points (out of 14).

2. **Capital Preservation & Profit Locking**:
   - **Per-Trade Risk**: Strictly 1% of account equity per trade.
   - **Leverage**: Default 5x leverage with dynamic notional clamping and precision rounding.
   - **Dynamic Breakeven**: Automatically moves Stop Loss to Breakeven (Entry) once price reaches $+1.5R$.
   - **Partial Take-Profit**: Scales out 50% of position at $+2.0R$ to guarantee profits, letting the remaining 50% ride to the opposing structural liquidity target.
   - **Fee Drag Protection**: Rejects micro-stop distances ($< 0.20\%$).
   - **2% Max Daily Loss** hard kill switch.
   - **3 Consecutive Losses** -> 4-hour automatic cooldown.
   - Max 5 trades per UTC day across all symbols.
   - Max 3 simultaneous open positions & strictly 1 position per symbol.
   - Zero Martingale / Zero averaging down / Zero grid recovery.

3. **Execution Safety & Failsafe Protection**:
   - **Dry-Run & Paper Trading**: Full simulation with real data and zero financial risk.
   - **Testnet & Live Safety Gate**: Triple-lock protection (`BINANCE_TESTNET=false`, `LIVE_TRADING=true`, `LIVE_TRADING_CONFIRMATION=true`).
   - **Post-Fill Protection**: Immediate protective SL and TP orders placed upon fill. If protective SL placement fails after 3 retries, the position is immediately closed via market order.

4. **Multi-Timeframe Backtesting Engine**:
   - Event-driven backtester with fee, funding rate, and slippage simulation.
   - 60% Development / 20% Validation / 20% Out-Of-Sample split tester.
   - Metrics: Win Rate, Expectancy (Gross/Net), Profit Factor, Max Drawdown, Long vs Short win rates, etc.

5. **Terminal Dashboard & SQLite Persistence**:
   - Live multi-symbol status table (4H/1H bias, state transitions, open positions).
   - Full trade lifecycle logging and rejection reason tracking (`REJECTED_LOW_RR`, `REJECTED_LOW_SCORE`, etc.).

---

## Directory Structure

```
smc_futures_bot/
├── config.py                 # Configuration & parameters
├── database.py               # SQLite database & trade logging
├── main.py                   # Main CLI entrypoint
├── requirements.txt          # Dependencies (optional)
├── market_data/
│   ├── binance_client.py     # Async REST API client with precision & symbol filters
│   ├── candle_manager.py     # Multi-timeframe buffer with integrity validator
│   └── historical_fetcher.py # Historical OHLCV downloader
├── strategy/
│   ├── models.py             # Dataclasses (Candle, SwingPoint, Setup, Trade, etc.)
│   ├── swing_detector.py     # Deterministic swing high/low detector
│   ├── market_structure.py   # 4H/1H bias & premium/discount range
│   ├── liquidity.py          # Buy-side/Sell-side, Equal Highs/Lows, PDH/PDL
│   ├── sweep_detector.py     # 15M liquidity sweep detector
│   ├── displacement.py       # Candle body displacement detector
│   ├── mss_detector.py       # 5M Market Structure Shift detector
│   ├── fvg_detector.py       # 3-candle Fair Value Gap & midpoint
│   ├── setup_evaluator.py    # Scoring (>=11), ATR volatility filter, UTC sessions
│   └── state_machine.py      # 15-state per-symbol state machine
├── execution/
│   ├── risk_manager.py       # 1% sizing, daily limits, cooldowns
│   ├── order_manager.py      # Precision rounding & unique client order IDs
│   ├── position_guard.py     # Protective SL/TP & emergency market close
│   └── executor.py           # Unified execution coordinator
├── backtesting/
│   ├── engine.py             # Event-driven backtester
│   ├── metrics.py            # Performance analytics
│   └── split_tester.py       # 60/20/20 Dev/Validation/OOS runner
├── ui/
│   └── dashboard.py          # Live console dashboard
└── tests/
    ├── test_smc_bot.py       # Unit tests
    ├── test_full_smc_lifecycle.py # Full SMC setup lifecycle integration test
    └── simulate_market.py    # Multi-timeframe backtest simulation
```

---

## How to Run

### 1. Run Unit Tests
```bash
python3 -m unittest discover tests
```

### 2. Dry-Run Mode (Safe Live Simulation)
```bash
python3 main.py --mode dry-run
```

### 3. Paper Trading Mode
```bash
python3 main.py --mode paper
```

### 4. Backtesting on Historical Data
```bash
python3 main.py --mode backtest --symbol BTCUSDT
```

### 5. Out-of-Sample 60/20/20 Split Testing
```bash
python3 main.py --mode split-test --symbol BTCUSDT
```

### 6. Binance Futures Testnet Mode
```bash
export BINANCE_API_KEY="your_testnet_key"
export BINANCE_API_SECRET="your_testnet_secret"
export BINANCE_TESTNET=true
python3 main.py --mode testnet
```
