import sys
import os
import time
import argparse
import logging
from datetime import datetime, timezone

from config import Config
from database import Database
from market_data.binance_client import BinanceFuturesClient
from market_data.candle_manager import CandleManager
from market_data.historical_fetcher import HistoricalFetcher
from strategy.setup_evaluator import SetupEvaluator
from strategy.state_machine import SymbolStateMachine
from execution.risk_manager import RiskManager
from execution.executor import ExecutionCoordinator
from backtesting.engine import BacktestEngine
from backtesting.split_tester import SplitTester
from ui.dashboard import Dashboard

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("SMC_Bot")

def run_backtest_cli(config: Config, symbol: str, split_test: bool = False):
    print(f"\n[*] Initializing Deterministic SMC Backtest for {symbol}...")
    client = BinanceFuturesClient(is_testnet=False)
    candle_mgr = CandleManager(max_buffer=6000)
    fetcher = HistoricalFetcher(client, candle_mgr)

    print(f"[*] Fetching historical market data from Binance Public Endpoints...")
    fetcher.fetch_all_timeframes_for_symbol(
        symbol=symbol,
        limit_4h=config.WARMUP_CANDLES_4H,
        limit_1h=config.WARMUP_CANDLES_1H,
        limit_15m=config.WARMUP_CANDLES_15M,
        limit_5m=config.WARMUP_CANDLES_5M
    )

    c4h = candle_mgr.get_closed_candles(symbol, "4h")
    c1h = candle_mgr.get_closed_candles(symbol, "1h")
    c15m = candle_mgr.get_closed_candles(symbol, "15m")
    c5m = candle_mgr.get_closed_candles(symbol, "5m")

    print(f"[*] Validated Candle Counts: 4H={len(c4h)}, 1H={len(c1h)}, 15M={len(c15m)}, 5M={len(c5m)}")

    if split_test:
        print(f"[*] Running 60/20/20 Dev/Validation/Out-of-Sample Split Backtests...")
        split_tester = SplitTester(config)
        res = split_tester.run_split_tests(symbol, c4h, c1h, c15m, c5m)
        print("\n" + "=" * 60)
        print(f"  OUT-OF-SAMPLE SPLIT TEST RESULTS FOR {symbol}")
        print("=" * 60)
        for split_name, metrics in [("Development (60%)", res["development_60"]),
                                   ("Validation (20%)", res["validation_20"]),
                                   ("Out-of-Sample (20%)", res["out_of_sample_20"])]:
            print(f"\n--- {split_name} ---")
            print(f"  Total Trades:     {metrics[total_trades]}")
            print(f"  Win Rate:         {metrics[win_rate]:.1f}%")
            print(f"  Net Profit:       ${metrics[net_profit]:+,.2f} ({metrics[return_pct]:+.2f}%)")
            print(f"  Profit Factor:    {metrics[profit_factor]:.2f}")
            print(f"  Max Drawdown:     {metrics[max_drawdown_pct]:.2f}%")
            print(f"  Expectancy (Net): ${metrics[expectancy_net]:+.2f}")
        print("=" * 60)
    else:
        engine = BacktestEngine(config)
        res = engine.run_backtest(symbol, c4h, c1h, c15m, c5m, initial_capital=config.INITIAL_EQUITY)
        m = res["metrics"]
        print("\n" + "=" * 60)
        print(f"  BACKTEST PERFORMANCE SUMMARY: {symbol}")
        print("=" * 60)
        print(f"  Total Trades Executed:   {m[total_trades]}")
        print(f"  Winning Trades:          {m[winning_trades]} ({m[win_rate]:.1f}%)")
        print(f"  Losing Trades:           {m[losing_trades]}")
        print(f"  Net Profit:              ${m[net_profit]:+,.2f} ({m[return_pct]:+.2f}%)")
        print(f"  Gross Profit:            ${m[gross_profit]:,.2f}")
        print(f"  Gross Loss:              ${m[gross_loss]:,.2f}")
        print(f"  Total Fees & Slippage:   ${m[fees]:,.2f}")
        print(f"  Profit Factor:           {m[profit_factor]:.2f}")
        print(f"  Expectancy per Trade:    ${m[expectancy_net]:+.2f}")
        print(f"  Max Drawdown:            {m[max_drawdown_pct]:.2f}% (${m[max_drawdown_dollars]:,.2f})")
        print(f"  Max Consecutive Losses:  {m[max_consecutive_losses]}")
        print(f"  Long Trades (Win Rate):  {m[long_trades]} ({m[long_win_rate]:.1f}%)")
        print(f"  Short Trades (Win Rate): {m[short_trades]} ({m[short_win_rate]:.1f}%)")
        print(f"  Largest Win / Loss:      +${m[largest_winner]:,.2f} / -${abs(m[largest_loser]):,.2f}")
        print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Binance USDT-M Futures Deterministic SMC Trading Bot")
    parser.add_argument("--mode", choices=["dry-run", "paper", "testnet", "live", "backtest", "split-test"], default="dry-run")
    parser.add_argument("--symbol", default="BTCUSDT", help="Symbol for backtest / focus")
    args = parser.parse_args()

    config = Config()

    # Mode Override
    if args.mode == "dry-run":
        config.DRY_RUN = True
        config.PAPER_TRADING = False
        config.LIVE_TRADING = False
    elif args.mode == "paper":
        config.DRY_RUN = False
        config.PAPER_TRADING = True
        config.LIVE_TRADING = False
    elif args.mode == "testnet":
        config.DRY_RUN = False
        config.PAPER_TRADING = False
        config.BINANCE_TESTNET = True
        config.LIVE_TRADING = False
    elif args.mode == "live":
        config.DRY_RUN = False
        config.PAPER_TRADING = False
        config.BINANCE_TESTNET = False
        config.LIVE_TRADING = True
        config.LIVE_TRADING_CONFIRMATION = True

    if args.mode in ("backtest", "split-test"):
        run_backtest_cli(config, args.symbol, split_test=(args.mode == "split-test"))
        return

    # Live / Paper / Dry-Run Multi-Symbol Runner
    print(f"\n[*] Launching SMC Trading Bot in [{config.get_mode_name()}] mode...")
    db = Database(config.DATABASE_PATH)
    client = BinanceFuturesClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET, is_testnet=config.BINANCE_TESTNET)
    candle_mgr = CandleManager()
    fetcher = HistoricalFetcher(client, candle_mgr)
    evaluator = SetupEvaluator(
        min_rr=config.MIN_RR,
        min_score=config.MIN_SETUP_SCORE,
        sl_atr_multiplier=config.SL_ATR_BUFFER_MULTIPLIER,
        max_atr_ratio=config.MAX_ATR_RATIO,
        allowed_sessions=config.ALLOWED_SESSIONS
    )
    risk_mgr = RiskManager(
        risk_per_trade=config.RISK_PER_TRADE,
        max_daily_loss=config.MAX_DAILY_LOSS,
        max_consecutive_losses=config.MAX_CONSECUTIVE_LOSSES,
        cooldown_hours=config.CONSECUTIVE_LOSS_COOLDOWN_HOURS,
        max_daily_trades=config.MAX_DAILY_TRADES,
        max_open_positions=config.MAX_OPEN_POSITIONS,
        default_leverage=config.DEFAULT_LEVERAGE
    )
    coordinator = ExecutionCoordinator(config, db, client, risk_mgr)
    dashboard = Dashboard(config)

    # Initialize State Machines per Symbol
    state_machines = {sym: SymbolStateMachine(sym, evaluator, swing_length=config.SWING_LENGTH) for sym in config.SYMBOLS}

    # Fetch initial warm-up candles for all 10 symbols
    print(f"[*] Warming up historical market data for {len(config.SYMBOLS)} pairs...")
    for sym in config.SYMBOLS:
        fetcher.fetch_all_timeframes_for_symbol(
            sym, limit_4h=50, limit_1h=100, limit_15m=150, limit_5m=200
        )

    # Single iteration dry-run / paper check
    symbol_states_summary = {}
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for sym in config.SYMBOLS:
        sm = state_machines[sym]
        c4h = candle_mgr.get_closed_candles(sym, "4h")
        c1h = candle_mgr.get_closed_candles(sym, "1h")
        c15m = candle_mgr.get_closed_candles(sym, "15m")
        c5m = candle_mgr.get_closed_candles(sym, "5m")

        setup, status = sm.process_candles(c4h, c1h, c15m, c5m)
        symbol_states_summary[sym] = {
            "bias_4h": sm.bias_4h.value,
            "bias_1h": sm.bias_1h.value,
            "state": sm.state.value,
            "reason": sm.last_transition_reason
        }

        if setup:
            has_pos = sym in coordinator.virtual_open_positions
            coordinator.execute_setup(
                setup=setup,
                current_account_equity=coordinator.virtual_equity,
                starting_daily_equity=coordinator.virtual_equity,
                today_realized_pnl=0.0,
                today_trade_count=db.get_daily_trades_count(today_date),
                open_positions_count=len(coordinator.virtual_open_positions),
                has_position_on_symbol=has_pos
            )

    # Render Terminal Dashboard
    account_info = {
        "equity": coordinator.virtual_equity,
        "daily_pnl": 0.0,
        "daily_loss_pct": 0.0,
        "daily_trades": db.get_daily_trades_count(today_date),
        "consecutive_losses": risk_mgr.current_consecutive_losses
    }
    dashboard.render_console(account_info, symbol_states_summary, list(coordinator.virtual_open_positions.values()), [])
    print(f"[*] Verification complete. System ready for continuous automated scanning.\n")

if __name__ == "__main__":
    main()
