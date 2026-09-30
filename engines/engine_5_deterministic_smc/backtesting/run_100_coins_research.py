import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import time
import urllib.request
from typing import Dict, Any, List
from config import Config
from market_data.binance_client import BinanceFuturesClient
from market_data.candle_manager import CandleManager
from market_data.historical_fetcher import HistoricalFetcher
from backtesting.engine import BacktestEngine
from backtesting.metrics import PerformanceMetrics

TOP_100_PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "SUIUSDT",
    "NEARUSDT", "PEPEUSDT", "SHIBUSDT", "APTUSDT", "LTCUSDT", "TONUSDT", "WIFUSDT", "BCHUSDT", "FETUSDT", "TIAUSDT",
    "ARBUSDT", "OPUSDT", "INJUSDT", "RENDERUSDT", "KASUSDT", "FILUSDT", "ATOMUSDT", "SEIUSDT", "UNIUSDT", "ICPUSDT",
    "FTMUSDT", "TRXUSDT", "BONKUSDT", "FLOKIUSDT", "JUPUSDT", "ENAUSDT", "STRKUSDT", "PYTHUSDT", "AAVEUSDT", "STXUSDT",
    "GALAUSDT", "THETAUSDT", "RUNEUSDT", "GRTUSDT", "DYDXUSDT", "WLDUSDT", "ORDIUSDT", "BEAMUSDT", "SANDUSDT", "MANAUSDT",
    "AXSUSDT", "CHZUSDT", "PENDLEUSDT", "CRVUSDT", "MKRUSDT", "SNXUSDT", "LDOUSDT", "QNTUSDT", "ALGOUSDT", "VETUSDT",
    "EGLDUSDT", "FLOWUSDT", "KAVAUSDT", "BLURUSDT", "MINAUSDT", "NEOUSDT", "ROSEUSDT", "ZILUSDT", "1INCHUSDT", "IOTAUSDT",
    "ENJUSDT", "GMXUSDT", "APEUSDT", "CFXUSDT", "KSMUSDT", "ZRXUSDT", "COMPUSDT", "BATUSDT", "DASHUSDT", "EOSUSDT",
    "ETCUSDT", "HOTUSDT", "ICXUSDT", "IOSTUSDT", "KLAYUSDT", "LRCUSDT", "MASKUSDT", "OMGUSDT", "ONTUSDT", "QTUMUSDT",
    "RVNUSDT", "SCUSDT", "SKLUSDT", "STORJUSDT", "SUSHIUSDT", "WAVESUSDT", "XECUSDT", "XLMUSDT", "XMRUSDT", "YFIUSDT"
]

