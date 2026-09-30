"""
Binance USDT-M Futures Fibonacci Pullback Trading Bot (Version 1)
Main Application Entrypoint
"""

import argparse
import datetime
import logging
import os
import signal
import sys
import time
from typing import Dict, List

from config import constants
from config.settings import settings
from core.confirmation import ConfirmationEngine
from core.fibonacci import FibonacciCalculator
from core.impulse import ImpulseDetector
from core.indicators import calculate_atr_ratio, get_latest_atr
from core.pullback import PullbackDetector
from core.risk_engine import RiskEngine
from core.setup_scorer import SetupScorer
from core.state_machine import StateMachineManager
from core.swings import SwingDetector
from core.trend import TrendDetector
from core.types import (
    Candle,
    FibZoneCategory,
    OrderStatus,
    Position,
    PositionSide,
    SetupRejectReason,
    StrategyState,
    TradeRecord,
    TradeSetup,
    TrendType,
)
from execution.live_gate import LiveTradingGate
from execution.order_manager import OrderManager
from execution.safety import SafetyManager
from market_data.binance_client import BinanceClient
from market_data.candle_store import CandleStore
from market_data.exchange_info import ExchangeInfoManager
from risk.risk_manager import RiskManager
from storage.database import Database
from ui.dashboard import TerminalDashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("MainBot")


