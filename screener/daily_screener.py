"""
24-Hour Daily Rolling Screener & Dynamic Rotation Daemon.
Runs every midnight (00:00:00 UTC), evaluates past 24 hours of market data across 30 pairs,
filters coins with >= 50% Win Rate & 1:2 Risk/Reward, and updates shared/active_pairs.json.
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

# Ensure local imports work cleanly
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    SYMBOLS,
    MIN_WIN_RATE,
    MIN_RR,
    LOOKBACK_HOURS,
    ACTIVE_PAIRS_FILE,
    AUDIT_LOG_FILE,
    SHARED_DIR
)
from evaluator import fetch_klines, StrategyEvaluator


def log_message(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(SHARED_DIR, exist_ok=True)
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run_24h_screening_cycle() -> Dict[str, Any]:
    """
    Executes a complete 24-hour screening run across all 30 crypto pairs.
    """
    log_message("=" * 80)
    log_message("🚀 INITIATING 24-HOUR DAILY CRYPTO STRATEGY PERFORMANCE SCREENER")
    log_message(f"Evaluation Window: Trailing {LOOKBACK_HOURS}h (Midnight to Midnight)")
    log_message(f"Selection Gate: Win Rate >= {MIN_WIN_RATE * 100:.0f}% with 1:2 Risk/Reward")
    log_message(f"Analyzing {len(SYMBOLS)} Tier-1 USDT-M Futures Pairs...")
    log_message("=" * 80)

    rankings: List[Dict[str, Any]] = []
    engine_groups = {
        "confluence_scalpers": ["engine_1_multiregime_ml", "engine_3_confluence_scalper", "engine_10_confluence_100pairs"],
        "momentum_reversals": ["engine_2_momentum_3candle", "engine_4_reversal_5candle"],
        "smc_fvg_pullbacks": [
            "engine_5_deterministic_smc",
            "engine_6_fibonacci_pullback",
            "engine_7_institutional_fvg",
            "engine_8_gfs_multitimeframe",
            "engine_9_futures_swing"
        ]
    }

    per_engine_pairs: Dict[str, List[str]] = {
        f"engine_{i}": [] for i in range(1, 11)
    }

    qualified_for_confluence = []
    qualified_for_momentum = []
    qualified_for_smc = []

    for idx, sym in enumerate(SYMBOLS, 1):
        # Fetch 15m candles covering at least 24 hours (96 candles + 50 warmup)
        candles = fetch_klines(sym, interval="15m", limit=150)
        if not candles or len(candles) < 60:
            log_message(f"  [{idx:2d}/{len(SYMBOLS)}] {sym:<14} ⚠️ Insufficient data, skipped.")
            continue

        res_confluence = StrategyEvaluator.evaluate_confluence_scalper(candles)
        res_momentum = StrategyEvaluator.evaluate_momentum_reversal(candles)
        res_smc = StrategyEvaluator.evaluate_smc_fvg_pullback(candles)

        best_wr = max(res_confluence["win_rate"], res_momentum["win_rate"], res_smc["win_rate"])
        total_eval_trades = res_confluence["trades"] + res_momentum["trades"] + res_smc["trades"]

        rankings.append({
            "symbol": sym,
            "best_win_rate": best_wr,
            "confluence": res_confluence,
            "momentum": res_momentum,
            "smc_fvg": res_smc,
            "price": candles[-1]["close"]
        })

        # Check 50%+ threshold
        if res_confluence["win_rate"] >= (MIN_WIN_RATE * 100) and res_confluence["trades"] >= 1:
            qualified_for_confluence.append(sym)
        if res_momentum["win_rate"] >= (MIN_WIN_RATE * 100) and res_momentum["trades"] >= 1:
            qualified_for_momentum.append(sym)
        if res_smc["win_rate"] >= (MIN_WIN_RATE * 100) and res_smc["trades"] >= 1:
            qualified_for_smc.append(sym)

        status_str = f"WR: {best_wr:5.1f}% | Trades: {total_eval_trades:2d} | Confluence: {res_confluence['win_rate']:.0f}% | Mom: {res_momentum['win_rate']:.0f}% | SMC: {res_smc['win_rate']:.0f}%"
        flag = "✅ [QUALIFIED 50%+]" if best_wr >= 50.0 and total_eval_trades >= 1 else "   [WATCHLIST]"
        log_message(f"  [{idx:2d}/{len(SYMBOLS)}] {sym:<14} : {status_str} {flag}")

    # Fallback guard: ensure every engine always has top pairs even during quiet weekend consolidation
    baseline_top = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    if not qualified_for_confluence:
        qualified_for_confluence = baseline_top
    if not qualified_for_momentum:
        qualified_for_momentum = baseline_top
    if not qualified_for_smc:
        qualified_for_smc = baseline_top

    # Assign to individual engines
    engine_pair_allocations = {
        "engine_1_multiregime_ml": qualified_for_confluence,
        "engine_2_momentum_3candle": qualified_for_momentum,
        "engine_3_confluence_scalper": qualified_for_confluence,
        "engine_4_reversal_5candle": qualified_for_momentum,
        "engine_5_deterministic_smc": qualified_for_smc,
        "engine_6_fibonacci_pullback": qualified_for_smc,
        "engine_7_institutional_fvg": qualified_for_smc,
        "engine_8_gfs_multitimeframe": qualified_for_smc,
        "engine_9_futures_swing": qualified_for_smc,
        "engine_10_confluence_100pairs": qualified_for_confluence
    }

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    next_midnight = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00 UTC")

    payload = {
        "last_screened_at": now_iso,
        "valid_until": next_midnight,
        "cycle_duration": "24h (Midnight to Midnight)",
        "min_win_rate_gate": f"{MIN_WIN_RATE * 100:.0f}%",
        "target_risk_reward": f"1:{MIN_RR}",
        "total_universe_scanned": len(SYMBOLS),
        "engine_allocations": engine_pair_allocations,
        "summary": {
            "qualified_confluence_count": len(qualified_for_confluence),
            "qualified_momentum_count": len(qualified_for_momentum),
            "qualified_smc_count": len(qualified_for_smc)
        },
        "top_ranked_pairs": sorted(rankings, key=lambda x: x["best_win_rate"], reverse=True)[:15]
    }

    # Write out active pairs atomically to shared/
    try:
        os.makedirs(SHARED_DIR, exist_ok=True)
        tmp_file = ACTIVE_PAIRS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_file, ACTIVE_PAIRS_FILE)
        log_message(f"\n✅ Dynamic active pairs successfully updated at {ACTIVE_PAIRS_FILE}")
    except Exception as e:
        log_message(f"❌ Error saving active pairs: {e}")

    log_message("=" * 80)
    log_message(f"🏁 24H SCREENING COMPLETE: Validated until next midnight ({next_midnight})")
    log_message("=" * 80)
    return payload


def seconds_until_midnight_utc() -> float:
    now = datetime.now(timezone.utc)
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
    return (next_midnight - now).total_seconds()


def main():
    parser = argparse.ArgumentParser(description="24-Hour Daily Crypto Strategy Screener")
    parser.add_argument("--run-now", action="store_true", help="Execute an immediate 24h screening audit")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for cron/scheduled tasks)")
    args = parser.parse_args()

    # Always execute one screening immediately on startup so engines have data right away
    run_24h_screening_cycle()

    if args.once:
        sys.exit(0)

    # 24-Hour Continuous Midnight Loop
    while True:
        wait_sec = seconds_until_midnight_utc()
        hrs = wait_sec / 3600.0
        log_message(f"⏳ Screener sleeping {wait_sec:.0f}s ({hrs:.2f} hours) until next Midnight (00:00:00 UTC)...")
        time.sleep(wait_sec)
        try:
            run_24h_screening_cycle()
        except Exception as e:
            log_message(f"❌ Unexpected error in screening cycle: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()
