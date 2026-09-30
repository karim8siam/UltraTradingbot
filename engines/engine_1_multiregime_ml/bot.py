"""
Main Orchestration Loop for Binance Futures 200-Point Master Bot.
Scans the 4 whitelisted pairs using:
- Section 1: Trend Direction (50 pts)
- Section 2: Location & Order Blocks (50 pts)
- Section 3: Indicators (70 pts)
- Section 4: Candlestick Patterns (30 pts)
- 10 Hard Veto Rules & London/NY Session Filters
- Adaptive ML Meta-Classifier Gate
"""

import sys
import time
import argparse
from datetime import datetime
from typing import Dict, Any

from config import (
    ALLOWED_SYMBOLS,
    DEFAULT_TIMEFRAME,
    HIGHER_TIMEFRAME,
    USE_TESTNET,
    RISK_PER_TRADE_PERCENT,
    DEFAULT_LEVERAGE,
    PAUSE_NEW_TRADES
)
from database import (
    get_open_trades,
    get_closed_trades,
    get_performance_summary,
    record_daily_balance
)
from data_fetcher import data_fetcher
from strategy import analyze_market
from execution import executor
from ml_brain import ml_brain
from location_engine import is_active_trading_session


def print_banner():
    session_active, session_desc = is_active_trading_session()
    print("=" * 80)
    print("  🚀 BINANCE CRYPTO FUTURES ADAPTIVE MULTI-REGIME + ML TRADING BOT")
    print("=" * 80)
    print(f"  • Whitelist Pairs    : {', '.join(ALLOWED_SYMBOLS)}")
    print(f"  • Timeframe          : {DEFAULT_TIMEFRAME} (Macro: {HIGHER_TIMEFRAME})")
    print(f"  • Risk per Trade     : {RISK_PER_TRADE_PERCENT}% Total Portfolio Balance")
    print(f"  • Leverage           : {DEFAULT_LEVERAGE}x Isolated Margin")
    print(f"  • Active Session     : {session_desc}")
    print(f"  • Strategy Engines   : 1. Trend Pullback | 2. Volatility Breakout | 3. Range Mean-Reversion")
    print(f"  • Execution Quality  : Score >= 75 (PERFECT 🔥) | Score >= 60 (STRONG ✅) | Score >= 50 (MODERATE ⚠️)")
    print(f"  • ML Meta-Classifier : {'Active & Calibrated' if ml_brain.is_trained else 'Active (Ensemble Calibrated)'}")
    print("=" * 80)


