# UltraTradingBot Suite 🚀

Multi-Strategy Institutional Algorithmic Crypto Suite for 24/7 Uninterrupted Trading.

All engines operate **fully decoupled and isolated** — if one engine encounters network latency, rate limits, or crashes, the remaining engines continue trading without interruption.

---

## 🏗️ Architecture Overview

```text
UltraTradingbot/
├── engines/
│   ├── engine_1_multiregime_ml/       # 5M/15M/1H Multi-Regime + ML Ensemble + Gemini AI
│   ├── engine_2_momentum_3candle/     # 15M 3-Candle Momentum & Volume Breakout
│   ├── engine_3_confluence_scalper/   # 10-Point Confluence Scalper (1.55x ATR, 1% Risk, 5x Lev)
│   ├── engine_4_reversal_5candle/     # 15M 5-Candle Momentum Exhaustion Reversal
│   ├── engine_5_deterministic_smc/    # 4H/1H/15M/5M Smart Money Concepts (FVG + MSS)
│   ├── engine_6_fibonacci_pullback/   # 4H/1H/15M/5M Fibonacci Pullback (Golden Pocket)
│   ├── engine_7_institutional_fvg/    # 4H/1H/15M/5M Institutional FVG (1:2 R:R)
│   ├── engine_8_gfs_multitimeframe/   # 1D/4H/15M Grandfather-Father-Son Trend Engine
│   ├── engine_9_futures_swing/        # 1D/4H/1H Multi-Timeframe Swing Trend Engine
│   └── engine_10_confluence_100pairs/ # 100-Pair 10/10 Confluence Scanner
├── screener/                          # Phase 2: 24-Hour Midnight Screener (50%+ Win-Rate, 1:2 R:R)
├── shared/                            # Real-time dynamic active_pairs.json (Zero-Downtime volume)
├── docker-compose.yml                 # Master 24/7 Multi-Service Orchestrator (11 Services)
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
* **Formulas:** 1.55x ATR Stop-Loss & 3.10x ATR Take-Profit (Strict 1:2 Risk to Reward)
* **Risk & Leverage:** Strictly <= 1.0% Risk per trade of portfolio equity, 5x Isolated Leverage
* **Max Hold Timeout:** 8 Candles (Auto market close)
* **Pairs:** Top 30 Clean High-Liquidity Crypto USDT Pairs (Stablecoins & Pegged Assets filtered out)

### 4. Engine 4: 15M 5-Candle Momentum Exhaustion Reversal
* **Timeframe:** 15m
* **Strategy:** 5 consecutive healthy directional candles (Doji skipping filter) + RSI(14) Overbought (>= 65) / Oversold (<= 35) reversal capture
* **Hold Duration:** Fixed 45-minute time exit (3 candles)
* **Risk & Leverage:** 0.1% margin fraction per trade, 5x Isolated Leverage
* **Max Concurrent Trades:** 3
* **Pairs:** Top 25 Verified High-Win-Rate Futures Pairs

### 5. Engine 5: Deterministic SMC Futures Trading Bot
* **Timeframes:** 4H Macro Bias | 1H Confirmation & Range | 15M Liquidity Sweeps | 5M Displacement, MSS & FVG Midpoint Entry
* **Strategy:** Strictly deterministic Smart Money Concepts (Zero AI/subjective discretion)
  * Confirmed Swings (`SWING_LENGTH=2`, no lookahead)
  * Equal Highs/Lows (0.1% tolerance) & UTC Prev Day High/Low (PDH/PDL)
  * 15M Liquidity Sweep + 5M Candle Close MSS + 5M FVG 50% Midpoint Limit Entry
  * 14-Factor Setup Scoring (Requires Score >= 11/14)
* **Profit-Locking Features:**
  * **Dynamic Breakeven:** Moves Stop Loss to Entry price once trade reaches $+1.5R$.
  * **Partial Take-Profit:** Scales out 50% position at $+2.0R$, letting remainder run to structural target.
  * **Fee Drag Protection:** Filters out micro-stops ($< 0.20\%$).
* **Risk & Leverage:** Strictly **1.0% Risk per trade**, **5x Leverage** with notional clamping, 2% Max Daily Loss kill switch, 3-loss cooldown.
* **Pairs:** **Top 20 Liquid Futures Pairs** (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `DOGEUSDT`, `ADAUSDT`, `AVAXUSDT`, `LINKUSDT`, `SUIUSDT`, `NEARUSDT`, `PEPEUSDT`, `SHIBUSDT`, `APTUSDT`, `LTCUSDT`, `TONUSDT`, `WIFUSDT`, `BCHUSDT`, `FETUSDT`, `TIAUSDT`).

### 6. Engine 6: Deterministic Fibonacci Pullback Trading Bot
* **Timeframes:** 4H Macro Trend | 1H Intermediate Trend | 15M Impulse Move ($\ge 2.0 \times \text{ATR}$) | 5M Confirmation & Entry
* **Strategy:** 100% Deterministic Fibonacci Retracement & Trend Pullback system
  * 4H & 1H multi-timeframe swing alignment (`SWING_LENGTH=2`)
  * 15M confirmed impulse move ($\ge 2.0 \times \text{ATR}_{14}$)
  * 5M Golden Pocket Retracement (38.2%–61.8% zone, 78.6% invalidation guard)
  * 5M structure shift with high-momentum displacement candle ($\text{Body} \ge 1.5 \times \text{AvgBody}_{10}$ and $\text{Body\%} \ge 60\%$)
  * 16-Factor Setup Scorer ($\ge 11/16$ threshold)
* **Risk & Leverage:** Strictly **1.0% Risk per trade**, **5X Isolated Leverage**, uncapped daily loss, structural SL + ATR buffer, dynamic TP with $\text{RR} \ge 2.0$.
* **Pairs:** **Top 30 Liquid Binance USDT-M Futures Pairs** (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `DOGEUSDT`, `ADAUSDT`, `SUIUSDT`, `AVAXUSDT`, `LINKUSDT`, `TRXUSDT`, `NEARUSDT`, `PEPEUSDT`, `ENAUSDT`, `SHIBUSDT`, `LTCUSDT`, `BCHUSDT`, `DOTUSDT`, `UNIUSDT`, `APTUSDT`, `WLDUSDT`, `TAOUSDT`, `FETUSDT`, `RENDERUSDT`, `OPUSDT`, `ARBUSDT`, `FILUSDT`, `INJUSDT`, `AAVEUSDT`, `CRVUSDT`).

### 7. Engine 7: Institutional Fair Value Gap (FVG) Trading Engine
* **Timeframes:** 4H Macro Bias | 1H Intermediate Trend | 15M FVG Displacement | 5M Pullback & Market Structure Shift (MSS)
* **Strategy:** Institutional Smart Money Concept (SMC) Fair Value Gap system
  * 4H & 1H multi-timeframe swing bias alignment (`SWING_LENGTH=2`)
  * 15M Fair Value Gap identification with high-velocity displacement body ($> 1.5\times\text{ATR}$, $> 60\%$ candle body)
  * 5M pullback to FVG midpoint (discount zone for Longs, premium zone for Shorts)
  * 5M structure shift confirmation before execution
* **Risk & Leverage:** Strictly **2.0% Maximum Risk per trade**, **5x Fixed Leverage**, exact **1:2 Risk/Reward Ratio** (Loss \$1 $\rightarrow$ Win \$2)
* **Session Exit:** Global **+2.0% Total Account PnL Exit** (closes open positions when total unrealized profit $\ge 2\%$)
* **Execution & Protection:** Immediate market entry upon confirmation, predefined server-side cloud SL/TP orders on Binance (`closePosition=True`)
* **Pairs:** **Top 30 Liquid Binance USDT-M Futures Pairs** (`BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `XRPUSDT`, `DOGEUSDT`, `ADAUSDT`, `AVAXUSDT`, `LINKUSDT`, `SUIUSDT`, `NEARUSDT`, `APTUSDT`, `LTCUSDT`, `BCHUSDT`, `DOTUSDT`, `POLUSDT`, `ETCUSDT`, `XLMUSDT`, `FILUSDT`, `INJUSDT`, `RENDERUSDT`, `1000PEPEUSDT`, `1000SHIBUSDT`, `1000BONKUSDT`, `1000FLOKIUSDT`, `TIAUSDT`, `SEIUSDT`, `FETUSDT`, `ARBUSDT`, `OPUSDT`).

