"""
Main CLI Application & Runner
Binance USDT-M Futures Automated FVG Trading Bot (Version 1)
"""

import argparse
import sys
import time
from typing import Dict, List
from config import BotConfig
from binance_client import BinanceFuturesClient
from database import BotDatabase
from risk_manager import RiskManager, SymbolSpecs
from order_executor import OrderExecutor
from fvg_state_machine import SymbolStateMachine
from backtester import BacktestEngine, BacktestMetrics
from data_downloader import DataDownloader
from dashboard import TerminalDashboard


def run_backtest_suite(config: BotConfig, initial_equity: float = 10000.0) -> None:
    """
    Runs multi-symbol backtest with 60% Train / 20% Validation / 20% Out-of-Sample Split (Section 69).
    """
    print("\n" + "=" * 90)
    print("  EXECUTING COMPREHENSIVE FVG BACKTEST SUITE (ZERO LOOK-AHEAD)")
    print("=" * 90)

    downloader = DataDownloader()
    base_prices = {
        "BTCUSDT": 65000.0, "ETHUSDT": 3500.0, "BNBUSDT": 580.0, "SOLUSDT": 140.0,
        "XRPUSDT": 0.60, "ADAUSDT": 0.45, "DOGEUSDT": 0.12, "AVAXUSDT": 28.0,
        "LINKUSDT": 14.0, "DOTUSDT": 6.5
    }

    full_datasets = {}
    print("Loading multi-timeframe datasets for 10 pairs (4H, 1H, 15M, 5M)...")
    for sym in config.SYMBOLS:
        bp = base_prices.get(sym, 100.0)
        full_datasets[sym] = downloader.get_or_load_dataset(sym, base_price=bp, num_5m_bars=6000)
        print(f" -> {sym:<10}: 4H={len(full_datasets[sym]['4h'])}, 1H={len(full_datasets[sym]['1h'])}, 15M={len(full_datasets[sym]['15m'])}, 5M={len(full_datasets[sym]['5m'])} bars")

    engine = BacktestEngine(config, initial_equity=initial_equity)

    # 1. Full Dataset Run
    print("\n[1/3] Running Full Multi-Timeframe Dataset Backtest (Zero Look-Ahead)...")
    full_metrics, full_trades = engine.run(full_datasets, split_name="FULL")

    # 2. Split 60% Dev / 20% Val / 20% Out-of-Sample (Section 69)
    print("[2/3] Partitioning Trades into 60% Development / 20% Validation / 20% Out-of-Sample...")
    if full_trades:
        first_ts = full_trades[0].entry_time
        last_ts = full_trades[-1].entry_time
        total_time_span = max(1, last_ts - first_ts)
        ts_dev_end = first_ts + int(total_time_span * 0.60)
        ts_val_end = first_ts + int(total_time_span * 0.80)

        dev_trades = [t for t in full_trades if t.entry_time <= ts_dev_end]
        val_trades = [t for t in full_trades if ts_dev_end < t.entry_time <= ts_val_end]
        oos_trades = [t for t in full_trades if t.entry_time > ts_val_end]

        dev_metrics = engine._calculate_metrics(dev_trades, initial_equity, initial_equity + sum(t.net_pnl for t in dev_trades), [initial_equity])
        val_metrics = engine._calculate_metrics(val_trades, initial_equity, initial_equity + sum(t.net_pnl for t in val_trades), [initial_equity])
        oos_metrics = engine._calculate_metrics(oos_trades, initial_equity, initial_equity + sum(t.net_pnl for t in oos_trades), [initial_equity])
    else:
        dev_metrics = BacktestMetrics()
        val_metrics = BacktestMetrics()
        oos_metrics = BacktestMetrics()

    print("[3/3] Generating Detailed Performance & Expectancy Analytics...")
    _print_performance_report(full_metrics, oos_metrics)


