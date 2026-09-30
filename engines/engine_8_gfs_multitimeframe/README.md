# Binance Futures GFS Trading Bot (1D → 4H → 15M)

A production-grade, mathematically deterministic algorithmic trading bot for **Binance USDT-M Futures** built on the **Grandfather-Father-Son (GFS)** multi-timeframe strategy across 10 major cryptocurrency pairs.

---

## Strategy Hierarchy & Logic

```
1D (Grandfather)   --> Determines Macro Market Trend (EMA50 vs EMA200 & Slope)
      ↓
4H (Father)        --> Confirms Medium-Term Trend (EMA20 vs EMA50) & Identifies Pullback Zone
      ↓
15M (Son)          --> Detects Market Structure Shift (MSS) with Momentum Displacement
      ↓
ENTRY & BRACKET    --> 50% Retracement Limit Entry, Structural SL with ATR Buffer, 4H Swing TP (RR >= 2.0)
```

---

## Mathematical Formulations

### 1. Grandfather (1D) Trend
- **Bullish**: $\text{EMA}_{50} > \text{EMA}_{200} \land \text{Close}_{1D} > \text{EMA}_{50} \land \text{Slope}(\text{EMA}_{50}) > 0$
- **Bearish**: $\text{EMA}_{50} < \text{EMA}_{200} \land \text{Close}_{1D} < \text{EMA}_{50} \land \text{Slope}(\text{EMA}_{50}) < 0$
- **Neutral**: Otherwise (No new trades permitted).

### 2. Father (4H) Trend & Pullback Zone
- **Bullish 4H**: $\text{EMA}_{20} > \text{EMA}_{50} \land \text{Close}_{4H} > \text{EMA}_{20} \land \text{Slope}(\text{EMA}_{20}) > 0$
- **Bearish 4H**: $\text{EMA}_{20} < \text{EMA}_{50} \land \text{Close}_{4H} < \text{EMA}_{20} \land \text{Slope}(\text{EMA}_{20}) < 0$
- **Pullback Zone**: Price trades between $\text{EMA}_{20}$ and $\text{EMA}_{50}$ without closing beyond $\text{EMA}_{50}$.

### 3. Son (15M) Market Structure Shift & Displacement
- **Swing Detection** ($\text{Length} = 2$):
  - Swing High: $\text{High}_i > \text{High}_{i-1}, \text{High}_{i-2}, \text{High}_{i+1}, \text{High}_{i+2}$
  - Swing Low: $\text{Low}_i < \text{Low}_{i-1}, \text{Low}_{i-2}, \text{Low}_{i+1}, \text{Low}_{i+2}$
- **Displacement Filter**:
  - $\text{Candle Body} \ge 1.25 \times \text{AverageBody}_{10}$
  - $\text{Body} / \text{Range} \ge 0.55$

### 4. Entry, SL, TP, and Risk Sizing
- **Planned Entry**: $50\%$ retracement of 15M confirmation candle.
- **Stop Loss**:
  - Long: $\text{PullbackLow} - (0.10 \times \text{ATR}_{14})$
  - Short: $\text{PullbackHigh} + (0.10 \times \text{ATR}_{14})$
- **Take Profit**: Previous significant 4H structural swing target where $\text{RR} = \frac{|\text{TP} - \text{Entry}|}{|\text{Entry} - \text{SL}|} \ge 2.0$.
- **Position Sizing**:
  $$\text{PositionSize} = \frac{\text{AccountEquity} \times 0.01}{|\text{Entry} - \text{SL}|}$$
  (Quantized to exchange `stepSize` and `minQty`).

---

## Risk Management Rules

- **Risk Per Trade**: Fixed $1\%$ of account equity per trade.
- **Max Daily Loss**: $2\%$ (halts new trades until next UTC day 00:00).
- **Consecutive Loss Limiter**: $3$ consecutive losses triggers a $4$-hour cooldown.
- **Max Daily Trades**: $5$ trades/day.
- **Max Open Positions**: $3$ simultaneous positions across all pairs.
- **One Position Per Symbol**: No pyramiding, no averaging down.
- **Failsafe**: If Stop Loss order placement fails upon fill, the position is immediately market-closed.

---

## Project Structure

```
binance_gfs_bot/
├── config.py             # Strategy parameters, risk thresholds, API configurations
├── indicators.py         # Pure mathematical indicators (EMA, ATR, Swings, Displacement)
├── gfs_strategy.py       # Multi-timeframe GFS evaluator and setup scoring engine
├── risk_manager.py       # Position sizing, daily loss limits, cooldowns, filters
├── state_machine.py      # Symbol lifecycle state machine
├── database.py           # SQLite persistence for trades, snapshots, rejection logs
├── binance_client.py     # Public & signed Binance Futures REST/WebSocket client
├── order_manager.py      # Entry limit placement, bracket SL/TP, failsafe protection
├── paper_trader.py       # Virtual execution against live market candle stream
├── bot_daemon.py         # Multi-symbol master daemon and CLI dashboard
├── metrics.py            # Quantitative performance analytics (Expectancy, Drawdown, Sharpe)
├── backtester.py         # Zero look-ahead historical simulation engine
├── run_backtest.py       # CLI historical backtest runner (In-sample, Val, OOS)
├── run_bot.py            # Main bot launcher (DRY_RUN, PAPER, TESTNET, LIVE)
└── tests/                # Complete unit test suite (11 test cases)
```

---

## Quickstart & Commands

### 1. Run Unit Tests
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

### 2. Run Historical Backtesting (with 60/20/20 Train/Val/OOS Split)
```bash
python3 run_backtest.py --symbols BTCUSDT ETHUSDT SOLUSDT BNBUSDT XRPUSDT ADAUSDT DOGEUSDT AVAXUSDT LINKUSDT DOTUSDT --split
```

### 3. Launch Paper Trading Daemon
```bash
python3 run_bot.py --mode PAPER --symbols BTCUSDT ETHUSDT SOLUSDT BNBUSDT XRPUSDT
```

### 4. Binance Testnet / Live Trading
```bash
# Testnet
export BINANCE_API_KEY="your_testnet_key"
export BINANCE_API_SECRET="your_testnet_secret"
python3 run_bot.py --mode TESTNET

# Live Trading (Requires confirmation prompt)
python3 run_bot.py --mode LIVE
```
