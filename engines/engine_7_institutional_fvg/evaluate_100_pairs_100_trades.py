"""
100-Pair Evaluation & 100-Trade Performance Analyzer
Executes deterministic FVG Strategy across Top 100 Binance USDT-M Pairs
Calculates exact PnL ($), Return (%), Win Rate (%), Profit Factor, Expectancy, and Trade Log.
"""

import os
import sys
import time
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import BotConfig
from indicators import Candle
from risk_manager import PositionSizeResult, RiskManager, SymbolSpecs
from fvg_state_machine import SymbolStateMachine, BotSymbolState
from backtester import BacktestEngine, BacktestMetrics, BacktestTrade
from data_downloader import DataDownloader


TOP_100_PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "MATICUSDT", "NEARUSDT", "ICPUSDT", "SUIUSDT", "APTUSDT", "ATOMUSDT", "LTCUSDT", "BCHUSDT", "ETCUSDT", "XLMUSDT",
    "FILUSDT", "HBARUSDT", "KASUSDT", "INJUSDT", "RNDRUSDT", "GRTUSDT", "THETAUSDT", "FTMUSDT", "STXUSDT", "MANAUSDT",
    "SANDUSDT", "AXSUSDT", "GALAUSDT", "APEUSDT", "AAVEUSDT", "MKRUSDT", "SNXUSDT", "CRVUSDT", "LDOUSDT", "RUNEUSDT",
    "DYDXUSDT", "COMPUSDT", "1INCHUSDT", "SUSHIUSDT", "UNIUSDT", "ARBUSDT", "OPUSDT", "TIAUSDT", "SEIUSDT", "BLURUSDT",
    "WLDUSDT", "ORDIUSDT", "SATSUSDT", "MEMEUSDT", "PEPEUSDT", "SHIBUSDT", "BONKUSDT", "FLOKIUSDT", "WIFUSDT", "BOMEUSDT",
    "FETUSDT", "AGIXUSDT", "OCEANUSDT", "TAOUSDT", "ARKMUSDT", "PENDLEUSDT", "ENAUSDT", "ETHFIUSDT", "JTOUSDT", "PYTHUSDT",
    "JUPUSDT", "STRKUSDT", "ALTUSDT", "MANTAUSDT", "PORTALUSDT", "AEVOUSDT", "PIXELUSDT", "RONINUSDT", "DYMUSDT", "AIUSDT",
    "NFPUSDT", "XAIUSDT", "ACEUSDT", "BEAMUSDT", "SUPERUSDT", "ILVUSDT", "YGGUSDT", "IMXUSDT", "FLOWUSDT", "ENJUSDT",
    "CHZUSDT", "KAVAUSDT", "EGLDUSDT", "ALGOUSDT", "QNTUSDT", "XTZUSDT", "EOSUSDT", "IOTAUSDT", "NEOUSDT", "ZILUSDT"
]

