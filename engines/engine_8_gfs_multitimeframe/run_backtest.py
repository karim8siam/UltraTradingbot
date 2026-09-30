"""
CLI Historical Backtesting Runner for Binance Futures GFS Strategy
Runs full in-sample (60%), validation (20%), and out-of-sample (20%) evaluation.
"""

import argparse
import sys
import os
import math
import random
from typing import Dict, List, Any

from config import DEFAULT_SYMBOLS, TIMEFRAME_GRANDFATHER, TIMEFRAME_FATHER, TIMEFRAME_SON
from indicators import Candle
from binance_client import BinanceFuturesClient
from backtester import GFSBacktestEngine
from metrics import PerformanceSummary


def fetch_or_generate_data(client: BinanceFuturesClient, symbols: List[str], limit_15m: int = 5000) -> Dict[str, Dict[str, List[Candle]]]:
    data: Dict[str, Dict[str, List[Candle]]] = {}
    print(f"[DATA] Loading multi-timeframe historical data for {len(symbols)} symbols...")

    for sym in symbols:
        try:
            d_candles = client.fetch_klines(sym, TIMEFRAME_GRANDFATHER, limit=500)
            h4_candles = client.fetch_klines(sym, TIMEFRAME_FATHER, limit=1000)
            m15_candles = client.fetch_klines(sym, TIMEFRAME_SON, limit=limit_15m)

            if len(d_candles) >= 200 and len(h4_candles) >= 100 and len(m15_candles) >= 200:
                data[sym] = {
                    "1d": d_candles,
                    "4h": h4_candles,
                    "15m": m15_candles
                }
                print(f"  [ONLINE] {sym}: 1D={len(d_candles)}, 4H={len(h4_candles)}, 15M={len(m15_candles)}")
                continue
        except Exception:
            pass

        print(f"  [SYNTHETIC] Generating comprehensive multi-timeframe dataset for {sym}...")
        data[sym] = generate_synthetic_data(sym, limit_15m)

    return data


def generate_synthetic_data(symbol: str, limit_15m: int = 5000) -> Dict[str, List[Candle]]:
    random.seed(42 + hash(symbol) % 1000)
    base_price = 50000.0 if "BTC" in symbol else (3000.0 if "ETH" in symbol else 100.0)

    # 1. Generate 300 Daily Candles (Warm up EMA50/200)
    d_candles = []
    curr_d_price = base_price * 0.70
    start_ts_1d = 1640995200000 # 2022-01-01

    for i in range(350):
        # Create steady macro uptrend and cycles
        drift = (base_price * 0.001) if i < 220 else (base_price * 0.0005 * math.sin(i / 15.0))
        vol = base_price * 0.015
        delta = drift + random.gauss(0, 1) * vol
        c_open = curr_d_price
        c_close = max(1.0, c_open + delta)
        c_high = max(c_open, c_close) + abs(random.gauss(0, 1)) * (vol * 0.6)
        c_low = min(c_open, c_close) - abs(random.gauss(0, 1)) * (vol * 0.6)
        ts = start_ts_1d + (i * 86400000)
        d_candles.append(Candle(ts, c_open, c_high, c_low, c_close, random.uniform(1000, 5000), ts + 86400000 - 1))
        curr_d_price = c_close

    # 2. Generate 4H Candles aligned with the daily progression
    h4_candles = []
    curr_h4_price = d_candles[100].open
    start_ts_4h = d_candles[100].timestamp

    for i in range(1200):
        vol = (curr_h4_price * 0.008)
        drift = (curr_h4_price * 0.0004) * (1 if (i % 80 < 55) else -0.7) # Trend + Pullbacks
        delta = drift + random.gauss(0, 1) * vol
        c_open = curr_h4_price
        c_close = max(1.0, c_open + delta)
        c_high = max(c_open, c_close) + abs(random.gauss(0, 1)) * (vol * 0.5)
        c_low = min(c_open, c_close) - abs(random.gauss(0, 1)) * (vol * 0.5)
        ts = start_ts_4h + (i * 14400000)
        h4_candles.append(Candle(ts, c_open, c_high, c_low, c_close, random.uniform(200, 1000), ts + 14400000 - 1))
        curr_h4_price = c_close

    # 3. Generate 15M Candles aligned with the latter 4H period
    m15_candles = []
    curr_15m_price = h4_candles[600].open
    start_ts_15m = h4_candles[600].timestamp

    for i in range(limit_15m):
        vol = (curr_15m_price * 0.003)
        drift = (curr_15m_price * 0.00015) * (1 if (i % 60 < 40) else -0.8)
        delta = drift + random.gauss(0, 1) * vol
        c_open = curr_15m_price
        c_close = max(1.0, c_open + delta)
        c_high = max(c_open, c_close) + abs(random.gauss(0, 1)) * (vol * 0.4)
        c_low = min(c_open, c_close) - abs(random.gauss(0, 1)) * (vol * 0.4)
        ts = start_ts_15m + (i * 900000)
        m15_candles.append(Candle(ts, c_open, c_high, c_low, c_close, random.uniform(50, 300), ts + 900000 - 1))
        curr_15m_price = c_close

    return {"1d": d_candles, "4h": h4_candles, "15m": m15_candles}


