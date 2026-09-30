"""
Top 100 Coins Live Binance Futures Backtesting Suite
Evaluates the exact Fibonacci Pullback strategy across top 100 USDT pairs.
"""

import json
import logging
import sys
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

from backtest.dataset import HistoricalDataset
from backtest.engine import BacktestEngine
from backtest.metrics import MetricsCalculator, PerformanceMetrics
from backtest.zone_analysis import FibZoneAnalyzer
from core.types import Candle, TradeRecord

logging.basicConfig(level=logging.WARNING)


def fetch_top_100_symbols() -> List[str]:
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    
    usdt_pairs = [
        d for d in data 
        if d.get("symbol", "").endswith("USDT") 
        and not d["symbol"].startswith("DEFI")
        and not d["symbol"].startswith("BTCDOM")
    ]
    usdt_pairs.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
    return [d["symbol"] for d in usdt_pairs[:100]]


def fetch_klines(symbol: str, interval: str, limit: int = 1000) -> List[Candle]:
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    candles = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            for item in raw:
                candles.append(
                    Candle(
                        timestamp=int(item[0]),
                        open=float(item[1]),
                        high=float(item[2]),
                        low=float(item[3]),
                        close=float(item[4]),
                        volume=float(item[5]),
                        close_time=int(item[6]),
                        is_closed=True,
                    )
                )
    except Exception:
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                for item in raw:
                    candles.append(
                        Candle(
                            timestamp=int(item[0]),
                            open=float(item[1]),
                            high=float(item[2]),
                            low=float(item[3]),
                            close=float(item[4]),
                            volume=float(item[5]),
                            close_time=int(item[6]),
                            is_closed=True,
                        )
                    )
        except Exception:
            pass
    return candles


def process_symbol(symbol: str) -> Tuple[str, List[TradeRecord], Optional[PerformanceMetrics]]:
    c_5m = fetch_klines(symbol, "5m", limit=1000)
    c_15m = fetch_klines(symbol, "15m", limit=600)
    c_1h = fetch_klines(symbol, "1h", limit=300)
    c_4h = fetch_klines(symbol, "4h", limit=200)

    if len(c_5m) < 100 or len(c_15m) < 50 or len(c_1h) < 30 or len(c_4h) < 15:
        return symbol, [], None

    ds = HistoricalDataset(symbol)
    ds.candles_5m = c_5m
    ds.candles_15m = c_15m
    ds.candles_1h = c_1h
    ds.candles_4h = c_4h

    engine = BacktestEngine(initial_capital=10000.0)
    engine.risk_manager.trading_sessions = [(0, 0, 23, 59)]
    metrics = engine.run(ds)
    return symbol, engine.closed_trades, metrics


