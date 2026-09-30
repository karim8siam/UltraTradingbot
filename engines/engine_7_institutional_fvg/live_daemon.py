"""
Live Daemon Runner for Binance USDT-M Futures FVG Bot
Runs continuously in background, auto-reconnects on network drops, and logs to bot_live.log.
"""

import os
import sys
import time
import traceback
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import BotConfig
from binance_client import BinanceFuturesClient
from database import BotDatabase
from risk_manager import RiskManager, SymbolSpecs
from order_executor import OrderExecutor
from fvg_state_machine import SymbolStateMachine
from dashboard import TerminalDashboard


def log_message(msg: str, log_file: str = "bot_live.log") -> None:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    formatted = f"[{now_str}] {msg}"
    print(formatted)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def run_daemon():
    config = BotConfig()
    config.validate_safety()

    log_message("=" * 80)
    log_message("STARTING BINANCE USDT-M FUTURES FVG TRADING BOT (LIVE DAEMON)")
    log_message(f"Risk per trade: {config.RISK_PER_TRADE * 100:.1f}% max equity risk | Leverage: {config.DEFAULT_LEVERAGE}x fixed")
    log_message(f"Entry Mode: MARKET (instant) | SL/TP Ratio: 1:2 (Risk $1 -> Win $2) | Session Exit: {config.TARGET_SESSION_PNL_PCT * 100:.0f}% total PnL")
    log_message(f"Monitoring Pairs ({len(config.SYMBOLS)}): {', '.join(config.SYMBOLS)}")
    log_message("=" * 80)

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
    state_machines = {sym: SymbolStateMachine(sym) for sym in config.SYMBOLS}

    # Fetch initial balance
    account_equity = 12.07
    try:
        live_bal = client.get_account_balance()
        if live_bal > 0:
            account_equity = live_bal
            log_message(f"Connected to Binance. Live Futures Equity: ${account_equity:,.2f} USDT")
    except Exception as e:
        log_message(f"Initial balance fetch warning: {str(e)}. Using fallback: ${account_equity:,.2f} USDT")

    # Fetch exchange specs
    log_message("Retrieving Binance Futures exchange specifications & tick/lot sizes...")
    try:
        specs = client.get_exchange_info(config.SYMBOLS)
        log_message(f"Exchange specifications cached for {len(specs)} symbols.")
    except Exception as e:
        log_message(f"Exchange info error: {str(e)}. Initializing default specs.")
        specs = {sym: SymbolSpecs(symbol=sym) for sym in config.SYMBOLS}

    cycle = 0
    while True:
        cycle += 1
        now_ts = int(time.time() * 1000)

        # Refresh equity every 10 cycles (~1 minute)
        if cycle % 10 == 0:
            try:
                live_bal = client.get_account_balance()
                if live_bal > 0:
                    account_equity = live_bal
            except Exception:
                pass

        # 1. Synchronize open positions directly from Binance Futures
        open_pos_map = executor.sync_active_positions()
        num_open = len(executor.active_positions)

        # 2. Check 2% PnL Target exit — close position if target met
        if num_open > 0:
            pnl_msg = executor.check_and_close_pnl_target(
                account_equity=account_equity,
                target_pct=config.TARGET_SESSION_PNL_PCT
            )
            if pnl_msg:
                log_message(f"[TARGET HIT] {pnl_msg}")
                try:
                    account_equity = client.get_account_balance()
                except Exception:
                    pass
                num_open = len(executor.active_positions)

        # 3. Position Capacity Check
        if num_open >= config.MAX_OPEN_POSITIONS:
            active_syms = list(executor.active_positions.keys())
            curr_pnl = sum(p.get("unrealized_profit", 0.0) for p in open_pos_map.values())
            target_pnl = account_equity * config.TARGET_SESSION_PNL_PCT
            if cycle % 6 == 0:  # log status every ~30 seconds
                log_message(f"[POSITIONS ACTIVE ({num_open}/{config.MAX_OPEN_POSITIONS})] {', '.join(active_syms)} | Unrealized PnL: ${curr_pnl:+.4f} USDT | Target Exit: ${target_pnl:.4f} USDT (+2%)")
            time.sleep(5)
            continue

        for sym in config.SYMBOLS:
            try:
                # Fetch live closed candles from Binance
                c4 = client.get_klines(sym, "4h", limit=50)
                c1 = client.get_klines(sym, "1h", limit=100)
                c15 = client.get_klines(sym, "15m", limit=150)
                c5 = client.get_klines(sym, "5m", limit=200)

                if not c5 or not c15 or not c1 or not c4:
                    continue

                curr_p = c5[-1].close
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
                    log_message(f"*** VALID SETUP DETECTED on {sym} ({setup.side}) ***")
                    log_message(f" -> Score: {setup.setup_score} | Planned Entry: ${setup.entry_price:.4f} | SL: ${setup.sl_price:.4f} | TP: ${setup.tp_price:.4f} | RR: {setup.rr:.2f}")

                    success, reason = executor.execute_trade(
                        setup,
                        specs.get(sym, SymbolSpecs(symbol=sym)),
                        account_equity,
                        curr_p,
                        now_ts
                    )
                    if success:
                        log_message(f"[SUCCESS] Executed {setup.side} on {sym}. Server-side SL & TP submitted to Binance cloud.")
                    else:
                        log_message(f"[REJECTED] Trade not executed: {reason}")

            except Exception as err:
                state_machines[sym].status_message = f"Error: {str(err)[:30]}"

        # Periodic heartbeat log every 100 cycles (~10 minutes)
        if cycle % 100 == 0:
            log_message(f"Heartbeat: Cycle #{cycle} | Equity: ${account_equity:,.2f} USDT | Open Positions: {len(executor.active_positions)}")

        time.sleep(5)


if __name__ == "__main__":
    try:
        run_daemon()
    except KeyboardInterrupt:
        log_message("Bot stopped by user.")
    except Exception as e:
        log_message(f"Fatal error: {str(e)}\n{traceback.format_exc()}")
