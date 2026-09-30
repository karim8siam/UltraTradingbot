"""
Main CLI Launcher for Binance Futures GFS Multi-Timeframe Trading Bot
"""

import argparse
import sys
import os

from config import BotConfig, DEFAULT_SYMBOLS
from bot_daemon import GFSBotDaemon


def main():
    parser = argparse.ArgumentParser(description="Binance Futures GFS Trading Bot Launcher")
    parser.add_argument("--mode", type=str, default="PAPER", choices=["DRY_RUN", "PAPER", "TESTNET", "LIVE"], help="Operating Mode")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="List of trading symbols")
    parser.add_argument("--risk", type=float, default=0.02, help="Risk per trade (default: 0.02 = 2%)")
    parser.add_argument("--leverage", type=int, default=5, help="Default leverage (default: 5x)")
    parser.add_argument("--max-positions", type=int, default=1, help="Max simultaneous open positions (default: 1)")
    parser.add_argument("--poll", type=int, default=15, help="Poll interval in seconds")
    parser.add_argument("--sessions", action="store_true", help="Enforce UTC trading sessions")
    args = parser.parse_args()

    paper_trading = (args.mode == "PAPER" or args.mode == "DRY_RUN")
    testnet = (args.mode == "TESTNET")
    live_trading = (args.mode == "LIVE")
    live_confirmation = False

    if live_trading:
        # Check if confirmed via environment or CLI
        from config import LIVE_TRADING_CONFIRMATION
        if LIVE_TRADING_CONFIRMATION:
            live_confirmation = True
        elif sys.stdin.isatty():
            print("\n" + "=" * 80)
            print(" [WARNING] YOU HAVE SELECTED LIVE TRADING WITH REAL CAPITAL!")
            print("=" * 80)
            conf = input(" Type \x27CONFIRM_LIVE\x27 to enable live execution: ").strip()
            if conf != "CONFIRM_LIVE":
                print("[ABORT] Live trading was not confirmed. Exiting.")
                sys.exit(1)
            live_confirmation = True
        else:
            live_confirmation = True

    config = BotConfig(
        symbols=args.symbols,
        paper_trading=paper_trading,
        binance_testnet=testnet,
        live_trading=live_trading,
        live_confirmation=live_confirmation,
        risk_per_trade=args.risk,
        default_leverage=args.leverage,
        max_open_positions=args.max_positions,
        enforce_sessions=args.sessions
    )

    daemon = GFSBotDaemon(config=config)
    daemon.start(poll_interval_sec=args.poll)


if __name__ == "__main__":
    main()
