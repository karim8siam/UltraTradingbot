"""
Binance USDT-M Futures Systematic Swing Trading Bot - CLI Entrypoint.
Commands:
  python main.py backtest [--symbols BTCUSDT,ETHUSDT]
  python main.py walk-forward
  python main.py scan
  python main.py paper
  python main.py testnet
"""

import sys
import os
import argparse
import logging
import time
from typing import List

from config import DEFAULT_CONFIG
from database.db import Database
from market_data.data_fetcher import DataFetcher
from backtesting.engine import BacktestEngine
from backtesting.walk_forward import WalkForwardEngine
from execution.trader import SwingTrader
from dashboard.cli_dashboard import CLIDashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Main")


def run_backtest(args) -> None:
    config = DEFAULT_CONFIG
    symbols = args.symbols.split(",") if args.symbols else config.SYMBOLS
    db = Database(config.DB_PATH)
    fetcher = DataFetcher(config)
    dashboard = CLIDashboard()

    print(f"\n[+] Loading / Fetching Multi-Timeframe Data for {len(symbols)} symbols: {', '.join(symbols)}...")
    symbols_data = {}
    for s in symbols:
        s = s.strip().upper()
        df_1d = fetcher.get_candles(s, config.TF_DAILY, min_candles=args.daily_candles)
        df_4h = fetcher.get_candles(s, config.TF_4H, min_candles=args.four_h_candles)
        df_1h = fetcher.get_candles(s, config.TF_1H, min_candles=args.one_h_candles)
        symbols_data[s] = {"1d": df_1d, "4h": df_4h, "1h": df_1h}

    print(f"[+] Running Bar-by-Bar Multi-Timeframe Backtest Engine (Initial Equity: ${args.equity:,.2f})...")
    engine = BacktestEngine(config=config, initial_equity=args.equity, db=db)
    result = engine.run(symbols_data)

    print("\n")
    dashboard.render_backtest_summary(result.metrics)


def run_walk_forward(args) -> None:
    config = DEFAULT_CONFIG
    symbols = args.symbols.split(",") if args.symbols else config.SYMBOLS
    fetcher = DataFetcher(config)
    dashboard = CLIDashboard()

    print(f"\n[+] Loading Data for Walk-Forward & Out-of-Sample Evaluation: {', '.join(symbols)}...")
    symbols_data = {}
    for s in symbols:
        s = s.strip().upper()
        df_1d = fetcher.get_candles(s, config.TF_DAILY, min_candles=args.daily_candles)
        df_4h = fetcher.get_candles(s, config.TF_4H, min_candles=args.four_h_candles)
        df_1h = fetcher.get_candles(s, config.TF_1H, min_candles=args.one_h_candles)
        symbols_data[s] = {"1d": df_1d, "4h": df_4h, "1h": df_1h}

    wf_engine = WalkForwardEngine(config=config)
    dev_res, val_res, oos_res = wf_engine.run_split_evaluation(symbols_data)

    print("\n========== 1. DEVELOPMENT SET (60%) ==========")
    dashboard.render_backtest_summary(dev_res.metrics)

    print("\n========== 2. VALIDATION SET (20%) ==========")
    dashboard.render_backtest_summary(val_res.metrics)

    print("\n========== 3. OUT-OF-SAMPLE TEST (20%) ==========")
    dashboard.render_backtest_summary(oos_res.metrics)


def run_scan(args) -> None:
    config = DEFAULT_CONFIG
    symbols = args.symbols.split(",") if args.symbols else config.SYMBOLS
    db = Database(config.DB_PATH)
    trader = SwingTrader(config=config, db=db)
    dashboard = CLIDashboard()

    dashboard.print_header(
        mode=trader.mode_str,
        account_equity=10000.0,
        open_positions_count=0,
        open_risk_pct=0.0,
        daily_loss_pct=0.0
    )

    results = []
    print(f"[+] Scanning {len(symbols)} symbols on 1D -> 4H -> 1H...")
    for s in symbols:
        res = trader.scan_symbol_cycle(s.strip().upper())
        if res:
            results.append(res)

    dashboard.render_scan_table(results)


def run_paper(args) -> None:
    config = DEFAULT_CONFIG
    config.PAPER_TRADING = True
    config.DRY_RUN = False
    config.LIVE_TRADING = False
    symbols = args.symbols.split(",") if args.symbols else config.SYMBOLS
    db = Database(config.DB_PATH)
    trader = SwingTrader(config=config, db=db)
    trader.startup_and_recover()
    dashboard = CLIDashboard()

    print("[+] Paper Trading daemon active. Press Ctrl+C to terminate.\n")
    try:
        while True:
            results = []
            for s in symbols:
                res = trader.scan_symbol_cycle(s.strip().upper())
                if res:
                    results.append(res)
            dashboard.render_scan_table(results)
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[+] Paper Trading stopped.")


def main():
    parser = argparse.ArgumentParser(description="Binance USDT-M Futures Systematic Swing Trading Bot")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Backtest command
    bt_parser = subparsers.add_parser("backtest", help="Run historical backtesting")
    bt_parser.add_argument("--symbols", type=str, default="", help="Comma-separated symbols (e.g. BTCUSDT,ETHUSDT)")
    bt_parser.add_argument("--equity", type=float, default=10000.0, help="Initial account equity")
    bt_parser.add_argument("--daily-candles", type=int, default=1000, help="Number of 1D candles")
    bt_parser.add_argument("--four-h-candles", type=int, default=3000, help="Number of 4H candles")
    bt_parser.add_argument("--one-h-candles", type=int, default=6000, help="Number of 1H candles")

    # Walk-Forward command
    wf_parser = subparsers.add_parser("walk-forward", help="Run 60/20/20 Out-of-sample & Walk-forward testing")
    wf_parser.add_argument("--symbols", type=str, default="")
    wf_parser.add_argument("--daily-candles", type=int, default=1000)
    wf_parser.add_argument("--four-h-candles", type=int, default=3000)
    wf_parser.add_argument("--one-h-candles", type=int, default=6000)

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Run live market scan on current candles")
    scan_parser.add_argument("--symbols", type=str, default="")

    # Paper trading command
    paper_parser = subparsers.add_parser("paper", help="Run real-time paper trading loop")
    paper_parser.add_argument("--symbols", type=str, default="")

    args = parser.parse_args()

    if args.command == "backtest":
        run_backtest(args)
    elif args.command == "walk-forward":
        run_walk_forward(args)
    elif args.command == "scan":
        run_scan(args)
    elif args.command == "paper":
        run_paper(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