def run_100_coins_research():
    print("\n" + "=" * 90)
    print("  COMPREHENSIVE DETERMINISTIC SMC RESEARCH ON TOP 100 CRYPTO PAIRS")
    print("=" * 90 + "\n")

    config = Config()
    config.ALLOWED_SESSIONS = [(0, 24)] # 24/7 market evaluation
    client = BinanceFuturesClient()
    engine = BacktestEngine(config)

    overall_results: Dict[str, Any] = {}
    all_trades: List[Dict[str, Any]] = []

    successful_symbols = 0
    start_time_all = time.time()

    for idx, sym in enumerate(TOP_100_PAIRS, 1):
        candle_mgr = CandleManager(max_buffer=8000)
        fetcher = HistoricalFetcher(client, candle_mgr)

        try:
            fetcher.fetch_all_timeframes_for_symbol(
                symbol=sym,
                limit_4h=200,
                limit_1h=500,
                limit_15m=1200,
                limit_5m=2500
            )

            c4h = candle_mgr.get_closed_candles(sym, "4h")
            c1h = candle_mgr.get_closed_candles(sym, "1h")
            c15m = candle_mgr.get_closed_candles(sym, "15m")
            c5m = candle_mgr.get_closed_candles(sym, "5m")

            if len(c5m) < 100 or len(c15m) < 30:
                print(f"[{idx:03d}/{len(TOP_100_PAIRS)}] {sym:<10} -> [SKIP] Insufficient history")
                continue

            res = engine.run_backtest(sym, c4h, c1h, c15m, c5m, initial_capital=config.INITIAL_EQUITY)
            m = res["metrics"]
            trades = res["trades"]

            overall_results[sym] = {
                "metrics": m,
                "trades": trades
            }
            all_trades.extend(trades)
            successful_symbols += 1

            t_cnt = m["total_trades"]
            wr = m["win_rate"]
            pnl = m["net_profit"]
            ret = m["return_pct"]
            print(f"[{idx:03d}/{len(TOP_100_PAIRS)}] {sym:<10} -> Trades={t_cnt:<3} | WinRate={wr:>5.1f}% | Net PnL=${pnl:>+8,.2f} ({ret:>+5.2f}%)")

        except Exception as e:
            print(f"[{idx:03d}/{len(TOP_100_PAIRS)}] {sym:<10} -> [ERROR] {e}")
            continue

    elapsed = time.time() - start_time_all
    print(f"\n[*] Completed backtest on {successful_symbols} coins in {elapsed:.1f}s")

    # Aggregate Portfolio Metrics
    agg_metrics = PerformanceMetrics.calculate_metrics(all_trades, initial_capital=config.INITIAL_EQUITY)

    print("\n" + "=" * 95)
    print("  PORTFOLIO-WIDE AGGREGATE PERFORMANCE REPORT (TOP 100 COINS)")
    print("=" * 95)
    print(f"  Total Coins Analyzed:     {successful_symbols}")
    print(f"  Total Trades Executed:    {agg_metrics[total_trades]}")
    print(f"  Winning Trades:           {agg_metrics[winning_trades]} ({agg_metrics[win_rate]:.1f}%)")
    print(f"  Losing Trades:            {agg_metrics[losing_trades]}")
    print(f"  Gross Profit:             ${agg_metrics[gross_profit]:,.2f}")
    print(f"  Gross Loss:               ${agg_metrics[gross_loss]:,.2f}")
    print(f"  Total Fees & Slippage:    ${agg_metrics[fees]:,.2f}")
    print(f"  Cumulative Net Profit:    ${agg_metrics[net_profit]:+,.2f} ({agg_metrics[return_pct]:+.2f}%)")
    print(f"  Profit Factor:            {agg_metrics[profit_factor]:.2f}")
    print(f"  Expectancy Net / Trade:   ${agg_metrics[expectancy_net]:+.2f}")
    print(f"  Max Drawdown:             {agg_metrics[max_drawdown_pct]:.2f}%")
    print(f"  Max Consecutive Losses:   {agg_metrics[max_consecutive_losses]}")
    print("=" * 95)

    # Top 10 Best Coins by PnL
    active_coins = {k: v for k, v in overall_results.items() if v["metrics"]["total_trades"] > 0}
    ranked_coins = sorted(active_coins.items(), key=lambda x: x[1]["metrics"]["net_profit"], reverse=True)
    
    print("\n--- TOP 10 PERFORMING COINS ---")
    for r_sym, r_data in ranked_coins[:10]:
        rm = r_data["metrics"]
        print(f"  {r_sym:<12} | Trades: {rm[total_trades]:<4} | WinRate: {rm[win_rate]:<5.1f}% | Net PnL: ${rm[net_profit]:>+9,.2f} | PF: {rm[profit_factor]:.2f}")

    # Bottom 5 Coins by PnL
    print("\n--- WORST 5 PERFORMING COINS ---")
    for r_sym, r_data in ranked_coins[-5:]:
        rm = r_data["metrics"]
        print(f"  {r_sym:<12} | Trades: {rm[total_trades]:<4} | WinRate: {rm[win_rate]:<5.1f}% | Net PnL: ${rm[net_profit]:>+9,.2f} | PF: {rm[profit_factor]:.2f}")
    print("=" * 95)

    out_file = "/Users/karimsiam/.gemini/antigravity/scratch/smc_futures_bot/historical_research_100_coins.json"
    with open(out_file, "w") as f:
        json.dump(overall_results, f, indent=2)
    print(f"\n[OK] Full 100-coin dataset saved to {out_file}\n")

if __name__ == "__main__":
    run_100_coins_research()