def print_performance_table(title: str, summary: PerformanceSummary, rejections: Dict[str, int]):
    print("\n" + "=" * 80)
    print(f"  {title.upper()}")
    print("=" * 80)
    print(f"  Total Completed Trades : {summary.total_trades:<6} | Win Rate (%)       : {summary.win_rate:.2f}%")
    print(f"  Winning Trades         : {summary.winning_trades:<6} | Losing Trades      : {summary.losing_trades:<6}")
    print(f"  Profit Factor          : {summary.profit_factor:<6.2f} | Net Return (%)     : {summary.return_percentage:+.2f}%")
    print(f"  Gross Profit           : ${summary.gross_profit:,.2f} | Gross Loss         : ${summary.gross_loss:,.2f}")
    print(f"  Total Fees             : ${summary.total_fees:,.2f} | Funding Cost       : ${summary.total_funding:,.2f}")
    print(f"  Net PnL                : ${summary.net_pnl:+,.2f} | Average R-Multiple : {summary.average_r_multiple:+.2f}R")
    print(f"  Gross Expectancy       : ${summary.gross_expectancy:,.2f} | Net Expectancy     : ${summary.net_expectancy:,.2f}")
    print(f"  Average Win            : ${summary.average_win:,.2f} | Average Loss       : ${summary.average_loss:,.2f}")
    print(f"  Max Drawdown           : ${summary.max_drawdown_amount:,.2f} | Max Drawdown (%)   : {summary.max_drawdown_pct:.2f}%")
    print(f"  Max Consecutive Wins   : {summary.max_consecutive_wins:<6} | Max Consec Losses  : {summary.max_consecutive_losses:<6}")
    print(f"  Sharpe Ratio (Ann.)    : {summary.sharpe_ratio:<6.2f} | Sortino Ratio      : {summary.sortino_ratio:<6.2f}")
    print("-" * 80)
    print(f"  Long Trades : {summary.long_trades} (Win: {summary.long_win_rate:.1f}%, Net: ${summary.long_net_pnl:+,.2f})")
    print(f"  Short Trades: {summary.short_trades} (Win: {summary.short_win_rate:.1f}%, Net: ${summary.short_net_pnl:+,.2f})")
    print("=" * 80)

    if summary.symbol_breakdown:
        print("  SYMBOL BREAKDOWN:")
        h_sym, h_tr, h_wr, h_pnl, h_r = "SYMBOL", "TRADES", "WIN %", "NET PNL", "AVG R"
        print(f"  {h_sym:<10} | {h_tr:<8} | {h_wr:<8} | {h_pnl:<14} | {h_r:<6}")
        print("  " + "-" * 55)
        for sym, s_data in summary.symbol_breakdown.items():
            t_tr = s_data["total_trades"]
            t_wr = s_data["win_rate"]
            t_pnl = s_data["net_pnl"]
            t_r = s_data["avg_r"]
            print(f"  {sym:<10} | {t_tr:<8} | {t_wr:<7.1f}% | ${t_pnl:<13,.2f} | {t_r:<6.2f}")
        print("=" * 80)

    if rejections:
        top_rejections = sorted(rejections.items(), key=lambda x: x[1], reverse=True)[:6]
        print("  TOP REJECTED SETUP FILTERS:")
        for code, count in top_rejections:
            print(f"    - {code:<32} : {count} times")
        print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Binance Futures GFS Strategy Backtester")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="List of trading pairs")
    parser.add_argument("--equity", type=float, default=10000.0, help="Initial account equity in USD")
    parser.add_argument("--limit", type=int, default=5000, help="Number of 15M candles per symbol")
    parser.add_argument("--split", action="store_true", help="Split data into 60% Dev / 20% Val / 20% Out-of-Sample")
    parser.add_argument("--sessions", action="store_true", help="Enforce UTC trading session filter")
    args = parser.parse_args()

    client = BinanceFuturesClient()
    symbol_data = fetch_or_generate_data(client, args.symbols, limit_15m=args.limit)

    engine = GFSBacktestEngine(initial_equity=args.equity, enforce_sessions=args.sessions)

    if args.split:
        print("[BACKTEST] Running 3-Way Split: Development (60%), Validation (20%), Out-of-Sample (20%)...")
        summary_dev, _, rej_dev = engine.run_backtest(symbol_data, start_ratio=0.0, end_ratio=0.60)
        print_performance_table("In-Sample Development (60%)", summary_dev, rej_dev)

        summary_val, _, rej_val = engine.run_backtest(symbol_data, start_ratio=0.60, end_ratio=0.80)
        print_performance_table("Validation Set (20%)", summary_val, rej_val)

        summary_oos, _, rej_oos = engine.run_backtest(symbol_data, start_ratio=0.80, end_ratio=1.0)
        print_performance_table("Out-of-Sample Test (Final 20%)", summary_oos, rej_oos)
    else:
        print("[BACKTEST] Running Full Historical Backtest...")
        summary_full, _, rej_full = engine.run_backtest(symbol_data, start_ratio=0.0, end_ratio=1.0)
        print_performance_table("Full Historical Backtest", summary_full, rej_full)


if __name__ == "__main__":
    main()
