"""
Master Daemon Orchestrator for Binance Futures GFS Trading Bot
Synchronizes multi-symbol data, executes GFS logic, and manages lifecycle states.
"""

import time
import sys
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from config import (
    BotConfig, DEFAULT_SYMBOLS, TIMEFRAME_GRANDFATHER,
    TIMEFRAME_FATHER, TIMEFRAME_SON, MAX_SETUP_AGE
)
from indicators import Candle
from gfs_strategy import GFSStrategyEngine, GFSSetup, TrendDirection
from risk_manager import RiskManager, SymbolFilters
from state_machine import SymbolStateMachine, BotState
from database import GFSDatabase
from binance_client import BinanceFuturesClient
from order_manager import OrderManager
from paper_trader import PaperTrader
from dashboard import GFSDashboard


class GFSBotDaemon:
    """
    Main Trading Bot Service coordinating 10 symbols across 1D -> 4H -> 15M.
    """

    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or BotConfig()
        self.db = GFSDatabase(self.config.db_path)
        self.strategy = GFSStrategyEngine()
        self.risk_manager = RiskManager(
            starting_equity=13.34,
            risk_per_trade=self.config.risk_per_trade,
            max_daily_loss=self.config.max_daily_loss,
            max_consecutive_losses=self.config.max_consecutive_losses,
            max_daily_trades=self.config.max_daily_trades,
            max_open_positions=self.config.max_open_positions,
            default_leverage=self.config.default_leverage,
            enforce_sessions=self.config.enforce_sessions,
            enable_stop_loss=self.config.enable_stop_loss,
            target_profit_equity_pct=self.config.target_profit_equity_pct,
            stop_loss_equity_pct=self.config.stop_loss_equity_pct
        )

        self.client = BinanceFuturesClient(
            api_key=self.config.api_key,
            api_secret=self.config.api_secret,
            testnet=self.config.binance_testnet
        )

        self.order_manager = OrderManager(
            client=self.client,
            db=self.db,
            risk_manager=self.risk_manager,
            paper_trading=self.config.paper_trading,
            use_market_entry=self.config.use_market_entry,
            enable_stop_loss=self.config.enable_stop_loss,
            target_profit_equity_pct=self.config.target_profit_equity_pct,
            stop_loss_equity_pct=self.config.stop_loss_equity_pct,
            margin_type=self.config.margin_type
        )

        self.paper_trader = PaperTrader(
            db=self.db,
            risk_manager=self.risk_manager,
            initial_balance=10000.0
        )

        self.state_machines: Dict[str, SymbolStateMachine] = {
            sym: SymbolStateMachine(sym) for sym in self.config.symbols
        }

        self.candle_cache: Dict[str, Dict[str, List[Candle]]] = {
            sym: {"1d": [], "4h": [], "15m": []} for sym in self.config.symbols
        }

        self.symbol_dashboard_data: Dict[str, Dict[str, Any]] = {}
        self.is_running: bool = False

    def get_current_equity(self) -> float:
        if self.config.paper_trading:
            return self.paper_trader.virtual_balance
        try:
            acc = self.client.fetch_account()
            if isinstance(acc, dict) and not acc.get("error"):
                return float(acc.get("totalMarginBalance", self.risk_manager.daily_state.current_equity))
        except Exception:
            pass
        return self.risk_manager.daily_state.current_equity

    def initialize_exchange_info(self):
        """
        Fetches Binance symbol filters (precision, step size, min qty).
        """
        print("[INIT] Fetching dynamic exchange info from Binance Futures...", flush=True)
        filters = self.client.fetch_exchange_info()
        for sym in self.config.symbols:
            if sym in filters:
                self.risk_manager.set_symbol_filter(sym, filters[sym])
                print(f"  -> {sym}: stepSize={filters[sym].step_size}, minQty={filters[sym].min_qty}, tickSize={filters[sym].tick_size}", flush=True)
            else:
                print(f"  [WARN] Symbol {sym} not found in exchangeInfo, using default filters.", flush=True)

        # Sync live account balance and any existing open positions
        if not self.config.paper_trading:
            live_eq = self.get_current_equity()
            self.risk_manager.daily_state.starting_equity = live_eq
            self.risk_manager.daily_state.current_equity = live_eq
            print(f"[INIT] Live Binance Futures Account Margin Balance: ${live_eq:.4f} USDT", flush=True)

            try:
                live_positions = self.client.fetch_positions()
                for pos in live_positions:
                    amt = float(pos.get("positionAmt", 0.0))
                    if abs(amt) > 0:
                        psym = pos.get("symbol")
                        entry_p = float(pos.get("entryPrice", 0.0))
                        tp_p = self.order_manager.calculate_tp_price(
                            psym,
                            TrendDirection.BULLISH if amt > 0 else TrendDirection.BEARISH,
                            entry_p,
                            abs(amt),
                            live_eq
                        )
                        record = {
                            "trade_id": f"existing_{psym}",
                            "symbol": psym,
                            "direction": "BULLISH" if amt > 0 else "BEARISH",
                            "status": "ACTIVE",
                            "entry_price": entry_p,
                            "position_size": abs(amt),
                            "take_profit": tp_p,
                            "stop_loss": 0.0,
                            "entry_time": int(time.time() * 1000)
                        }
                        self.risk_manager.add_open_position(psym, record)
                        print(f"[INIT] Detected existing live position: {psym} (Qty: {amt}, Entry: {entry_p})", flush=True)
            except Exception as e:
                print(f"[INIT WARN] Could not check existing positions: {e}", flush=True)

    def _fetch_with_retry(self, symbol: str, interval: str, limit: int = 300) -> List[Candle]:
        for attempt in range(5):
            try:
                candles = self.client.fetch_klines(symbol, interval, limit=limit)
                if len(candles) >= 50:
                    time.sleep(0.1)
                    return candles
            except Exception:
                pass
            time.sleep(0.5)
        return []

    def sync_historical_data(self):
        """
        Downloads initial closed candles for 1D, 4H, and 15M across all symbols.
        """
        print("[SYNC] Downloading initial historical candles (1D, 4H, 15M)...", flush=True)
        for sym in self.config.symbols:
            try:
                d_candles = self._fetch_with_retry(sym, TIMEFRAME_GRANDFATHER, limit=250)
                h4_candles = self._fetch_with_retry(sym, TIMEFRAME_FATHER, limit=300)
                m15_candles = self._fetch_with_retry(sym, TIMEFRAME_SON, limit=300)

                # Keep strictly closed candles
                self.candle_cache[sym]["1d"] = d_candles[:-1] if d_candles else []
                self.candle_cache[sym]["4h"] = h4_candles[:-1] if h4_candles else []
                self.candle_cache[sym]["15m"] = m15_candles[:-1] if m15_candles else []
                c_1d = len(self.candle_cache[sym]['1d'])
                c_4h = len(self.candle_cache[sym]['4h'])
                c_15m = len(self.candle_cache[sym]['15m'])
                print(f"  -> {sym}: Loaded 1D ({c_1d}), 4H ({c_4h}), 15M ({c_15m})", flush=True)
            except Exception as e:
                print(f"  [ERROR] Failed syncing data for {sym}: {e}", flush=True)

    def process_symbol_cycle(self, symbol: str):
        """
        Executes complete GFS evaluation cycle for a single symbol.
        """
        d_candles = self.candle_cache[symbol]["1d"]
        h4_candles = self.candle_cache[symbol]["4h"]
        m15_candles = self.candle_cache[symbol]["15m"]

        sm = self.state_machines[symbol]
        now_ts = int(time.time() * 1000)

        # 1. Grandfather 1D Trend Check
        d_trend, d_ema50, d_ema200, _ = self.strategy.evaluate_1d_trend(d_candles)

        # 2. Father 4H Trend Check & Pullback Zone
        h4_trend, h4_ema20, h4_ema50, _ = self.strategy.evaluate_4h_trend(h4_candles)
        in_pb_zone, pb_invalid, _, _ = self.strategy.check_4h_pullback_zone(h4_candles, h4_trend)

        # Update symbol dashboard status
        self.symbol_dashboard_data[symbol] = {
            "1d_trend": d_trend.value,
            "4h_trend": h4_trend.value,
            "pullback": "YES" if in_pb_zone else "NO",
            "15m_status": "IDLE",
            "score": 0,
            "rr": 0.0,
            "state": sm.current_state.value
        }

        # Check Invalidation
        if pb_invalid:
            sm.transition_to(BotState.INVALIDATED, "4H closed beyond EMA50 invalidating pullback")
            self.symbol_dashboard_data[symbol]["state"] = "INVALIDATED"
            return

        # Check Trend Alignment
        if d_trend == TrendDirection.NEUTRAL or h4_trend == TrendDirection.NEUTRAL:
            sm.transition_to(BotState.WAITING, "Trend Neutral")
            return

        if d_trend != h4_trend:
            sm.transition_to(BotState.WAITING, "1D and 4H Misaligned")
            return

        # Pullback Zone check
        if not in_pb_zone:
            sm.transition_to(BotState.WAITING_FOR_PULLBACK, "Waiting for 4H price to enter EMA20-EMA50")
            return

        # Transition to 15M Monitoring
        sm.transition_to(BotState.SON_TIMEFRAME_MONITORING, "In 4H Pullback Zone, scanning 15M candles")
        self.symbol_dashboard_data[symbol]["15m_status"] = "SCANNING"

        # Check setup expiration (20 candles)
        if sm.increment_setup_age(MAX_SETUP_AGE):
            self.symbol_dashboard_data[symbol]["state"] = "EXPIRED"
            return

        # 3. Evaluate 15M Entry Setup
        setup, reason = self.strategy.evaluate_15m_entry_setup(
            symbol=symbol,
            daily_candles=d_candles,
            four_hour_candles=h4_candles,
            son_candles=m15_candles
        )

        if setup is None:
            self.db.record_rejection(symbol, "15M_EVALUATION", reason)
            return

        # GFS Signal Approved!
        self.symbol_dashboard_data[symbol]["15m_status"] = "BREAK_CONFIRMED"
        self.symbol_dashboard_data[symbol]["score"] = setup.setup_score
        self.symbol_dashboard_data[symbol]["rr"] = setup.risk_reward

        sm.transition_to(BotState.STRUCTURE_SHIFT_CONFIRMED, "15M Break and Displacement Confirmed")

        # 4. Risk Validation & Position Sizing
        current_eq = self.get_current_equity()
        allowed, risk_reason = self.risk_manager.check_trade_allowed(symbol, current_eq, now_ts)
        if not allowed:
            self.db.record_rejection(symbol, "RISK_MANAGER", risk_reason)
            return

        pos_qty, risk_amt, notional, size_status = self.risk_manager.calculate_position_size(
            symbol=symbol,
            equity=current_eq,
            entry_price=setup.entry_price,
            stop_loss=setup.stop_loss
        )
        if size_status != "OK":
            self.db.record_rejection(symbol, "POSITION_SIZING", size_status)
            return

        # 5. Order Execution
        sm.transition_to(BotState.ENTRY_SUBMITTED, "Submitting entry order")
        if self.config.paper_trading:
            order_id = self.paper_trader.submit_virtual_order(setup, pos_qty)
            sm.active_order_id = order_id
        else:
            success, order_id, exec_msg = self.order_manager.submit_entry_order(setup, pos_qty, current_eq)
            if success:
                sm.active_order_id = order_id
                if self.config.use_market_entry:
                    sm.transition_to(BotState.POSITION_ACTIVE, "Market entry filled and TP placed")
            else:
                self.db.record_rejection(symbol, "ORDER_MANAGER", exec_msg)
                sm.transition_to(BotState.INVALIDATED, exec_msg)

    def run_single_loop(self):
        """
        Executes one polling and update iteration for all symbols.
        """
        # 1. Update 15M candles
        for sym in self.config.symbols:
            try:
                latest_15m = self.client.fetch_klines(sym, TIMEFRAME_SON, limit=5)
                if len(latest_15m) >= 2:
                    last_closed = latest_15m[-2] # Closed candle
                    cached = self.candle_cache[sym]["15m"]
                    if not cached or cached[-1].timestamp < last_closed.timestamp:
                        cached.append(last_closed)
                        if len(cached) > 300:
                            self.candle_cache[sym]["15m"] = cached[-300:]
                        # Notify Paper Trader
                        if self.config.paper_trading:
                            self.paper_trader.on_15m_candle_closed(sym, last_closed)

                self.process_symbol_cycle(sym)
            except Exception as e:
                pass

        # 2. Timeout order management (only relevant if limit orders used)
        if not self.config.use_market_entry:
            self.order_manager.cancel_timeout_orders()

        # 3. Live Position Monitoring
        if not self.config.paper_trading and len(self.risk_manager.open_positions) > 0:
            try:
                live_positions = self.client.fetch_positions()
                pos_map = {p["symbol"]: p for p in live_positions if isinstance(p, dict) and "symbol" in p}

                for sym, pos_data in list(self.risk_manager.open_positions.items()):
                    live_pos = pos_map.get(sym)
                    pos_amt = abs(float(live_pos.get("positionAmt", 0.0))) if live_pos else 0.0

                    # If Binance shows 0 position amount, position has exited (TP hit, SL hit, or closed)
                    if pos_amt == 0.0:
                        entry_p = float(pos_data.get("entry_price", 0.0))
                        tp_p = float(pos_data.get("take_profit", entry_p))
                        sl_p = float(pos_data.get("stop_loss", 0.0))
                        qty = float(pos_data.get("position_size", 0.0))
                        direction = pos_data.get("direction", "BULLISH")
                        now_ms = int(time.time() * 1000)

                        # Check remaining open orders to identify whether TP or SL filled
                        open_orders = []
                        try:
                            open_orders = self.client.fetch_open_orders(sym)
                        except Exception:
                            pass

                        # If a STOP_MARKET / _sl_ remains open, TP triggered!
                        # If a TAKE_PROFIT_MARKET / _tp_ remains open, SL triggered!
                        sl_remaining = any(o.get("type") in ("STOP_MARKET", "STOP") or "_sl_" in o.get("clientOrderId", "") for o in open_orders)
                        tp_remaining = any(o.get("type") in ("TAKE_PROFIT_MARKET", "TAKE_PROFIT") or "_tp_" in o.get("clientOrderId", "") for o in open_orders)

                        # Attempt to get exact fill info from Binance user trades
                        user_trades = []
                        try:
                            user_trades = self.client.fetch_user_trades(sym, limit=2)
                        except Exception:
                            pass

                        if user_trades and isinstance(user_trades, list) and len(user_trades) > 0:
                            last_trade = user_trades[-1]
                            exit_p = float(last_trade.get("price", tp_p))
                            pnl = float(last_trade.get("realizedPnl", 0.0))
                            fees = float(last_trade.get("commission", 0.0005 * qty * exit_p))
                            exit_reason = "TAKE_PROFIT_TRIGGERED" if pnl >= 0 else "STOP_LOSS_TRIGGERED"
                        else:
                            if tp_remaining and not sl_remaining and sl_p > 0:
                                exit_p = sl_p
                                exit_reason = "STOP_LOSS_TRIGGERED"
                            else:
                                exit_p = tp_p
                                exit_reason = "TAKE_PROFIT_TRIGGERED"

                            if direction == "BULLISH":
                                pnl = (exit_p - entry_p) * qty
                            else:
                                pnl = (entry_p - exit_p) * qty
                            fees = 0.0005 * qty * exit_p

                        self.db.record_trade_exit(
                            trade_id=pos_data.get("trade_id", f"exit_{sym}"),
                            exit_time=now_ms,
                            exit_price=exit_p,
                            gross_pnl=pnl,
                            fees=fees,
                            funding_cost=0.0,
                            net_pnl=pnl - fees,
                            result="WIN" if pnl > 0 else "LOSS",
                            exit_reason=exit_reason
                        )
                        self.risk_manager.record_trade_closed(pnl, now_ms)
                        self.risk_manager.remove_open_position(sym)
                        if sym in self.state_machines:
                            self.state_machines[sym].transition_to(BotState.WAITING, f"Position closed: {exit_reason}")

                        # Cancel any remaining residual orders for symbol
                        if open_orders:
                            for o in open_orders:
                                try:
                                    self.client.cancel_order(sym, order_id=o.get("orderId"))
                                except Exception:
                                    pass
            except Exception:
                pass

        current_eq = self.get_current_equity()
        open_pos = self.paper_trader.open_positions if self.config.paper_trading else self.risk_manager.open_positions
        daily_pnl = self.risk_manager.daily_state.realized_daily_pnl
        self.db.record_snapshot(
            equity=current_eq,
            available_margin=current_eq,
            daily_pnl=daily_pnl,
            open_positions=len(open_pos),
            consecutive_losses=self.risk_manager.daily_state.consecutive_losses
        )

    def render_dashboard(self):
        current_eq = self.get_current_equity()
        open_pos = self.paper_trader.open_positions if self.config.paper_trading else self.risk_manager.open_positions
        rejections = self.db.get_rejection_counts()
        view = GFSDashboard.render_cli_view(
            mode=self.config.mode_name,
            equity=current_eq,
            daily_pnl=self.risk_manager.daily_state.realized_daily_pnl,
            daily_trades=self.risk_manager.daily_state.daily_trade_count,
            consec_losses=self.risk_manager.daily_state.consecutive_losses,
            symbol_states=self.symbol_dashboard_data,
            open_positions=open_pos,
            rejections=rejections
        )
        if sys.stdout.isatty():
            os.system("clear")
        print(view, flush=True)

    def start(self, poll_interval_sec: int = 10):
        self.is_running = True
        self.initialize_exchange_info()
        self.sync_historical_data()

        print(f"[START] GFS Bot Daemon started in {self.config.mode_name} mode.", flush=True)
        try:
            while self.is_running:
                self.run_single_loop()
                self.render_dashboard()
                time.sleep(poll_interval_sec)
        except KeyboardInterrupt:
            self.is_running = False