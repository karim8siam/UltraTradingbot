import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import time
from typing import Dict, Any, List
from config import Config
from market_data.binance_client import BinanceFuturesClient
from market_data.candle_manager import CandleManager
from market_data.historical_fetcher import HistoricalFetcher
from backtesting.engine import BacktestEngine

def run_research():
    config = Config()
    client = BinanceFuturesClient()
    engine = BacktestEngine(config)

    symbols = config.SYMBOLS
    print("\n" + "=" * 80)
    print("  STARTING DETERMINISTIC SMC HISTORICAL RESEARCH ACROSS " + str(len(symbols)) + " PAIRS")
    print("=" * 80 + "\n")

    overall_results: Dict[str, Any] = {}
    all_trade_records: List[Dict[str, Any]] = []

    for sym_idx, sym in enumerate(symbols, 1):
        print(f"[{sym_idx}/{len(symbols)}] Fetching historical candles for {sym}...")
        candle_mgr = CandleManager(max_buffer=8000)
        fetcher = HistoricalFetcher(client, candle_mgr)

        fetcher.fetch_all_timeframes_for_symbol(
            symbol=sym,
            limit_4h=500,
            limit_1h=1500,
            limit_15m=3000,
            limit_5m=5000
        )

        c4h = candle_mgr.get_closed_candles(sym, "4h")
        c1h = candle_mgr.get_closed_candles(sym, "1h")
        c15m = candle_mgr.get_closed_candles(sym, "15m")
        c5m = candle_mgr.get_closed_candles(sym, "5m")

        print("  -> " + sym + ": Loaded 4H=" + str(len(c4h)) + ", 1H=" + str(len(c1h)) + ", 15M=" + str(len(c15m)) + ", 5M=" + str(len(c5m)) + " candles")
        print("  -> Running SMC strategy simulation on " + sym + "...")

        res = engine.run_backtest(
            symbol=sym,
            candles_4h=c4h,
            candles_1h=c1h,
            candles_15m=c15m,
            candles_5m=c5m,
            initial_capital=config.INITIAL_EQUITY
        )

        metrics = res["metrics"]
        trades = res["trades"]
        recent_100_trades = trades[-100:] if len(trades) > 100 else trades

        overall_results[sym] = {
            "metrics": metrics,
            "total_trades_count": len(trades),
            "recent_100_trades": recent_100_trades
        }
        all_trade_records.extend(trades)

        tot_t = metrics["total_trades"]
        wr_t = metrics["win_rate"]
        np_t = metrics["net_profit"]
        rp_t = metrics["return_pct"]
        print(f"  [+] {sym} Done: Total Trades={tot_t}, Win Rate={wr_t:.1f}%, Net PnL=${np_t:+,.2f} ({rp_t:+.2f}%)")
        time.sleep(0.1)

    print("\n" + "=" * 95)
    print("  DETERMINISTIC SMC HISTORICAL PERFORMANCE REPORT (10 PAIRS)")
    print("=" * 95)
    p_hdr = "PAIR"
    t_hdr = "TRADES"
    w_hdr = "WIN RATE"
    np_hdr = "NET PNL ($)"
    r_hdr = "RETURN (%)"
    pf_hdr = "PF"
    dd_hdr = "MAX DD (%)"
    print(f"  {p_hdr:<10} | {t_hdr:<7} | {w_hdr:<9} | {np_hdr:<14} | {r_hdr:<11} | {pf_hdr:<6} | {dd_hdr}")
    print("-" * 95)

    tot_trades_all = 0
    tot_pnl_all = 0.0

    for sym, data in overall_results.items():
        m = data["metrics"]
        tot_trades_all += m["total_trades"]
        tot_pnl_all += m["net_profit"]
        sym_s = sym
        t_s = m["total_trades"]
        w_s = str(round(m["win_rate"], 1)) + "%"
        np_s = f"${m['net_profit']:,.2f}"
        rp_s = str(round(m["return_pct"], 2)) + "%"
        pf_s = str(round(m["profit_factor"], 2))
        dd_s = str(round(m["max_drawdown_pct"], 2)) + "%"
        print(f"  {sym_s:<10} | {t_s:<7} | {w_s:<9} | {np_s:<14} | {rp_s:<11} | {pf_s:<6} | {dd_s}")

    print("-" * 95)
    print(f"  PORTFOLIO TOTAL: Trades={tot_trades_all} | Cumulative Net PnL=${tot_pnl_all:+,.2f}")
    print("=" * 95)

    out_file = "/Users/karimsiam/.gemini/antigravity/scratch/smc_futures_bot/historical_research_results.json"
    with open(out_file, "w") as f:
        json.dump(overall_results, f, indent=2)
    print("\n[OK] Full historical trade records saved to " + out_file + "\n")

if __name__ == "__main__":
    run_research()