### 8. Engine 8: Grandfather-Father-Son (GFS) Multi-Timeframe Trend Engine
* **Timeframes:** 1D Macro Trend (Grandfather: EMA50/200) | 4H Pullback Zone (Father: EMA20/50) | 15M Market Structure Shift & Displacement (Son)
* **Strategy:** Multi-Timeframe Trend Alignment & Pullback System
  * 1D Grandfather Trend: EMA50 > EMA200 + Positive Slope for Longs (vice-versa for Shorts)
  * 4H Father Pullback Zone: Price retracts into the EMA20–EMA50 value area
  * 15M Son Execution: Market Structure Shift (MSS) with verified displacement candle
  * 14-Factor Quantitative Setup Scorer (Requires Score >= 11)
* **Risk & Leverage:** Strictly **2.0% Maximum Risk**, **5x Isolated Leverage**, **Strict 1:2 Risk/Reward Ratio** (Loss \$1 $\rightarrow$ Win \$2)
* **Exit Target:** **+2.0% Account Equity Take Profit**, **-1.0% Account Equity Stop Loss**
* **Trade Constraints:** **Max 1 Concurrent Trade**, uncapped daily trade count
* **Execution & Protection:** Immediate market entry with native Binance Futures bracket orders (`TAKE_PROFIT_MARKET` & `STOP_MARKET`, `reduceOnly=True`) and OCO residual clean-up
* **Pairs:** **Top 30 Liquid Binance USDT-M Futures Pairs** (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `DOGEUSDT`, `ADAUSDT`, `AVAXUSDT`, `LINKUSDT`, `SUIUSDT`, `NEARUSDT`, `APTUSDT`, `LTCUSDT`, `BCHUSDT`, `DOTUSDT`, `POLUSDT`, `ETCUSDT`, `XLMUSDT`, `FILUSDT`, `INJUSDT`, `RENDERUSDT`, `1000PEPEUSDT`, `1000SHIBUSDT`, `1000BONKUSDT`, `1000FLOKIUSDT`, `TIAUSDT`, `SEIUSDT`, `FETUSDT`, `ARBUSDT`, `OPUSDT`).

