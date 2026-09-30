# 🚀 UltraTradingBot - Engine 9: Multi-Timeframe Systematic Swing Trading Bot

A deterministic USDT-M Futures swing trading system designed to capture medium-term market swings (days to weeks) across multiple timeframes (1D -> 4H -> 1H).

---

## 🌟 Architecture & Strategy Rules

1. **Multi-Timeframe Structure:**
   * **Daily (1D):** Macro Regime Bias & Trend Baseline (200 EMA + Structure)
   * **4-Hour (4H):** Intermediate Momentum & Swing Point Identification
   * **1-Hour (1H):** Precise Pullback & Confirmation Entry Zone

2. **Risk & Execution Rules:**
   * **Risk Per Trade:** 1.0% of portfolio equity
   * **Leverage:** 3x Isolated Leverage (conservative swing sizing)
   * **Risk/Reward:** Minimum 1:2.5 R:R threshold (`MIN_RR = 2.5`)
   * **Setup Scoring:** Minimum 14 points required for trade entry

3. **Trading Universe:**
   * Top 25 High-Liquidity USDT-M Futures pairs

---

## ⚡ Quick Start

```bash
cd engines/engine_9_futures_swing
pip install -r requirements.txt
python3 main.py --mode dry-run
```