def main():
    print("=" * 85)
    print("   BINANCE FUTURES -- TOP 100 COINS STRATEGY BACKTEST (REAL MARKET DATA)   ")
    print("=" * 85)
    print("Retrieving Top 100 USDT-M Coins by 24h Volume...")
    top100 = fetch_top_100_symbols()
    print(f"Found {len(top100)} top pairs. Downloading multi-timeframe candles & simulating...\n")

    all_trades: List[TradeRecord] = []
    symbol_results = {}
    completed_count = 0

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_symbol, sym): sym for sym in top100}
        for future in as_completed(futures):
            sym = futures[future]
            try:
                sym, trades, metrics = future.result()
                completed_count += 1
                if trades:
                    all_trades.extend(trades)
                    wins = len([t for t in trades if t.net_pnl > 0])
                    wr = (wins / len(trades)) * 100
                    pnl = sum(t.net_pnl for t in trades)
                    pnl_str = format(pnl, "+,.2f")
                    symbol_results[sym] = {"trades": len(trades), "wins": wins, "win_rate": wr, "pnl": pnl}
                    print(f"[{completed_count:>3}/100] {sym:<12} -> {len(trades):>2} trades | WinRate: {wr:>5.1f}% | Net PnL: $" + pnl_str)
                else:
                    print(f"[{completed_count:>3}/100] {sym:<12} ->  0 trades (No setup met all 16 criteria)")
            except Exception as e:
                print(f"[{completed_count:>3}/100] {sym:<12} -> Error: {e}")

    if not all_trades:
        print("\nNo trades were generated across the target coins during this window.")
        return

    all_trades.sort(key=lambda t: t.exit_time)
    last_100_trades = all_trades[-100:] if len(all_trades) >= 100 else all_trades
    last_100_metrics = MetricsCalculator.calculate(last_100_trades, initial_capital=10000.0)

    print("\n" + "=" * 85)
    print(f"        PERFORMANCE ANALYSIS -- LAST {len(last_100_trades)} COMPLETED TRADES        ")
    print("=" * 85)
    print(f"  Total Trades Evaluated:      {last_100_metrics.total_trades}")
    print(f"  Winning Trades:              {last_100_metrics.winning_trades} ({last_100_metrics.win_rate*100:.2f}%)")
    print(f"  Losing Trades:               {last_100_metrics.losing_trades} ({last_100_metrics.loss_rate*100:.2f}%)")
    print(f"  Profit Factor:               {last_100_metrics.profit_factor:.2f}")
    print("  Average Win:                 $" + format(last_100_metrics.average_win, ",.2f"))
    print("  Average Loss:                $" + format(last_100_metrics.average_loss, ",.2f"))
    print(f"  Average R-Multiple:          {last_100_metrics.average_r:.2f}R")
    print("  Gross Expectancy:            $" + format(last_100_metrics.gross_expectancy, "+,.2f") + " / trade")
    print("  Net Expectancy (after fees): $" + format(last_100_metrics.net_expectancy, "+,.2f") + " / trade")
    print("  Total Gross Profit:          $" + format(last_100_metrics.gross_profit, ",.2f"))
    print("  Total Gross Loss:            $" + format(last_100_metrics.gross_loss, ",.2f"))
    print("  Total Fees & Slippage Paid:  $" + format(last_100_metrics.total_fees, ",.2f"))
    print("  TOTAL NET PNL:               $" + format(last_100_metrics.net_pnl, "+,.2f"))
    print("  Max Drawdown:                $" + format(last_100_metrics.max_drawdown_amount, ",.2f") + f" ({last_100_metrics.max_drawdown_pct:.2f}%)")
    print(f"  Max Consecutive Losses:      {last_100_metrics.max_consecutive_losses}")
    print(f"  Long Performance:            {last_100_metrics.long_trades_count} trades ({last_100_metrics.long_win_rate*100:.1f}% win rate)")
    print(f"  Short Performance:           {last_100_metrics.short_trades_count} trades ({last_100_metrics.short_win_rate*100:.1f}% win rate)")

    zone_results = FibZoneAnalyzer.analyze_zones(last_100_trades)
    print("\n" + "=" * 85)
    print("           SECTION 61: FIBONACCI RETRACEMENT ZONE BREAKDOWN          ")
    print("=" * 85)
    print(f"  FIB ZONE        TRADES     WIN RATE     NET PNL          PROFIT FACTOR   AVG R     ")
    print("  " + "-" * 78)
    for z_name, z_data in zone_results.items():
        net_str = "$" + format(z_data['net_pnl'], "+,.2f")
        wr_val = z_data['win_rate'] * 100
        wr_str = f"{wr_val:.1f}%"
        pf_val = z_data['profit_factor']
        pf_str = f"{pf_val:.2f}"
        r_val = z_data['avg_r']
        r_str = f"{r_val:.2f}R"
        tr_count = z_data['trades']
        print(f"  {z_name:<15} {tr_count:<10} {wr_str:<12} {net_str:<16} {pf_str:<15} {r_str:<10}")

    sorted_coins = sorted(symbol_results.items(), key=lambda x: x[1]['pnl'], reverse=True)
    if sorted_coins:
        print("\n" + "=" * 85)
        print("                     TOP PERFORMING COINS IN PORTFOLIO                ")
        print("=" * 85)
        for sym, data in sorted_coins[:10]:
            pnl_c = format(data['pnl'], "+,.2f")
            tr_c = data['trades']
            wr_c = data['win_rate']
            print(f"  • {sym:<12} | Trades: {tr_c:>2} | WinRate: {wr_c:>5.1f}% | Net PnL: $" + pnl_c)

    print("=" * 85 + "\n")


if __name__ == "__main__":
    main()