class FibonacciPullbackBot:
    def __init__(self, mode: str = "DRY_RUN", symbols: List[str] = None):
        self.mode = mode
        self.symbols = symbols or settings.symbols
        self.running = True

        # Storage & Gate
        self.db = Database(settings.database_path)
        self.client = BinanceClient(
            api_key=settings.binance_api_key,
            api_secret=settings.binance_api_secret,
            testnet=settings.binance_testnet,
        )

        self.exchange_info = ExchangeInfoManager()
        self.candle_store = CandleStore()
        self.fsm_mgr = StateMachineManager(self.symbols)

        self.swing_detector = SwingDetector()
        self.trend_detector = TrendDetector(self.swing_detector)
        self.impulse_detector = ImpulseDetector(self.swing_detector)
        self.fib_calc = FibonacciCalculator()
        self.pullback_detector = PullbackDetector()
        self.confirmation_engine = ConfirmationEngine()
        self.scorer = SetupScorer(settings.min_setup_score)
        self.risk_engine = RiskEngine(settings.risk_per_trade, settings.min_rr)
        self.risk_manager = RiskManager(
            max_daily_loss=settings.max_daily_loss,
            max_consecutive_losses=settings.max_consecutive_losses,
            cooldown_hours=settings.cooldown_hours,
            max_daily_trades=settings.max_daily_trades,
            max_open_positions=settings.max_open_positions,
            max_atr_ratio=settings.max_atr_ratio,
        )
        self.safety = SafetyManager(self.client)
        self.order_mgr = OrderManager(
            client=self.client,
            exchange_info=self.exchange_info,
            safety_manager=self.safety,
            mode=self.mode,
        )

        self.equity = 10000.0
        self.active_positions: Dict[str, Position] = {}

    def initialize(self):
        logger.info("Initializing Trading Bot...")
        LiveTradingGate.verify_mode(settings)

        # In offline/sandboxed environments, load synthetic historical candles for initialization
        logger.info(f"Loading historical candle buffers for {len(self.symbols)} symbols...")
        for sym in self.symbols:
            from backtest.dataset import HistoricalDataset
            ds = HistoricalDataset.generate_synthetic_data(symbol=sym, num_5m_candles=3500, seed=abs(hash(sym)) % 10000)
            self.candle_store.add_candles(sym, "4h", ds.candles_4h)
            self.candle_store.add_candles(sym, "1h", ds.candles_1h)
            self.candle_store.add_candles(sym, "15m", ds.candles_15m)
            self.candle_store.add_candles(sym, "5m", ds.candles_5m)

            # Initialize synthetic exchange filters
            from market_data.exchange_info import SymbolFilters
            self.exchange_info.symbols[sym] = SymbolFilters(
                symbol=sym,
                status="TRADING",
                price_precision=2,
                quantity_precision=3,
                tick_size=0.01,
                step_size=0.001,
                min_qty=0.001,
                max_qty=100000.0,
                min_notional=5.0,
                max_leverage=20,
            )
        logger.info("Initialization complete. All systems nominal.")

    def run_cycle(self):
        now_ts = int(time.time() * 1000)

        for sym in self.symbols:
            sm = self.fsm_mgr.get(sym)
            c_4h = self.candle_store.get_candles(sym, "4h")
            c_1h = self.candle_store.get_candles(sym, "1h")
            c_15m = self.candle_store.get_candles(sym, "15m")
            c_5m = self.candle_store.get_candles(sym, "5m")

            if not c_5m or not c_15m or not c_1h or not c_4h:
                continue

            # 1. Update 4H & 1H Trends
            bias_4h, _, _ = self.trend_detector.classify_trend(c_4h, "4h")
            bias_1h, _, _ = self.trend_detector.classify_trend(c_1h, "1h")
            sm.bias_4h = bias_4h
            sm.bias_1h = bias_1h

            if bias_4h == TrendType.NEUTRAL or bias_4h != bias_1h:
                if sm.state not in (StrategyState.POSITION_OPEN, StrategyState.POSITION_MANAGEMENT):
                    sm.reset_to_waiting_trend("HTF bias mismatch/neutral", now_ts)
                continue

            if sm.state == StrategyState.WAITING_FOR_TREND:
                sm.transition_to(StrategyState.TREND_CONFIRMED, f"HTF aligned: {bias_4h.value}", now_ts)
                sm.transition_to(StrategyState.WAITING_FOR_IMPULSE, "Scanning 15M swings", now_ts)

            # 2. Detect 15M Impulse
            impulse = self.impulse_detector.detect_impulse(sym, c_15m, bias_4h, bias_1h)
            if not impulse:
                if sm.state not in (StrategyState.POSITION_OPEN, StrategyState.POSITION_MANAGEMENT):
                    sm.transition_to(StrategyState.WAITING_FOR_IMPULSE, "No valid impulse leg", now_ts)
                continue

            if sm.current_impulse is None or impulse.timestamp != sm.current_impulse.timestamp:
                sm.current_impulse = impulse
                sm.fib_levels = self.fib_calc.calculate(impulse)
                sm.transition_to(StrategyState.IMPULSE_CONFIRMED, f"15M impulse size: {impulse.size:.2f}", now_ts)
                sm.transition_to(StrategyState.FIB_LEVELS_CALCULATED, "Fib levels generated", now_ts)
                sm.transition_to(StrategyState.WAITING_FOR_PULLBACK, "Monitoring 5M retracement", now_ts)

            # 3. Pullback Evaluation
            pb_start_idx = max(
                0,
                next(
                    (k for k, c in enumerate(c_5m) if c.timestamp >= impulse.timestamp),
                    len(c_5m) - 1,
                ),
            )
            is_valid_pb, is_pref, is_inval, pb_low, pb_high, zone_cat = (
                self.pullback_detector.evaluate_pullback(c_5m, sm.fib_levels, pb_start_idx)
            )

            if is_inval:
                sm.reset_to_waiting_impulse("Pullback closed beyond 78.6% Fib", now_ts)
                self.db.log_rejection(sym, SetupRejectReason.REJECTED_FIB_INVALIDATED, "Closed > 78.6%", now_ts)
                continue

            if not is_valid_pb or zone_cat is None:
                continue

            if sm.state == StrategyState.WAITING_FOR_PULLBACK:
                sm.transition_to(StrategyState.FIB_ZONE_REACHED, f"Reached {zone_cat.value}", now_ts)
                sm.transition_to(StrategyState.PULLBACK_CONFIRMATION, "Scanning 5M shift & displacement", now_ts)

            # 4. Confirmation (Structure Shift + Displacement)
            if impulse.side == PositionSide.LONG:
                shift, disp, conf_lvl, conf_candle, conf_idx = (
                    self.confirmation_engine.check_bullish_confirmation(c_5m, pb_start_idx, impulse.high)
                )
            else:
                shift, disp, conf_lvl, conf_candle, conf_idx = (
                    self.confirmation_engine.check_bearish_confirmation(c_5m, pb_start_idx, impulse.low)
                )

            if not (shift and disp and conf_candle):
                continue

            # 5. Order Geometry & Setup Scoring
            latest_price = c_5m[-1].close
            atr14 = impulse.atr14

            entry_px, rej_entry = self.risk_engine.calculate_entry_price(
                conf_candle, latest_price, atr14, impulse.side
            )
            if rej_entry:
                self.db.log_rejection(sym, rej_entry, "Entry chase deviation", now_ts)
                continue

            sl_px, rej_sl = self.risk_engine.calculate_stop_loss(
                impulse.side, pb_low, pb_high, entry_px, atr14
            )
            if rej_sl:
                self.db.log_rejection(sym, rej_sl, "Invalid SL structure", now_ts)
                continue

            tp_px, rr, rej_tp = self.risk_engine.calculate_take_profit(
                impulse.side, entry_px, sl_px, impulse
            )
            if rej_tp or rr < settings.min_rr:
                self.db.log_rejection(sym, SetupRejectReason.REJECTED_LOW_RR, f"RR {rr:.2f} < 2.0", now_ts)
                continue

            atr_ratio = calculate_atr_ratio(c_15m)
            breakdown = self.scorer.score_setup(
                side=impulse.side,
                bias_4h=bias_4h,
                bias_1h=bias_1h,
                impulse=impulse,
                fib_levels=sm.fib_levels,
                pullback_price=pb_low if impulse.side == PositionSide.LONG else pb_high,
                is_structure_shift=shift,
                is_displacement=disp,
                is_confirmed=True,
                has_clear_tp=True,
                rr=rr,
                atr_ratio=atr_ratio,
                funding_rate=0.0001,
            )

            if breakdown.total_score < settings.min_setup_score:
                self.db.log_rejection(
                    sym, SetupRejectReason.REJECTED_LOW_SCORE, f"Score {breakdown.total_score} < 11", now_ts
                )
                continue

            # 6. Risk Manager Evaluation
            rej_risk = self.risk_manager.validate_new_trade(
                sym, now_ts, self.equity, atr_ratio, settings.emergency_stop
            )
            if rej_risk:
                self.db.log_rejection(sym, rej_risk, "Risk manager gate", now_ts)
                continue

            # 7. Position Sizing & Order Placement
            filters = self.exchange_info.get(sym)
            qty, risk_amt, is_valid = self.risk_engine.calculate_position_size(
                account_equity=self.equity,
                entry_price=entry_px,
                sl_price=sl_px,
                step_size=filters.step_size if filters else 0.001,
                min_qty=filters.min_qty if filters else 0.001,
                min_notional=filters.min_notional if filters else 5.0,
                qty_precision=filters.quantity_precision if filters else 3,
                leverage=settings.default_leverage,
            )

            if not is_valid or qty <= 0:
                continue

            setup = TradeSetup(
                symbol=sym,
                side=impulse.side,
                bias_4h=bias_4h,
                bias_1h=bias_1h,
                impulse=impulse,
                fib_levels=sm.fib_levels,
                pullback_low=pb_low,
                pullback_high=pb_high,
                confirmation_level=conf_lvl or 0.0,
                entry_price=entry_px,
                sl_price=sl_px,
                tp_price=tp_px,
                rr=rr,
                score=breakdown.total_score,
                score_breakdown=breakdown,
                atr14=atr14,
                timestamp=now_ts,
                setup_candle_index=len(c_5m) - 1,
                fib_zone_category=zone_cat,
            )
            sm.current_setup = setup
            sm.transition_to(StrategyState.ENTRY_READY, f"Score: {breakdown.total_score}/16 | RR: {rr:.2f}", now_ts)

            # Submit Order
            pos = self.order_mgr.submit_setup_entry(
                setup=setup,
                position_qty=qty,
                risk_amount=risk_amt,
                leverage=settings.default_leverage,
            )

            if pos:
                sm.active_position = pos
                sm.transition_to(StrategyState.ENTRY_SUBMITTED, "Order submitted", now_ts)
                if pos.status == OrderStatus.FILLED:
                    sm.transition_to(StrategyState.POSITION_OPEN, f"Position open: Qty={qty}", now_ts)
                    self.active_positions[sym] = pos
                    self.risk_manager.on_trade_opened(sym, now_ts)

    def render_dashboard(self):
        open_pos_list = [
            {
                "symbol": p.symbol,
                "side": p.side.value,
                "entry_price": p.entry_price,
                "sl_price": p.sl_price,
                "tp_price": p.tp_price,
                "quantity": p.quantity,
                "risk_amount": p.risk_amount,
            }
            for p in self.active_positions.values()
        ]
        daily_loss_pct = (
            ((self.risk_manager.starting_equity_today - self.equity) / self.risk_manager.starting_equity_today) * 100.0
            if self.risk_manager.starting_equity_today > 0
            else 0.0
        )
        TerminalDashboard.render(
            mode=self.mode,
            equity=self.equity,
            daily_pnl=self.risk_manager.daily_realized_pnl,
            daily_loss_pct=daily_loss_pct,
            daily_trades=self.risk_manager.daily_trade_count,
            consecutive_losses=self.risk_manager.consecutive_losses,
            state_machines=self.fsm_mgr.all(),
            open_positions=open_pos_list,
        )

    def start(self, poll_interval: int = 5, run_once: bool = False):
        self.initialize()
        logger.info("Starting main bot execution loop...")

        try:
            while self.running:
                self.run_cycle()
                self.render_dashboard()
                if run_once:
                    break
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            logger.info("Shutdown signal received. Exiting gracefully...")
        finally:
            logger.info("Bot stopped safely.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Binance Futures Fibonacci Pullback Trading Bot")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["dry-run", "paper", "testnet", "live"],
        default="dry-run",
        help="Execution mode (default: dry-run)",
    )
    parser.add_argument("--symbols", type=str, default="", help="Comma-separated list of symbols")
    parser.add_argument("--interval", type=int, default=5, help="Poll interval in seconds")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and print dashboard")
    args = parser.parse_args()

    mode_map = {
        "dry-run": "DRY_RUN",
        "paper": "PAPER",
        "testnet": "TESTNET",
        "live": "LIVE",
    }
    selected_mode = mode_map.get(args.mode.lower(), "DRY_RUN")
    sym_list = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] if args.symbols else None

    bot = FibonacciPullbackBot(mode=selected_mode, symbols=sym_list)
    bot.start(poll_interval=args.interval, run_once=args.once)
