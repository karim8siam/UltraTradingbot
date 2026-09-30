"""
Dedicated Backtesting CLI & Report Generator
Executes Sections 56-62 Specification
"""

import argparse
import sys
import os
from backtest.dataset import HistoricalDataset
from backtest.engine import BacktestEngine
from backtest.zone_analysis import FibZoneAnalyzer
from backtest.metrics import MetricsCalculator
from config.constants import DEFAULT_SYMBOLS


def run_backtest_suite(symbols=None, num_candles_5m=6000, split=True):
    symbols = symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    print("=" * 80)
    print("   BINANCE FUTURES -- FIBONACCI PULLBACK STRATEGY BACKTEST (VERSION 1)")
    print("=" * 80)
    print("Target Symbols:", symbols)
    print("Historical 5M Candles per Symbol:", num_candles_5m)
    print("Data Partitioning (60% Dev / 20% Val / 20% Out-of-Sample):", split)

    all_trades = []

    for sym in symbols:
        print("[Backtest] Generating & processing data for " + sym + "...")
        ds = HistoricalDataset.generate_synthetic_data(symbol=sym, num_5m_candles=num_candles_5m, seed=abs(hash(sym)) % 10000)

        if split:
            train_set, val_set, oos_set = ds.partition_data()
            print("  -> Running Development Split (60%)...")
            engine_train = BacktestEngine(initial_capital=10000.0)
            metrics_train = engine_train.run(train_set)

            print("  -> Running Validation Split (20%)...")
            engine_val = BacktestEngine(initial_capital=10000.0)
            metrics_val = engine_val.run(val_set)

            print("  -> Running Out-of-Sample Split (20% - Unseen)...")
            engine_oos = BacktestEngine(initial_capital=10000.0)
            metrics_oos = engine_oos.run(oos_set)

            all_trades.extend(engine_train.closed_trades + engine_val.closed_trades + engine_oos.closed_trades)
            print(f"\n  --- {sym} Partition Results ---")
            wr_tr = round(metrics_train.win_rate * 100, 1)
            wr_va = round(metrics_val.win_rate * 100, 1)
            wr_oo = round(metrics_oos.win_rate * 100, 1)
            pnl_tr = format(metrics_train.net_pnl, "+,.2f")
            pnl_va = format(metrics_val.net_pnl, "+,.2f")
            pnl_oo = format(metrics_oos.net_pnl, "+,.2f")
            print("  Dev (60%):   Trades=" + str(metrics_train.total_trades) + " | WinRate=" + str(wr_tr) + "% | NetPnL=" + pnl_tr + " | PF=" + str(round(metrics_train.profit_factor, 2)))
            print("  Val (20%):   Trades=" + str(metrics_val.total_trades) + " | WinRate=" + str(wr_va) + "% | NetPnL=" + pnl_va + " | PF=" + str(round(metrics_val.profit_factor, 2)))
            print("  OOS (20%):   Trades=" + str(metrics_oos.total_trades) + " | WinRate=" + str(wr_oo) + "% | NetPnL=" + pnl_oo + " | PF=" + str(round(metrics_oos.profit_factor, 2)))
        else:
            engine = BacktestEngine(initial_capital=10000.0)
            metrics = engine.run(ds)
            all_trades.extend(engine.closed_trades)
            wr = round(metrics.win_rate * 100, 1)
            pnl = format(metrics.net_pnl, "+,.2f")
            print("  Trades=" + str(metrics.total_trades) + " | WinRate=" + str(wr) + "% | NetPnL=" + pnl + " | PF=" + str(round(metrics.profit_factor, 2)))

    agg_metrics = MetricsCalculator.calculate(all_trades, initial_capital=10000.0)
    print("\n" + "=" * 80)
    print("                     STRATEGY PERFORMANCE SUMMARY                     ")
    print("=" * 80)
    print("  Total Completed Trades:      " + str(agg_metrics.total_trades))
    print("  Winning Trades:              " + str(agg_metrics.winning_trades) + " (" + str(round(agg_metrics.win_rate * 100, 2)) + "%)")
    print("  Losing Trades:               " + str(agg_metrics.losing_trades) + " (" + str(round(agg_metrics.loss_rate * 100, 2)) + "%)")
    print("  Profit Factor:               " + str(round(agg_metrics.profit_factor, 2)))
    print("  Average Win:                 $" + format(agg_metrics.average_win, ",.2f"))
    print("  Average Loss:                $" + format(agg_metrics.average_loss, ",.2f"))
    print("  Average R-Multiple:          " + str(round(agg_metrics.average_r, 2)) + "R")
    print("  Gross Expectancy:            $" + format(agg_metrics.gross_expectancy, "+,.2f") + " / trade")
    print("  Net Expectancy (after fees): $" + format(agg_metrics.net_expectancy, "+,.2f") + " / trade")
    print("  Net PnL:                     $" + format(agg_metrics.net_pnl, "+,.2f"))
    print("  Total Fees Paid:             $" + format(agg_metrics.total_fees, ",.2f"))
    print("  Max Drawdown:                $" + format(agg_metrics.max_drawdown_amount, ",.2f") + " (" + str(round(agg_metrics.max_drawdown_pct, 2)) + "%)")
    print("  Max Consecutive Losses:      " + str(agg_metrics.max_consecutive_losses))
    print("  Long Win Rate:               " + str(agg_metrics.long_trades_count) + " trades (" + str(round(agg_metrics.long_win_rate * 100, 1)) + "% win)")
    print("  Short Win Rate:              " + str(agg_metrics.short_trades_count) + " trades (" + str(round(agg_metrics.short_win_rate * 100, 1)) + "% win)")

    zone_results = FibZoneAnalyzer.analyze_zones(all_trades)
    print("\n" + "=" * 80)
    print("           SECTION 61: FIBONACCI RETRACEMENT ZONE ANALYSIS           ")
    print("=" * 80)
    print("  FIB ZONE        TRADES     WIN RATE     NET PNL         PROFIT FACTOR   AVG R     ")
    print("  " + "-" * 75)
    for z_name, z_data in zone_results.items():
        net_val = "$" + format(z_data["net_pnl"], ",.2f")
        wr_val = str(round(z_data["win_rate"] * 100, 1)) + "%"
        pf_val = str(round(z_data["profit_factor"], 2))
        r_val = str(round(z_data["avg_r"], 2)) + "R"
        tr_cnt = str(z_data["trades"])
        print("  " + z_name.ljust(15) + tr_cnt.ljust(11) + wr_val.ljust(13) + net_val.ljust(16) + pf_val.ljust(16) + r_val)
    print("=" * 80 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Binance Futures Fibonacci Pullback Backtester")
    parser.add_argument("--symbols", type=str, default="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,ADAUSDT", help="Comma-separated list of symbols")
    parser.add_argument("--candles", type=int, default=6000, help="Number of 5M candles per symbol")
    parser.add_argument("--split", action="store_true", default=True, help="Enable 60/20/20 Train/Val/OOS split")
    args = parser.parse_args()

    sym_list = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    run_backtest_suite(symbols=sym_list, num_candles_5m=args.candles, split=args.split)
