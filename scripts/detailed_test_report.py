"""
Detailed 10-Pair Historical Backtest & Trade Analyzer.
Runs bar-by-bar backtest across all 10 symbols over multi-year data,
computes comprehensive per-pair and aggregate metrics, and exports reports.
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from tabulate import tabulate

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DEFAULT_CONFIG
from database.db import Database
from market_data.data_fetcher import DataFetcher
from backtesting.engine import BacktestEngine
from backtesting.metrics import MetricsEngine


def main():
    config = DEFAULT_CONFIG
    symbols = config.SYMBOLS
    db_path = config.DB_PATH
    
    # Remove existing DB for clean historical run
    if os.path.exists(db_path):
        os.remove(db_path)
    db = Database(db_path)
    fetcher = DataFetcher(config)

    print(f"\n================================================================================")
    print(f"  SYSTEMATIC CRYPTO SWING STRATEGY (v1) — 10-PAIR HISTORICAL AUDIT")
    print(f"================================================================================")
    print(f"[+] Loading multi-year historical candles for 10 pairs...")

    symbols_data = {}
    for s in symbols:
        df_1d = fetcher.get_candles(s, "1d", min_candles=1500)
        df_4h = fetcher.get_candles(s, "4h", min_candles=6000)
        df_1h = fetcher.get_candles(s, "1h", min_candles=15000)
        symbols_data[s] = {"1d": df_1d, "4h": df_4h, "1h": df_1h}
        print(f"    - {s:10s}: 1D={len(df_1d):5d} candles | 4H={len(df_4h):5d} candles | 1H={len(df_1h):6d} candles")

    initial_equity = 10000.0
    print(f"\n[+] Executing bar-by-bar deterministic simulation (Starting Equity: ${initial_equity:,.2f})...")
    engine = BacktestEngine(config=config, initial_equity=initial_equity, db=db)
    result = engine.run(symbols_data)

    trades = result.trades
    metrics = result.metrics
    df_trades = pd.DataFrame(trades)

    print(f"\n[+] Backtest Complete. Total Executed Trades: {len(trades)}")

    # 1. Overall Portfolio Metrics Table
    overall_table = [
        ["Initial Equity", f"${initial_equity:,.2f}"],
        ["Final Equity", f"${result.equity_curve[-1]['equity']:,.2f}" if result.equity_curve else f"${initial_equity:,.2f}"],
        ["Total Net PnL", f"${metrics.total_net_pnl:+,.2f} ({((metrics.total_net_pnl / initial_equity) * 100):+.2f}%)"],
        ["Total Trades", f"{metrics.total_trades}"],
        ["Win / Loss / Breakeven", f"{metrics.winning_trades}W / {metrics.losing_trades}L / {metrics.break_even_trades}BE"],
        ["Win Rate", f"{metrics.win_rate:.2f}%"],
        ["Profit Factor", f"{metrics.profit_factor:.2f}"],
        ["Gross Profit", f"${metrics.gross_profit:,.2f}"],
        ["Gross Loss", f"${metrics.gross_loss:,.2f}"],
        ["Total Fees Paid", f"${metrics.total_fees:,.2f}"],
        ["Total Funding Cost", f"${metrics.total_funding:,.2f}"],
        ["Total Slippage Cost", f"${metrics.total_slippage:,.2f}"],
        ["Average Win", f"${metrics.average_win:,.2f}"],
        ["Average Loss", f"${metrics.average_loss:,.2f}"],
        ["Average R-Multiple", f"{metrics.average_r:+.2f} R"],
        ["Trade Expectancy", f"${metrics.expectancy:+,.2f} per trade"],
        ["Maximum Drawdown ($ / %)", f"${metrics.max_drawdown_amount:,.2f} ({metrics.max_drawdown_percent:.2f}%)"],
        ["Max Consecutive Losses", f"{metrics.max_consecutive_losses}"],
        ["Avg / Median / Max Holding Time", f"{metrics.average_holding_hours:.1f}h / {metrics.median_holding_hours:.1f}h / {metrics.max_holding_hours:.1f}h"],
        ["Long Performance", f"{metrics.long_win_rate:.1f}% win rate ({metrics.long_trades_count} trades) | Net PnL: ${metrics.long_net_pnl:+,.2f}"],
        ["Short Performance", f"{metrics.short_win_rate:.1f}% win rate ({metrics.short_trades_count} trades) | Net PnL: ${metrics.short_net_pnl:+,.2f}"]
    ]

    print("\n" + "=" * 80)
    print("PORTFOLIO PERFORMANCE SUMMARY (10 Pairs Combined)")
    print("=" * 80)
    print(tabulate(overall_table, headers=["Metric", "Value"], tablefmt="fancy_grid"))

    # 2. Individual Pair Breakdown Table
    pair_rows = []
    for s in symbols:
        if df_trades.empty or s not in df_trades["symbol"].values:
            pair_rows.append([s, 0, "0.0%", "0 / 0 / 0", "$0.00", "$0.00", "$0.00", "0.00", "$0.00", "0.0h", "$0.00 (0.0%)"])
            continue

        s_df = df_trades[df_trades["symbol"] == s]
        s_total = len(s_df)
        s_win = len(s_df[s_df["net_pnl"] > 0])
        s_loss = len(s_df[s_df["net_pnl"] < 0])
        s_be = len(s_df[s_df["net_pnl"] == 0])
        s_winrate = (s_win / s_total) * 100.0 if s_total > 0 else 0.0

        s_gross_win = float(s_df[s_df["net_pnl"] > 0]["gross_pnl"].sum()) if s_win > 0 else 0.0
        s_gross_loss = abs(float(s_df[s_df["net_pnl"] < 0]["gross_pnl"].sum())) if s_loss > 0 else 0.0
        s_pf = (s_gross_win / s_gross_loss) if s_gross_loss > 0 else (999.0 if s_gross_win > 0 else 0.0)

        s_net_pnl = float(s_df["net_pnl"].sum())
        s_pnl_pct = (s_net_pnl / initial_equity) * 100.0
        s_fees = float(s_df["fees"].sum()) + float(s_df["funding_cost"].sum()) + float(s_df["slippage"].sum())
        s_avg_r = float(s_df["R_multiple"].mean()) if "R_multiple" in s_df.columns else 0.0
        s_avg_hold = float(s_df["holding_hours"].mean()) if "holding_hours" in s_df.columns else 0.0

        pair_rows.append([
            s,
            s_total,
            f"{s_winrate:.1f}%",
            f"{s_win} / {s_loss} / {s_be}",
            f"${s_gross_win:,.2f}",
            f"${s_gross_loss:,.2f}",
            f"${s_fees:,.2f}",
            f"{s_pf:.2f}",
            f"{s_avg_r:+.2f} R",
            f"{s_avg_hold:.1f}h",
            f"${s_net_pnl:+,.2f} ({s_pnl_pct:+.2f}%)"
        ])

    print("\n" + "=" * 80)
    print("INDIVIDUAL TRADING PAIR BREAKDOWN (All 10 Symbols)")
    print("=" * 80)
    print(tabulate(pair_rows, headers=[
        "Symbol", "Trades", "Win Rate", "W / L / BE", "Gross Win", "Gross Loss",
        "Total Costs", "Profit Factor", "Avg R", "Avg Hold", "Net PnL (% Equity)"
    ], tablefmt="fancy_grid"))

    # 3. Recent Trades Audit Log
    if not df_trades.empty:
        print("\n" + "=" * 80)
        print("SAMPLE TRADE AUDIT LOG (Most Recent Trades)")
        print("=" * 80)
        sample_cols = ["timestamp", "symbol", "direction", "entry", "SL", "TP1", "exit_price", "net_pnl", "R_multiple", "result", "exit_reason", "holding_hours"]
        recent_df = df_trades[sample_cols].tail(15)
        print(tabulate(recent_df.values, headers=sample_cols, tablefmt="grid"))


if __name__ == "__main__":
    main()