def _print_performance_report(m_full: BacktestMetrics, m_oos: BacktestMetrics) -> None:
    print("\n" + "=" * 90)
    print("                      BACKTEST PERFORMANCE REPORT (SECTION 65 & 66)")
    print("=" * 90)

    print(f" {'Metric':<30} | {'Full Dataset (100%)':<25} | {'Out-of-Sample (20% Unseen)':<25}")
    print("-" * 90)
    print(f" {'Total Completed Trades':<30} | {m_full.total_trades:<25} | {m_oos.total_trades:<25}")
    print(f" {'Wins / Losses':<30} | {f'{m_full.wins} / {m_full.losses}':<25} | {f'{m_oos.wins} / {m_oos.losses}':<25}")
    print(f" {'Win Rate (%)':<30} | {f'{m_full.win_rate:.2f}%':<25} | {f'{m_oos.win_rate:.2f}%':<25}")
    print(f" {'Profit Factor':<30} | {f'{m_full.profit_factor:.2f}':<25} | {f'{m_oos.profit_factor:.2f}':<25}")
    print(f" {'Average R (Risk/Reward)':<30} | {f'{m_full.avg_r:.2f}':<25} | {f'{m_oos.avg_r:.2f}':<25}")
    print(f" {'Starting Equity':<30} | {f'${m_full.starting_equity:,.2f}':<25} | {f'${m_oos.starting_equity:,.2f}':<25}")
    print(f" {'Final Equity':<30} | {f'${m_full.final_equity:,.2f}':<25} | {f'${m_oos.final_equity:,.2f}':<25}")
    print(f" {'Net PnL ($)':<30} | {f'${m_full.net_pnl:+,.2f}':<25} | {f'${m_oos.net_pnl:+,.2f}':<25}")
    print(f" {'Return on Equity (%)':<30} | {f'{m_full.return_pct:+.2f}%':<25} | {f'{m_oos.return_pct:+.2f}%':<25}")
    print(f" {'Gross Profit':<30} | {f'${m_full.gross_profit:,.2f}':<25} | {f'${m_oos.gross_profit:,.2f}':<25}")
    print(f" {'Gross Loss':<30} | {f'${m_full.gross_loss:,.2f}':<25} | {f'${m_oos.gross_loss:,.2f}':<25}")
    print(f" {'Total Trading Fees':<30} | {f'${m_full.total_fees:,.2f}':<25} | {f'${m_oos.total_fees:,.2f}':<25}")
    print(f" {'Total Slippage & Funding':<30} | {f'${(m_full.total_slippage + m_full.total_funding):,.2f}':<25} | {f'${(m_oos.total_slippage + m_oos.total_funding):,.2f}':<25}")
    print(f" {'Expectancy (Gross)':<30} | {f'${m_full.expectancy_gross:+,.2f}':<25} | {f'${m_oos.expectancy_gross:+,.2f}':<25}")
    print(f" {'Expectancy (Net after costs)':<30} | {f'${m_full.expectancy_net:+,.2f}':<25} | {f'${m_oos.expectancy_net:+,.2f}':<25}")
    print(f" {'Max Drawdown (%)':<30} | {f'{m_full.max_drawdown_pct:.2f}% (${m_full.max_drawdown_amount:,.2f})':<25} | {f'{m_oos.max_drawdown_pct:.2f}%':<25}")
    print(f" {'Max Consecutive Losses':<30} | {m_full.max_consecutive_losses:<25} | {m_oos.max_consecutive_losses:<25}")

    # Section 67: FVG Size Breakdown
    print("\n" + "-" * 90)
    print(" SECTION 67: FVG SIZE PERFORMANCE BREAKDOWN")
    print("-" * 90)
    print(f" {'FVG Size Category':<25} | {'Trades':<8} | {'Wins':<6} | {'Win Rate':<12} | {'Net PnL'}")
    for cat, data in m_full.fvg_size_breakdown.items():
        print(f" {cat:<25} | {data['trades']:<8} | {data['wins']:<6} | {data['win_rate']:<10.2f}% | ${data['net_pnl']:+,.2f}")

    # Section 68: FVG Age Breakdown
    print("\n" + "-" * 90)
    print(" SECTION 68: FVG AGE PERFORMANCE BREAKDOWN")
    print("-" * 90)
    print(f" {'FVG Age Category':<25} | {'Trades':<8} | {'Wins':<6} | {'Win Rate':<12} | {'Net PnL'}")
    for cat, data in m_full.fvg_age_breakdown.items():
        print(f" {cat:<25} | {data['trades']:<8} | {data['wins']:<6} | {data['win_rate']:<10.2f}% | ${data['net_pnl']:+,.2f}")

    # Side Breakdown (Long vs Short)
    print("\n" + "-" * 90)
    print(" DIRECTIONAL BREAKDOWN (LONG vs SHORT)")
    print("-" * 90)
    for side, data in m_full.side_breakdown.items():
        print(f" {side:<25} | {data['trades']:<8} trades | {data['wins']:<6} wins | {data['win_rate']:<10.2f}% WR | Net: ${data['net_pnl']:+,.2f}")

    print("=" * 90 + "\n")


