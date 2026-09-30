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

def run_deep_research():
    config = Config()
    client = BinanceFuturesClient()
    
    print("\n" + "=" * 90)
    print("  DEEP HISTORICAL SMC RESEARCH (10 PAIRS — EXPANDED CANDLE DATASET)")
    print("=" * 90 + "\n")

    symbols = config.SYMBOLS
    results_24h: Dict[str, Any] = {}
    
    candle_mgr = CandleManager(max_buffer=25000)
    fetcher = HistoricalFetcher(client, candle_mgr)

    config_24h = Config()
    config_24h.ALLOWED_SESSIONS = [(0, 24)]
    engine_24h = BacktestEngine(config_24h)

    for sym_idx, sym in enumerate(symbols, 1):
        print(f"[{sym_idx}/{len(symbols)}] Downloading deep historical dataset for {sym}...")
        
        fetcher.fetch_all_timeframes_for_symbol(
            symbol=sym,
            limit_4h=600,
            limit_1h=2000,
            limit_15m=5000,
            limit_5m=10000
        )

        c4h = candle_mgr.get_closed_candles(sym, "4h")
        c1h = candle_mgr.get_closed_candles(sym, "1h")
        c15m = candle_mgr.get_closed_candles(sym, "15m")
        c5m = candle_mgr.get_closed_candles(sym, "5m")

        print("  -> " + sym + ": Loaded 4H=" + str(len(c4h)) + ", 1H=" + str(len(c1h)) + ", 15M=" + str(len(c15m)) + ", 5M=" + str(len(c5m)) + " candles")
        print("  -> Running SMC Backtest on " + sym + "...")

        res = engine_24h.run_backtest(sym, c4h, c1h, c15m, c5m, initial_capital=config.INITIAL_EQUITY)
        m = res["metrics"]
        trades = res["trades"]
        
        results_24h[sym] = {
            "metrics": m,
            "trades": trades
        }

        tot = m["total_trades"]
        wr = m["win_rate"]
        np_val = m["net_profit"]
        ret = m["return_pct"]
        dd = m["max_drawdown_pct"]
        print("  [+] " + sym + " Result: Trades=" + str(tot) + ", WinRate=" + str(round(wr, 1)) + "%, Net PnL=$" + f"{np_val:+,.2f}" + " (" + str(round(ret, 2)) + "%), MaxDD=" + str(round(dd, 2)) + "%")
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

    for sym, data in results_24h.items():
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

    out_file = "/Users/karimsiam/.gemini/antigravity/scratch/smc_futures_bot/deep_historical_research.json"
    with open(out_file, "w") as f:
        json.dump(results_24h, f, indent=2)
    print(f"\n[OK] Deep historical research records saved to {out_file}\n")

if __name__ == "__main__":
    run_deep_research()