### 9. Engine 9: Multi-Timeframe Systematic Swing Trading Engine
* **Timeframes:** 1D Macro Regime Bias (200 EMA + Structure) | 4H Intermediate Momentum & Swing Points | 1H Pullback & Confirmation Entry
* **Strategy:** Zero-Lookahead Multi-Timeframe Swing Trend Engine
  * Daily Trend Directional Baseline filter
  * 4H Swing High / Swing Low Structural Break detection
  * 1H Momentum Confirmation with ATR-based dynamic stop loss
  * Minimum Setup Scorer (>= 14 points required)
* **Risk & Leverage:** Strictly **1.0% Risk per trade**, **3x Isolated Leverage** (conservative swing sizing), **>= 1:2.5 Risk/Reward Ratio**
* **Pairs:** Top 25 High-Liquidity Binance USDT-M Futures Pairs (`BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `XRPUSDT`, `ADAUSDT`, `DOGEUSDT`, `AVAXUSDT`, `LINKUSDT`, `DOTUSDT`, `NEARUSDT`, `SUIUSDT`, `APTUSDT`, `OPUSDT`, `ARBUSDT`, `ATOMUSDT`, `LTCUSDT`, `BCHUSDT`, `ETCUSDT`, `FILUSDT`, `ICPUSDT`, `INJUSDT`, `TIAUSDT`, `RENDERUSDT`, `UNIUSDT`).

### 10. Engine 10: 100-Pair 10/10 Confluence Futures Engine
* **Timeframes:** 5M Primary Execution | 15M Intermediate Structure | 1H Macro Trend Sentinel
* **Strategy:** High-Throughput 100-Pair 10/10 Confluence Scanner
  * Multi-Timeframe Trend Alignment & Momentum Checklist
  * Strict 10.0 / 10.0 Points (100% Confluence) Entry Trigger
  * 15-second high-speed cycle scanning across 100 Binance Futures pairs
* **Risk & Leverage:** Strictly **1.0% Risk per trade**, **5x Isolated Leverage**, **1:2 Risk/Reward Ratio** (`SL = 0.60x ATR`, `TP = 1.20x ATR`)
* **Pairs:** **Top 100 High-Liquidity Binance USDT-M Futures Pairs**.




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
docker compose logs -f engine_6_fibonacci_pullback

# 5. Stop all engines
docker compose down
```

### Option B: Run an Individual Engine Locally

```bash
# Run Engine 6 (Deterministic Fibonacci Pullback)
cd engines/engine_6_fibonacci_pullback
python3 main.py --mode dry-run --once

# Run Engine 5 (Deterministic SMC)
cd engines/engine_5_deterministic_smc
python3 main.py --mode dry-run

# Run Engine 1 (Multi-Regime ML)
cd engines/engine_1_multiregime_ml
python3 bot.py
```

---

## 🔒 Safety & Risk Protocol
* **Dry-Run Default:** Set `DRY_RUN=true` to test signals and execution without real money.
* **Server-Side Protection:** Stop Loss & Take Profit are mapped natively to Binance matching engines.
* **Decoupled Failure Domains:** Each engine runs in its own process/container with independent memory and state.

## Configuration

| Parameter | Default | Description |
|---|---|---|
| `DEFAULT_TIMEFRAME` | `5m` | Execution candle timeframe |
| `HIGHER_TIMEFRAME` | `15m` | Institutional structure timeframe |
| `BTC_SENTINEL_TIMEFRAME` | `1h` | Bitcoin macro trend timeframe |
| `RISK_PER_TRADE_PERCENT` | `0.1` | Max amount (margin) per trade (% of balance) |
| `MARGIN_FRACTION` | `0.001` | 0.1% maximum balance allocation per trade |
| `DEFAULT_LEVERAGE` | `5` | Isolated leverage multiplier |
| `MAX_OPEN_TRADES` | `30` | Maximum simultaneous positions |
| `PAUSE_NEW_TRADES` | `false` | Emergency pause toggle |

## Risk Management

- **0.1% Maximum Amount (Margin)** per trade with **5x Leverage** (e.g. $1,000 USDT balance uses 0.1% = $1.00 margin, yielding $5.00 notional)
- **1:2 Risk/Reward** — Take Profit = 2× Stop Loss distance (1.5x / 3.0x ATR)
- **Server-Side Protection** — SL and TP live on Binance's matching engine 24/7
- **Anti-Whipsaw Cooldown** — 5-minute lockout after stop-out per symbol
- **Losing Streak Halving** — 2 consecutive losses auto-cuts risk to 0.05%
- **10% Drawdown** — Protection mode (risk capped to 0.05%)
- **20% Drawdown** — Emergency halt (complete bot suspension)
- **3% Daily Loss** — Kill switch stops all new entries

## License

Private — All rights reserved.
