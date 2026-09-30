"""
Parallelized 100-Trade Portfolio Analyzer across Top 100 Pairs
"""

import bisect
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

from backtest.dataset import HistoricalDataset
from backtest.engine import BacktestEngine
from backtest.metrics import MetricsCalculator, PerformanceMetrics
from backtest.zone_analysis import FibZoneAnalyzer
from core.types import Candle, TradeRecord

logging.basicConfig(level=logging.WARNING)

TOP_100_COINS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT", "ADAUSDT", "SUIUSDT", "AVAXUSDT", "LINKUSDT",
    "TRXUSDT", "NEARUSDT", "PEPEUSDT", "ENAUSDT", "SHIBUSDT", "LTCUSDT", "BCHUSDT", "DOTUSDT", "UNIUSDT", "APTUSDT",
    "WLDUSDT", "TAOUSDT", "FETUSDT", "RENDERUSDT", "OPUSDT", "ARBUSDT", "FILUSDT", "INJUSDT", "AAVEUSDT", "CRVUSDT",
    "ATOMUSDT", "SEIUSDT", "JUPUSDT", "BONKUSDT", "FLOKIUSDT", "KASUSDT", "ONDOUSDT", "HBARUSDT", "IMXUSDT", "MKRUSDT",
    "GRTUSDT", "STXUSDT", "RUNEUSDT", "THETAUSDT", "VETUSDT", "ALGOUSDT", "FTMUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT",
    "GALAUSDT", "CHZUSDT", "DYDXUSDT", "BLURUSDT", "1000PEPEUSDT", "1000BONKUSDT", "1000FLOKIUSDT", "1000SATSUSDT", "1000RATSUSDT", "MEMEUSDT",
    "WIFUSDT", "POPCATUSDT", "MEWUSDT", "BOMEUSDT", "NOTUSDT", "DOGSUSDT", "NEIROUSDT", "TURBOUSDT", "CATIUSDT", "HMSTRUSDT",
    "EIGENUSDT", "ZKUSDT", "STRKUSDT", "IOUSDT", "ATHUSDT", "ZETAUSDT", "OMNIUSDT", "REZUSDT", "BBUSDT", "NOTUSDT",
    "ACTUSDT", "PNUTUSDT", "GOATUSDT", "MOODENGUSDT", "PENGUUSDT", "MOVEUSDT", "MEUSDT", "KAIAUSDT", "COOKIEUSDT", "DRIFTUSDT",
    "PENDLEUSDT", "LDOUSDT", "JTOUSDT", "PYTHUSDT", "ORDIUSDT", "TIAUSDT", "BEAMUSDT", "BLASTUSDT", "ZROUSDT", "LISTAUSDT"
]

def sim_unit(sym_idx_tuple):
    sym, cycle, idx = sym_idx_tuple
    seed_val = abs(hash(sym)) % 10000 + (cycle * 997) + idx
    ds = HistoricalDataset.generate_synthetic_data(symbol=sym, num_5m_candles=4500, seed=seed_val, volatility=0.005)
    engine = BacktestEngine(initial_capital=10000.0)
    engine.risk_manager.trading_sessions = [(0, 0, 23, 59)]
    engine.run(ds)
    return engine.closed_trades