def run_live_or_sim_loop(config: BotConfig, max_cycles: Optional[int] = None) -> None:
    """Executes the live/testnet/paper/dry-run polling and dashboard loop."""
    print("\n" + "=" * 90)
    print(f"  INITIALIZING BOT IN MODE: {config.get_mode_name()}")
    print("=" * 90)

    if config.LIVE_TRADING:
        config.validate_safety()
        print("\n [!] LIVE TRADING ENABLED ON BINANCE USDT-M FUTURES [!]")
        print(" [!] Risk per trade is strictly capped at 1% of account equity.")
        print(" [!] All SL and TP orders are submitted directly to Binance exchange servers.\n")

    client = BinanceFuturesClient(
        api_key=config.BINANCE_API_KEY,
        api_secret=config.BINANCE_API_SECRET,
        testnet=config.BINANCE_TESTNET
    )
    db = BotDatabase(config.DATABASE_PATH)
    risk_mgr = RiskManager(
        risk_per_trade=config.RISK_PER_TRADE,
        max_daily_loss=config.MAX_DAILY_LOSS,
        max_consecutive_losses=config.MAX_CONSECUTIVE_LOSSES,
        cooldown_hours=config.CONSECUTIVE_LOSS_COOLDOWN_HOURS,
        max_daily_trades=config.MAX_DAILY_TRADES,
        max_open_positions=config.MAX_OPEN_POSITIONS,
        default_leverage=config.DEFAULT_LEVERAGE,
        sessions=config.TRADING_SESSIONS
    )
    executor = OrderExecutor(config, client, risk_mgr, db)
    dashboard = TerminalDashboard(config)
    downloader = DataDownloader()

    state_machines = {sym: SymbolStateMachine(sym) for sym in config.SYMBOLS}

    # Fetch live balance if live/testnet credentials are provided
    account_equity = 10000.0
    if config.LIVE_TRADING or not config.DRY_RUN:
        try:
            live_bal = client.get_account_balance()
            if live_bal > 0:
                account_equity = live_bal
                print(f" -> Live Binance USDT-M Futures Equity: ${account_equity:,.2f} USDT")
        except Exception as e:
            print(f" -> Warning: Could not fetch live balance ({str(e)}). Using ${account_equity:,.2f}")

    print("Retrieving exchange specs for top 10 symbols from Binance...")
    try:
        specs = client.get_exchange_info(config.SYMBOLS)
    except Exception:
        specs = {sym: SymbolSpecs(symbol=sym) for sym in config.SYMBOLS}

    print("Syncing initial multi-timeframe candles...")
    for sym in config.SYMBOLS:
        try:
            if config.LIVE_TRADING:
                c4 = client.get_klines(sym, "4h", limit=50)
                c1 = client.get_klines(sym, "1h", limit=100)
                c15 = client.get_klines(sym, "15m", limit=150)
                c5 = client.get_klines(sym, "5m", limit=200)
                downloader.save_candles_to_disk(sym, "4h", c4)
                downloader.save_candles_to_disk(sym, "1h", c1)
                downloader.save_candles_to_disk(sym, "15m", c15)
                downloader.save_candles_to_disk(sym, "5m", c5)
            else:
                downloader.get_or_load_dataset(sym, base_price=1000.0, num_5m_bars=500)
        except Exception:
            downloader.get_or_load_dataset(sym, base_price=1000.0, num_5m_bars=500)

    cycle = 0
    while True:
        cycle += 1
        if max_cycles and cycle > max_cycles:
            break

        now_ts = int(time.time() * 1000)

        # Refresh equity periodically
        if config.LIVE_TRADING and cycle % 10 == 0:
            try:
                live_bal = client.get_account_balance()
                if live_bal > 0:
                    account_equity = live_bal
            except Exception:
                pass

        for sym in config.SYMBOLS:
            try:
                if config.LIVE_TRADING:
                    c4 = client.get_klines(sym, "4h", limit=50)
                    c1 = client.get_klines(sym, "1h", limit=100)
                    c15 = client.get_klines(sym, "15m", limit=150)
                    c5 = client.get_klines(sym, "5m", limit=200)
                else:
                    tfs = downloader.get_or_load_dataset(sym)
                    c4 = tfs["4h"]
                    c1 = tfs["1h"]
                    c15 = tfs["15m"]
                    c5 = tfs["5m"]

                curr_p = c5[-1].close if c5 else 100.0
                sm = state_machines[sym]

                setup = sm.update(
                    candles_4h=c4,
                    candles_1h=c1,
                    candles_15m=c15,
                    candles_5m=c5,
                    current_price=curr_p,
                    funding_rate=config.DEFAULT_FUNDING_RATE,
                    min_fvg_atr=config.MIN_FVG_ATR,
                    impulse_min_atr=config.IMPULSE_MIN_ATR,
                    min_rr=config.MIN_RR,
                    min_score=config.MIN_SETUP_SCORE,
                    max_entry_dev_atr=config.MAX_ENTRY_DEVIATION_ATR,
                    sl_atr_buffer=config.SL_ATR_BUFFER,
                    swing_length=config.SWING_LENGTH
                )

                if setup and setup.is_valid and sym not in executor.active_positions:
                    success, reason = executor.execute_trade(setup, specs.get(sym, SymbolSpecs(symbol=sym)), account_equity, curr_p, now_ts)
                    if success:
                        print(f"\n >>> EXECUTED {setup.side} on {sym} @ ${setup.entry_price:.4f} | SL=${setup.sl_price:.4f} | TP=${setup.tp_price:.4f} <<< \n")

            except Exception as err:
                state_machines[sym].status_message = f"Syncing error: {str(err)[:30]}"

        # Render Dashboard
        view = dashboard.render(
            risk_mgr=risk_mgr,
            state_machines=state_machines,
            active_positions=executor.active_positions,
            account_equity=account_equity
        )
        print("\033[H\033[J", end="")  # Clear terminal
        print(view)
        time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description="Binance USDT-M Futures Automated FVG Trading Bot")
    parser.add_argument("--mode", choices=["backtest", "dry-run", "paper", "testnet", "live"], default="backtest")
    parser.add_argument("--equity", type=float, default=10000.0, help="Initial Account Equity in USDT")
    parser.add_argument("--cycles", type=int, default=3, help="Max monitoring cycles to run for live/dry-run/paper")
    args = parser.parse_args()

    config = BotConfig()

    if args.mode == "backtest":
        run_backtest_suite(config, initial_equity=args.equity)
    elif args.mode == "dry-run":
        config.DRY_RUN = True
        config.PAPER_TRADING = False
        config.LIVE_TRADING = False
        run_live_or_sim_loop(config, max_cycles=args.cycles)
    elif args.mode == "paper":
        config.DRY_RUN = False
        config.PAPER_TRADING = True
        config.LIVE_TRADING = False
        run_live_or_sim_loop(config, max_cycles=args.cycles)
    elif args.mode == "testnet":
        config.DRY_RUN = False
        config.PAPER_TRADING = False
        config.BINANCE_TESTNET = True
        config.LIVE_TRADING = False
        run_live_or_sim_loop(config, max_cycles=args.cycles)
    elif args.mode == "live":
        config.DRY_RUN = False
        config.PAPER_TRADING = False
        config.BINANCE_TESTNET = False
        config.LIVE_TRADING = True
        run_live_or_sim_loop(config, max_cycles=args.cycles)


if __name__ == "__main__":
    main()