BASE_PRICES = {
    "BTCUSDT": 65000.0, "ETHUSDT": 3500.0, "BNBUSDT": 580.0, "SOLUSDT": 140.0, "XRPUSDT": 0.60,
    "ADAUSDT": 0.45, "DOGEUSDT": 0.12, "AVAXUSDT": 28.0, "LINKUSDT": 14.0, "DOTUSDT": 6.50,
    "MATICUSDT": 0.55, "NEARUSDT": 5.20, "ICPUSDT": 8.50, "SUIUSDT": 1.10, "APTUSDT": 7.80,
    "ATOMUSDT": 6.20, "LTCUSDT": 75.0, "BCHUSDT": 380.0, "ETCUSDT": 22.0, "XLMUSDT": 0.11,
    "FILUSDT": 4.50, "HBARUSDT": 0.07, "KASUSDT": 0.16, "INJUSDT": 24.0, "RNDRUSDT": 6.80,
    "GRTUSDT": 0.18, "THETAUSDT": 1.40, "FTMUSDT": 0.65, "STXUSDT": 1.70, "MANAUSDT": 0.35,
    "SANDUSDT": 0.32, "AXSUSDT": 5.80, "GALAUSDT": 0.025, "APEUSDT": 0.85, "AAVEUSDT": 140.0,
    "MKRUSDT": 2200.0, "SNXUSDT": 1.60, "CRVUSDT": 0.30, "LDOUSDT": 1.25, "RUNEUSDT": 4.80,
    "DYDXUSDT": 1.20, "COMPUSDT": 48.0, "1INCHUSDT": 0.32, "SUSHIUSDT": 0.75, "UNIUSDT": 7.50,
    "ARBUSDT": 0.60, "OPUSDT": 1.60, "TIAUSDT": 5.50, "SEIUSDT": 0.32, "BLURUSDT": 0.18,
    "WLDUSDT": 1.80, "ORDIUSDT": 35.0, "SATSUSDT": 0.0003, "MEMEUSDT": 0.015, "PEPEUSDT": 0.000009,
    "SHIBUSDT": 0.000018, "BONKUSDT": 0.000022, "FLOKIUSDT": 0.00015, "WIFUSDT": 2.10, "BOMEUSDT": 0.009,
    "FETUSDT": 1.30, "AGIXUSDT": 0.60, "OCEANUSDT": 0.55, "TAOUSDT": 320.0, "ARKMUSDT": 1.20,
    "PENDLEUSDT": 3.80, "ENAUSDT": 0.50, "ETHFIUSDT": 1.80, "JTOUSDT": 2.40, "PYTHUSDT": 0.35,
    "JUPUSDT": 0.85, "STRKUSDT": 0.45, "ALTUSDT": 0.12, "MANTAUSDT": 0.90, "PORTALUSDT": 0.40,
    "AEVOUSDT": 0.45, "PIXELUSDT": 0.18, "RONINUSDT": 1.60, "DYMUSDT": 1.80, "AIUSDT": 0.65,
    "NFPUSDT": 0.30, "XAIUSDT": 0.35, "ACEUSDT": 2.80, "BEAMUSDT": 0.018, "SUPERUSDT": 0.85,
    "ILVUSDT": 45.0, "YGGUSDT": 0.48, "IMXUSDT": 1.40, "FLOWUSDT": 0.60, "ENJUSDT": 0.18,
    "CHZUSDT": 0.07, "KAVAUSDT": 0.35, "EGLDUSDT": 32.0, "ALGOUSDT": 0.13, "QNTUSDT": 78.0,
    "XTZUSDT": 0.70, "EOSUSDT": 0.55, "IOTAUSDT": 0.14, "NEOUSDT": 11.5, "ZILUSDT": 0.018
}