def main():
    print("=" * 85, flush=True)
    print("   BINANCE FUTURES -- EXACT 100 TRADES PORTFOLIO OBSERVER (100 PAIRS)   ", flush=True)
    print("=" * 85, flush=True)
    print("Tracking 100 pairs concurrently until exactly 100 qualifying trades complete...\n", flush=True)

    all_trades: List[TradeRecord] = []
    symbol_stats = {}
    
    tasks = []
    for cycle in range(1, 20):
        for idx, sym in enumerate(TOP_100_COINS):
            tasks.append((sym, cycle, idx))

    with ThreadPoolExecutor(max_workers=14) as executor:
        futures = [executor.submit(sim_unit, t) for t in tasks]
        for f in as_completed(futures):
            try:
                new_trades = f.result()
                if new_trades:
                    for t in new_trades:
                        if len(all_trades) < 100:
                            all_trades.append(t)
                            sym_t = t.symbol
                            if sym_t not in symbol_stats:
                                symbol_stats[sym_t] = {"trades": 0, "wins": 0, "pnl": 0.0}
                            symbol_stats[sym_t]["trades"] += 1
                            if t.net_pnl > 0:
                                symbol_stats[sym_t]["wins"] += 1
                            symbol_stats[sym_t]["pnl"] += t.net_pnl
                            
                            trade_num = len(all_trades)
                            res_str = "WIN " if t.net_pnl > 0 else "LOSS"
                            side_str = t.side
                            pnl_str = format(t.net_pnl, "+,.2f")
                            print(f"  [Trade {trade_num:>3}/100] {t.symbol:<12} | {side_str:<5} | Result: {res_str} | Net PnL: $" + pnl_str, flush=True)
                            
                            if len(all_trades) >= 100:
                                break
                if len(all_trades) >= 100:
                    break
            except Exception:
                pass

    print(f"\nCollected exactly {len(all_trades)} trades across the 100-pair portfolio.", flush=True)

    # 100 Trades Metrics Calculation
    m = MetricsCalculator.calculate(all_trades, initial_capital=10000.0)

    print("\n" + "=" * 85, flush=True)
    print("      FINAL 100-TRADE STATISTICAL VERIFICATION REPORT      ", flush=True)
    print("=" * 85, flush=True)
    print(f"  Total Trades Tested:         {m.total_trades}", flush=True)
    print(f"  Winning Trades:              {m.winning_trades} ({m.win_rate*100:.2f}%)", flush=True)
    print(f"  Losing Trades:               {m.losing_trades} ({m.loss_rate*100:.2f}%)", flush=True)
    print(f"  Profit Factor:               {m.profit_factor:.2f}", flush=True)
    print("  Average Win:                 $" + format(m.average_win, ",.2f"), flush=True)
    print("  Average Loss:                $" + format(m.average_loss, ",.2f"), flush=True)
    print(f"  Average R-Multiple:          {m.average_r:.2f}R", flush=True)
    print("  Gross Expectancy:            $" + format(m.gross_expectancy, "+,.2f") + " / trade", flush=True)
    print("  Net Expectancy (after fees): $" + format(m.net_expectancy, "+,.2f") + " / trade", flush=True)
    print("  Total Gross Profit:          $" + format(m.gross_profit, ",.2f"), flush=True)
    print("  Total Gross Loss:            $" + format(m.gross_loss, ",.2f"), flush=True)
    print("  Total Fees & Slippage:       $" + format(m.total_fees, ",.2f"), flush=True)
    print("  TOTAL NET PNL:               $" + format(m.net_pnl, "+,.2f"), flush=True)
    print(f"  Portfolio Return on Capital: {(m.net_pnl / 10000.0)*100:+.2f}%", flush=True)
    print("  Max Drawdown:                $" + format(m.max_drawdown_amount, ",.2f") + f" ({m.max_drawdown_pct:.2f}%)", flush=True)
    print(f"  Max Consecutive Losses:      {m.max_consecutive_losses}", flush=True)
    print(f"  Long Trades:                 {m.long_trades_count} trades ({m.long_win_rate*100:.1f}% win rate)", flush=True)
    print(f"  Short Trades:                {m.short_trades_count} trades ({m.short_win_rate*100:.1f}% win rate)", flush=True)

    # Fibonacci Zone Breakdown
    zone_results = FibZoneAnalyzer.analyze_zones(all_trades)
    print("\n" + "=" * 85, flush=True)
    print("           SECTION 61: FIBONACCI RETRACEMENT ZONE BREAKDOWN          ", flush=True)
    print("=" * 85, flush=True)
    print("  FIB ZONE        TRADES     WIN RATE     NET PNL          PROFIT FACTOR   AVG R     ", flush=True)
    print("  " + "-" * 78, flush=True)
    for z_name, z_data in zone_results.items():
        net_str = "$" + format(z_data["net_pnl"], "+,.2f")
        wr_val = z_data["win_rate"] * 100
        wr_str = f"{wr_val:.1f}%"
        pf_val = z_data["profit_factor"]
        pf_str = f"{pf_val:.2f}"
        r_val = z_data["avg_r"]
        r_str = f"{r_val:.2f}R"
        tr_cnt = z_data["trades"]
        print(f"  {z_name:<15} {tr_cnt:<10} {wr_str:<12} {net_str:<16} {pf_str:<15} {r_str:<10}", flush=True)

    # Top performing coins
    if symbol_stats:
        print("\n" + "=" * 85, flush=True)
        print("                     TOP PERFORMING COINS IN PORTFOLIO                ", flush=True)
        print("=" * 85, flush=True)
        sorted_coins = sorted(symbol_stats.items(), key=lambda x: x[1]["pnl"], reverse=True)
        for s_name, s_data in sorted_coins[:10]:
            pnl_c = format(s_data["pnl"], "+,.2f")
            tr_c = s_data["trades"]
            wr_c = (s_data["wins"] / tr_c) * 100 if tr_c else 0.0
            print(f"  • {s_name:<12} | Trades: {tr_c:>2} | WinRate: {wr_c:>5.1f}% | Net PnL: $" + pnl_c, flush=True)

    print("=" * 85 + "\n", flush=True)


if __name__ == "__main__":
    main()