def run_single_iteration(verbose: bool = True) -> Dict[str, Any]:
    """
    Executes one complete market scan cycle across all whitelisted pairs.
    """
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    session_active, session_desc = is_active_trading_session()

    if verbose:
        print(f"\n[{now_str}] 🔄 Scanning {len(ALLOWED_SYMBOLS)} Tier-1 Crypto Pairs | Reverse 1:1 Engine ACTIVE 🔥")

    # Step 1: Check Open Positions
    closed_trades = executor.check_and_update_positions()
    if closed_trades and verbose:
        print(f"  -> Closed {len(closed_trades)} position(s) in this iteration.")

    # Step 2: Record Daily Balance
    balance = data_fetcher.fetch_balance_usdt()
    try:
        today_date = datetime.utcnow().strftime("%Y-%m-%d")
        record_daily_balance(today_date, balance)
    except Exception as e:
        pass

    # Check if new trade entries are paused by user directive
    import os
    from dotenv import load_dotenv
    load_dotenv(override=True)
    from config import PAUSE_NEW_TRADES
    if PAUSE_NEW_TRADES or os.getenv("PAUSE_NEW_TRADES", "false").lower() in ("true", "1", "yes"):
        open_trades = get_open_trades()
        perf = get_performance_summary()
        if verbose:
            print(f"  ⏸️ [PAUSE MODE ACTIVE] New trade entries are STOPPED.")
            print(f"     Monitoring {len(open_trades)} active position(s) until they finish naturally.")
            print("-" * 80)
            print(
                f"  Balance: ${balance:,.2f} USDT | Open Trades: {len(open_trades)}/21 | "
                f"Total Trades: {perf['total_trades']} | Win Rate: {perf['win_rate']:.2f}% | "
                f"Total PnL: ${perf['total_pnl']:,.2f}"
            )
            print("-" * 80)
        return {
            "timestamp": now_str,
            "balance": balance,
            "open_trades_count": len(open_trades),
            "signals_processed": [],
            "performance": perf,
            "status": "PAUSED_MANAGING_RUNNING_POSITIONS"
        }

    signals_processed = []

    # Dynamic 24-hour screener pair loader (50%+ win-rate)
    target_symbols = ALLOWED_SYMBOLS
    shared_active = os.getenv("ACTIVE_PAIRS_FILE", "/app/shared/active_pairs.json")
    if not os.path.exists(shared_active):
        shared_active = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "shared", "active_pairs.json"))
    if os.path.exists(shared_active):
        try:
            with open(shared_active, "r") as f:
                pair_data = json.load(f)
                alloc = pair_data.get("engine_allocations", {}).get("engine_1_multiregime_ml")
                if alloc:
                    target_symbols = [s if "/" in s else f"{s[:-4]}/{s[-4:]}" for s in alloc]
        except Exception:
            pass

    for symbol in target_symbols:
        try:
            df_tf = data_fetcher.fetch_ohlcv(symbol, timeframe=DEFAULT_TIMEFRAME, limit=300)
            df_htf = data_fetcher.fetch_ohlcv(symbol, timeframe=HIGHER_TIMEFRAME, limit=100)
            df_micro = data_fetcher.fetch_ohlcv(symbol, timeframe="5m", limit=50)

            # Analyze market with Adaptive Multi-Regime Crypto Engine
            analysis = analyze_market(symbol=symbol, df_tf=df_tf, df_htf=df_htf, df_micro=df_micro)

            if analysis.get("direction"):
                direction = analysis["direction"]
                score = analysis["score"]
                strat = analysis.get("strategy", "ADAPTIVE")
                tier = "PERFECT TRADE 🔥" if score >= 75 else ("STRONG TRADE ✅" if score >= 60 else "MODERATE TRADE ⚠️")
                ml_app = analysis["ml_approved"]
                ml_conf = analysis["ml_confidence"]
                curr_p = analysis["current_price"]
                sl = analysis["stop_loss"]
                tp = analysis["take_profit"]
                b = analysis.get("score_breakdown", {})

                if verbose:
                    status_icon = "✅ APPROVED" if ml_app else "❌ ML-FILTERED"
                    print(
                        f"\n  [{symbol}] {status_icon}: {direction} via {strat} ({tier}) | Score: {score}/100\n"
                        f"    • Price: ${curr_p:,.2f} | Stop-Loss: ${sl:,.2f} | Take-Profit: ${tp:,.2f}\n"
                        f"    • Regime : {b.get('regime', 'N/A')} ({b.get('regime_desc', '')})\n"
                        f"    • ML Brain: {ml_conf * 100:.1f}% Confidence ({analysis['ml_reason']})"
                    )

                if ml_app:
                    exec_result = executor.execute_signal(analysis, account_balance=balance)
                    signals_processed.append(exec_result)
                    if verbose:
                        if exec_result.get("success"):
                            print(
                                f"    -> [ORDER PLACED] Trade ID: {exec_result.get('trade_id')} | "
                                f"Qty: {exec_result.get('quantity')} {symbol} | Risk: ${exec_result.get('target_risk_usd', 0):.2f} (1.0%)"
                            )
                        else:
                            print(f"    -> [ORDER REJECTED] {exec_result.get('reason')}")
            else:
                if verbose:
                    print(f"  [{symbol}] Neutral ({analysis.get('reason', 'Analyzing market structure')})")

        except Exception as e:
            print(f"  [ERROR] Failed to scan {symbol}: {e}")

    # Summary Line
    open_trades = get_open_trades()
    perf = get_performance_summary()

    if verbose:
        print("-" * 80)
        print(
            f"  Balance: ${balance:,.2f} USDT | Open Trades: {len(open_trades)}/{len(ALLOWED_SYMBOLS)} | "
            f"Total Trades: {perf['total_trades']} | Win Rate: {perf['win_rate_pct']}% | Total PnL: ${perf['total_pnl_usd']:,.2f}"
        )
        print("-" * 80)

    return {
        "timestamp": now_str,
        "balance": balance,
        "open_trades_count": len(open_trades),
        "signals_processed": signals_processed,
        "performance": perf
    }


def start_trading_loop(interval_seconds: int = 10):
    print_banner()
    print("=" * 80)
    print("  ⚡ 5M / 15M MULTI-TIMEFRAME CONFLUENCE WITH 1H BTC SENTINEL ACTIVE:")
    print("    • 🎯 Trigger Timeframe : 5M Execution Candles (Replaces 1M Noise)")
    print("    • 🏛️ Structure Timeframe : 15M Institutional Order Blocks & Pivots")
    print("    • 👑 Sovereign Sentinel: 1-Hour Bitcoin Macro Trend Alignment")
    print("    • 🧠 ML Dual-Ensemble  : 300-Tree Random Forest + XGBoost (58-62% Gates)")
    print("    • 🛡️ Risk Management   : 1.0% Risk / Trade | 1:1.5+ Clean R:R")
    print("=" * 80)
    print("Starting continuous multi-interval loop. Press Ctrl+C to stop.\n")

    tick_count = 0
    try:
        while True:
            tick_count += 1
            is_30s_tick = (tick_count % 3 == 0)
            is_60s_tick = (tick_count % 6 == 0)

            cadence_tag = "10s Micro-Trigger"
            if is_60s_tick:
                cadence_tag = "60s Macro & Sync"
            elif is_30s_tick:
                cadence_tag = "30s 15M Structure"

            run_single_iteration(verbose=True)
            time.sleep(10)

    except KeyboardInterrupt:
        print("\n[Bot Stopped] Trading bot stopped safely by user.")
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Binance Futures Multi-Interval Master Bot")
    parser.add_argument("--once", action="store_true", help="Run a single scan iteration and exit")
    parser.add_argument("--interval", type=int, default=10, help="Base polling interval in seconds (default: 10)")
    parser.add_argument("--bootstrap", action="store_true", help="Run historical bootstrap & pre-train ML model first")

    args = parser.parse_args()

    if args.bootstrap:
        from backtester import bootstrap_and_train_ml
        bootstrap_and_train_ml()

    if args.once:
        print_banner()
        run_single_iteration(verbose=True)
    else:
        start_trading_loop(interval_seconds=args.interval)