def run_100_pair_analysis(target_trade_count: int = 100, initial_equity: float = 10000.0) -> None:
    print("\n" + "=" * 105)
    print("       BINANCE USDT-M FUTURES — 100-PAIR FVG STRATEGY PERFORMANCE ANALYZER")
    print(f"       Universe: 100 Pairs | Target Completed Trades: {target_trade_count} | Starting Equity: ${initial_equity:,.2f}")
    print("=" * 105)

    config = BotConfig()
    config.SYMBOLS = TOP_100_PAIRS
    config.TRADING_SESSIONS = [(0, 24)]  # 24H market coverage for comprehensive testing
    config.MAX_OPEN_POSITIONS = 10       # Allow 10 concurrent trades across 100 pairs
    downloader = DataDownloader()

    print(f"\n[1/4] Preparing Multi-Timeframe (4H, 1H, 15M, 5M) Market Data across 100 pairs...")
    datasets = {}
    specs = {}

    for sym in TOP_100_PAIRS:
        bp = BASE_PRICES.get(sym, 10.0)
        datasets[sym] = downloader.get_or_load_dataset(sym, base_price=bp, num_5m_bars=6000)
        price_prec = 2 if bp >= 1.0 else (4 if bp >= 0.01 else 7)
        qty_prec = 1 if bp >= 1000.0 else (2 if bp >= 10.0 else 0)
        step_sz = 0.1 if bp >= 1000.0 else (0.01 if bp >= 10.0 else 1.0)
        specs[sym] = SymbolSpecs(
            symbol=sym,
            tick_size=10 ** (-price_prec),
            step_size=step_sz,
            price_precision=price_prec,
            qty_precision=qty_prec,
            min_qty=step_sz,
            min_notional=5.0
        )

    print(f" -> Successfully loaded 100 multi-timeframe pair datasets (600,000 total 5M candles).")

    print("\n[2/4] Executing Institutional Zero Look-Ahead Multi-Timeframe Simulation Engine...")
    engine = BacktestEngine(config, initial_equity=initial_equity, specs=specs)
    all_metrics, all_trades = engine.run(datasets)

    print(f" -> Completed backtest run: {len(all_trades)} total trades generated across the 100-pair universe.")

    # Select the exact last 100 trades (or all if < 100)
    eval_trades = all_trades[-target_trade_count:] if len(all_trades) >= target_trade_count else all_trades
    n_trades = len(eval_trades)

    if n_trades == 0:
        print("\n [!] No trades triggered under current strict filter settings.")
        return

    # Calculate exact metrics for these 100 trades
    wins = [t for t in eval_trades if t.result == "WIN"]
    losses = [t for t in eval_trades if t.result == "LOSS"]

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / n_trades) * 100.0
    loss_rate = (loss_count / n_trades) * 100.0

    gross_profit = sum(t.gross_pnl for t in wins)
    gross_loss = abs(sum(t.gross_pnl for t in losses))
    total_fees = sum(t.fees for t in eval_trades)
    total_slippage = sum(t.slippage for t in eval_trades)
    total_funding = sum(t.funding for t in eval_trades)
    total_costs = total_fees + total_slippage + total_funding

    net_pnl = sum(t.net_pnl for t in eval_trades)
    final_equity = initial_equity + net_pnl
    return_pct = (net_pnl / initial_equity) * 100.0

    avg_win_dollar = (sum(t.net_pnl for t in wins) / win_count) if win_count else 0.0
    avg_loss_dollar = (abs(sum(t.net_pnl for t in losses)) / loss_count) if loss_count else 0.0
    avg_win_pct = (avg_win_dollar / initial_equity) * 100.0
    avg_loss_pct = (avg_loss_dollar / initial_equity) * 100.0

    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    avg_r = sum(t.rr for t in eval_trades) / n_trades

    # Expectancy
    wr_dec = win_rate / 100.0
    lr_dec = loss_rate / 100.0
    expectancy_net = (wr_dec * avg_win_dollar) - (lr_dec * avg_loss_dollar)

    # Max Drawdown for this 100-trade sequence
    eq = initial_equity
    curve = [eq]
    for t in eval_trades:
        eq += t.net_pnl
        curve.append(eq)

    peak = initial_equity
    max_dd_dollars = 0.0
    max_dd_pct = 0.0
    for val in curve:
        if val > peak:
            peak = val
        dd_amt = peak - val
        dd_pct = (dd_amt / peak) * 100.0 if peak > 0 else 0.0
        if dd_amt > max_dd_dollars:
            max_dd_dollars = dd_amt
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

    # Max consecutive losses
    curr_consec = 0
    max_consec = 0
    for t in eval_trades:
        if t.result == "LOSS":
            curr_consec += 1
            if curr_consec > max_consec:
                max_consec = curr_consec
        else:
            curr_consec = 0

    print("\n[3/4] 100-TRADE PERFORMANCE EXECUTIVE SUMMARY")
    print("-" * 105)
    print(f" Total Trades Evaluated       : {n_trades} Completed Trades across 100 Pairs")
    print(f" Winning Trades / Losing Trades: {win_count} Wins ({win_rate:.2f}%)  |  {loss_count} Losses ({loss_rate:.2f}%)")
    print(f" Starting Account Equity       : ${initial_equity:,.2f} USDT")
    print(f" Final Account Equity          : ${final_equity:,.2f} USDT")
    print(f" Net Realized PnL ($)          : ${net_pnl:+,.2f} USDT")
    print(f" Return on Equity (%)          : {return_pct:+.2f}%")
    print(f" Profit Factor                 : {profit_factor:.2f}")
    print(f" Average Risk/Reward (R)       : {avg_r:.2f}R")
    print(f" Average Win                   : +${avg_win_dollar:,.2f} (+{avg_win_pct:.2f}% equity)")
    print(f" Average Loss                  : -${avg_loss_dollar:,.2f} (-{avg_loss_pct:.2f}% equity)")
    print(f" Net Expectancy Per Trade      : ${expectancy_net:+,.2f} / trade")
    print(f" Gross Profit / Gross Loss     : +${gross_profit:,.2f}  |  -${gross_loss:,.2f}")
    print(f" Total Costs (Fees+Slip+Fund)  : ${total_costs:,.2f} (Fees: ${total_fees:,.2f}, Slippage: ${total_slippage:,.2f}, Funding: ${total_funding:,.2f})")
    print(f" Maximum Equity Drawdown       : -{max_dd_pct:.2f}% (-${max_dd_dollars:,.2f})")
    print(f" Max Consecutive Losses        : {max_consec} losses")

    # Directional Breakdown
    long_trades = [t for t in eval_trades if t.side == "LONG"]
    short_trades = [t for t in eval_trades if t.side == "SHORT"]
    long_wins = [t for t in long_trades if t.result == "WIN"]
    short_wins = [t for t in short_trades if t.result == "WIN"]

    print("\n DIRECTIONAL BREAKDOWN (LONG vs SHORT):")
    print("-" * 105)
    print(f" LONG Setups  : {len(long_trades):<3} trades | {len(long_wins):<3} wins | Win Rate: {(len(long_wins)/len(long_trades)*100.0 if long_trades else 0):>6.2f}% | Net PnL: ${sum(t.net_pnl for t in long_trades):>+10.2f} ({(sum(t.net_pnl for t in long_trades)/initial_equity*100):>+6.2f}%)")
    print(f" SHORT Setups : {len(short_trades):<3} trades | {len(short_wins):<3} wins | Win Rate: {(len(short_wins)/len(short_trades)*100.0 if short_trades else 0):>6.2f}% | Net PnL: ${sum(t.net_pnl for t in short_trades):>+10.2f} ({(sum(t.net_pnl for t in short_trades)/initial_equity*100):>+6.2f}%)")

    # Top Performing Symbols
    sym_perf = {}
    for t in eval_trades:
        if t.symbol not in sym_perf:
            sym_perf[t.symbol] = {"trades": 0, "wins": 0, "pnl": 0.0}
        sym_perf[t.symbol]["trades"] += 1
        if t.result == "WIN":
            sym_perf[t.symbol]["wins"] += 1
        sym_perf[t.symbol]["pnl"] += t.net_pnl

    sorted_syms = sorted(sym_perf.items(), key=lambda x: x[1]["pnl"], reverse=True)
    print("\n TOP PERFORMING COINS IN UNIVERSE:")
    print("-" * 105)
    for sym, data in sorted_syms[:8]:
        wr = (data["wins"] / data["trades"]) * 100.0
        print(f"  {sym:<12}: {data['trades']:<2} trades | {data['wins']:<2} wins ({wr:5.1f}%) | Net PnL: ${data['pnl']:>+8.2f}")

    # Detailed Trade Log
    print("\n[4/4] COMPLETE 100-TRADE AUDIT LOG (CHRONOLOGICAL):")
    print("=" * 105)
    print(f" {'#':<4} {'Symbol':<10} {'Side':<6} {'Entry Price':<12} {'SL Price':<12} {'TP Price':<12} {'RR':<6} {'Score':<6} {'Result':<6} {'Net PnL ($)':<12} {'Return (%)'}")
    print("-" * 105)

    running_eq = initial_equity
    for idx, t in enumerate(eval_trades, 1):
        trade_ret_pct = (t.net_pnl / initial_equity) * 100.0
        running_eq += t.net_pnl
        pnl_str = f"${t.net_pnl:+,.2f}"
        ret_str = f"{trade_ret_pct:+.2f}%"
        res_tag = "[WIN]" if t.result == "WIN" else "[LOSS]"
        print(f" {idx:<4} {t.symbol:<10} {t.side:<6} ${t.entry_price:<11.4f} ${t.sl_price:<11.4f} ${t.tp_price:<11.4f} {t.rr:<6.2f} {t.setup_score:<6} {res_tag:<6} {pnl_str:<12} {ret_str}")

    print("=" * 105 + "\n")


if __name__ == "__main__":
    run_100_pair_analysis(target_trade_count=100, initial_equity=10000.0)
