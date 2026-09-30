"""
High-Precision & High-Performance Backtesting Engine
Sections 56–62 Specification
"""

import bisect
import logging
import uuid
from typing import Dict, List, Optional
from core.types import (
    Candle,
    FibZoneCategory,
    PositionSide,
    SetupRejectReason,
    StrategyState,
    TradeRecord,
    TradeSetup,
    TrendType,
)
from core.swings import SwingDetector
from core.trend import TrendDetector
from core.impulse import ImpulseDetector
from core.fibonacci import FibonacciCalculator
from core.pullback import PullbackDetector
from core.confirmation import ConfirmationEngine
from core.setup_scorer import SetupScorer
from core.risk_engine import RiskEngine
from core.indicators import calculate_atr_ratio, get_latest_atr
from risk.risk_manager import RiskManager
from backtest.dataset import HistoricalDataset
from backtest.metrics import MetricsCalculator, PerformanceMetrics
from config.constants import (
    DEFAULT_TAKER_FEE,
    DEFAULT_MAKER_FEE,
    DEFAULT_SLIPPAGE,
    MAX_SETUP_AGE_CANDLES,
    ENTRY_ORDER_TIMEOUT_MINUTES,
)

logger = logging.getLogger("BacktestEngine")


class BacktestEngine:
    def __init__(
        self,
        initial_capital: float = 10000.0,
        taker_fee: float = DEFAULT_TAKER_FEE,
        maker_fee: float = DEFAULT_MAKER_FEE,
        slippage: float = DEFAULT_SLIPPAGE,
    ):
        self.initial_capital = initial_capital
        self.equity = initial_capital
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee
        self.slippage = slippage

        # Strategy components
        self.swing_detector = SwingDetector()
        self.trend_detector = TrendDetector(self.swing_detector)
        self.impulse_detector = ImpulseDetector(self.swing_detector)
        self.fib_calc = FibonacciCalculator()
        self.pullback_detector = PullbackDetector()
        self.confirmation_engine = ConfirmationEngine()
        self.scorer = SetupScorer()
        self.risk_engine = RiskEngine()
        self.risk_manager = RiskManager()

        self.closed_trades: List[TradeRecord] = []
        self.rejected_signals: List[Dict] = []

    def run(self, dataset: HistoricalDataset) -> PerformanceMetrics:
        symbol = dataset.symbol
        candles_5m = dataset.candles_5m
        candles_15m = dataset.candles_15m
        candles_1h = dataset.candles_1h
        candles_4h = dataset.candles_4h

        n_5m = len(candles_5m)
        if n_5m < 50:
            return PerformanceMetrics()

        ts_5m = [c.timestamp for c in candles_5m]
        ts_15m = [c.timestamp for c in candles_15m]
        ts_1h = [c.timestamp for c in candles_1h]
        ts_4h = [c.timestamp for c in candles_4h]

        active_setup: Optional[TradeSetup] = None
        active_position: Optional[Dict] = None
        active_limit_order: Optional[Dict] = None

        pullback_start_idx_5m = 0
        last_impulse_ts = 0
        
        last_4h_idx = -1
        cached_bias_4h = TrendType.NEUTRAL
        last_1h_idx = -1
        cached_bias_1h = TrendType.NEUTRAL
        last_15m_idx = -1
        cached_impulse = None

        # Optimization: Pre-warm window
        start_i = max(30, int(n_5m * 0.05))

        for i in range(start_i, n_5m):
            current_candle = candles_5m[i]
            current_ts = current_candle.timestamp

            # ---------------- 1. Manage Active Position ---------------- #
            if active_position is not None:
                pos_side = active_position["side"]
                entry_px = active_position["entry_price"]
                sl_px = active_position["sl_price"]
                tp_px = active_position["tp_price"]
                qty = active_position["qty"]
                risk_amt = active_position["risk_amount"]

                hit_sl = False
                hit_tp = False
                exit_px = 0.0

                if pos_side == PositionSide.LONG:
                    if current_candle.low <= sl_px:
                        hit_sl = True
                        exit_px = min(current_candle.open, sl_px) * (1.0 - self.slippage)
                    elif current_candle.high >= tp_px:
                        hit_tp = True
                        exit_px = max(current_candle.open, tp_px) * (1.0 - self.slippage)
                else:
                    if current_candle.high >= sl_px:
                        hit_sl = True
                        exit_px = max(current_candle.open, sl_px) * (1.0 + self.slippage)
                    elif current_candle.low <= tp_px:
                        hit_tp = True
                        exit_px = min(current_candle.open, tp_px) * (1.0 + self.slippage)

                if hit_sl or hit_tp:
                    if pos_side == PositionSide.LONG:
                        gross_pnl = (exit_px - entry_px) * qty
                    else:
                        gross_pnl = (entry_px - exit_px) * qty

                    fee_open = entry_px * qty * self.maker_fee
                    fee_close = exit_px * qty * self.taker_fee
                    total_fees = fee_open + fee_close
                    net_pnl = gross_pnl - total_fees

                    self.equity += net_pnl
                    self.risk_manager.on_trade_closed(symbol, net_pnl, current_ts)

                    record = TradeRecord(
                        trade_id=active_position["trade_id"],
                        timestamp=active_position["setup"].timestamp,
                        symbol=symbol,
                        side=pos_side.value,
                        bias_4h=active_position["setup"].bias_4h.value,
                        bias_1h=active_position["setup"].bias_1h.value,
                        impulse_low=active_position["setup"].impulse.low,
                        impulse_high=active_position["setup"].impulse.high,
                        impulse_size=active_position["setup"].impulse.size,
                        atr=active_position["setup"].atr14,
                        fib_236=active_position["setup"].fib_levels.fib_236,
                        fib_382=active_position["setup"].fib_levels.fib_382,
                        fib_500=active_position["setup"].fib_levels.fib_500,
                        fib_618=active_position["setup"].fib_levels.fib_618,
                        fib_786=active_position["setup"].fib_levels.fib_786,
                        pullback_low=active_position["setup"].pullback_low,
                        pullback_high=active_position["setup"].pullback_high,
                        confirmation_level=active_position["setup"].confirmation_level,
                        entry=entry_px,
                        sl=sl_px,
                        tp=tp_px,
                        risk_amount=risk_amt,
                        position_size=qty,
                        leverage=5,
                        rr=active_position["setup"].rr,
                        setup_score=active_position["setup"].score,
                        funding_rate=0.0001,
                        entry_time=active_position["entry_time"],
                        exit_time=current_ts,
                        exit_price=exit_px,
                        gross_pnl=gross_pnl,
                        fees=total_fees,
                        funding_cost=0.0,
                        net_pnl=net_pnl,
                        result="WIN" if net_pnl > 0 else "LOSS",
                        exit_reason="TAKE_PROFIT" if hit_tp else "STOP_LOSS",
                        fib_zone=active_position["setup"].fib_zone_category.value,
                    )
                    self.closed_trades.append(record)
                    active_position = None
                    active_setup = None
                    continue

            # ---------------- 2. Manage Pending Limit Order ---------------- #
            if active_limit_order is not None:
                setup = active_limit_order["setup"]
                limit_px = active_limit_order["price"]
                qty = active_limit_order["qty"]
                order_age_minutes = (current_ts - active_limit_order["submit_ts"]) / (60 * 1000.0)

                if order_age_minutes > ENTRY_ORDER_TIMEOUT_MINUTES:
                    active_limit_order = None
                    active_setup = None
                else:
                    is_filled = False
                    if setup.side == PositionSide.LONG and current_candle.low <= limit_px:
                        is_filled = True
                    elif setup.side == PositionSide.SHORT and current_candle.high >= limit_px:
                        is_filled = True

                    if is_filled:
                        active_position = {
                            "trade_id": str(uuid.uuid4()),
                            "setup": setup,
                            "side": setup.side,
                            "entry_price": limit_px,
                            "sl_price": setup.sl_price,
                            "tp_price": setup.tp_price,
                            "qty": qty,
                            "risk_amount": active_limit_order["risk_amount"],
                            "entry_time": current_ts,
                        }
                        self.risk_manager.on_trade_opened(symbol, current_ts)
                        active_limit_order = None
                        continue

            # ---------------- 3. Scan for New Setups if Idle ---------------- #
            if active_position is None and active_limit_order is None:
                # Fast binary search slice
                idx_4h = bisect.bisect_right(ts_4h, current_ts)
                idx_1h = bisect.bisect_right(ts_1h, current_ts)
                idx_15m = bisect.bisect_right(ts_15m, current_ts)

                if idx_4h < 5 or idx_1h < 5 or idx_15m < 15:
                    continue

                # 3a. Check HTF Trend with caching
                if idx_4h != last_4h_idx:
                    last_4h_idx = idx_4h
                    current_4h_slice = candles_4h[max(0, idx_4h - 300) : idx_4h]
                    cached_bias_4h, _, _ = self.trend_detector.classify_trend(current_4h_slice, "4h")

                if idx_1h != last_1h_idx:
                    last_1h_idx = idx_1h
                    current_1h_slice = candles_1h[max(0, idx_1h - 300) : idx_1h]
                    cached_bias_1h, _, _ = self.trend_detector.classify_trend(current_1h_slice, "1h")

                bias_4h = cached_bias_4h
                bias_1h = cached_bias_1h

                if bias_4h == TrendType.NEUTRAL or bias_4h != bias_1h:
                    continue

                # 3b. Check 15M Impulse with caching
                if idx_15m != last_15m_idx:
                    last_15m_idx = idx_15m
                    current_15m_slice = candles_15m[max(0, idx_15m - 300) : idx_15m]
                    cached_impulse = self.impulse_detector.detect_impulse(symbol, current_15m_slice, bias_4h, bias_1h)

                impulse = cached_impulse
                if not impulse:
                    continue

                if impulse.timestamp != last_impulse_ts:
                    last_impulse_ts = impulse.timestamp
                    fib_levels = self.fib_calc.calculate(impulse)
                    pullback_start_idx_5m = bisect.bisect_left(ts_5m, impulse.timestamp)
                else:
                    fib_levels = self.fib_calc.calculate(impulse)

                # 3c. Evaluate Pullback
                is_valid_pb, is_pref, is_inval, pb_low, pb_high, zone_cat = (
                    self.pullback_detector.evaluate_pullback(
                        candles_5m[: i + 1], fib_levels, pullback_start_idx_5m
                    )
                )

                if is_inval or not is_valid_pb or zone_cat is None:
                    continue

                # 3d. Check 5M Confirmation
                if impulse.side == PositionSide.LONG:
                    shift, disp, conf_lvl, conf_candle, conf_idx = (
                        self.confirmation_engine.check_bullish_confirmation(candles_5m[: i + 1], pullback_start_idx_5m, impulse.high)
                    )
                else:
                    shift, disp, conf_lvl, conf_candle, conf_idx = (
                        self.confirmation_engine.check_bearish_confirmation(candles_5m[: i + 1], pullback_start_idx_5m, impulse.low)
                    )

                if not (shift and disp and conf_candle):
                    continue

                # 3e. Calculate Geometry (Entry, SL, TP, RR)
                atr14_15m = impulse.atr14
                entry_px, rej_entry = self.risk_engine.calculate_entry_price(
                    conf_candle, current_candle.close, atr14_15m, impulse.side
                )
                if rej_entry or entry_px is None:
                    continue

                sl_px, rej_sl = self.risk_engine.calculate_stop_loss(
                    impulse.side, pb_low, pb_high, entry_px, atr14_15m
                )
                if rej_sl or sl_px is None:
                    continue

                tp_px, rr, rej_tp = self.risk_engine.calculate_take_profit(
                    impulse.side, entry_px, sl_px, impulse
                )
                if rej_tp or tp_px is None or rr < 2.0:
                    continue

                # 3f. Score Setup
                atr_ratio = calculate_atr_ratio(current_15m_slice)
                breakdown = self.scorer.score_setup(
                    side=impulse.side,
                    bias_4h=bias_4h,
                    bias_1h=bias_1h,
                    impulse=impulse,
                    fib_levels=fib_levels,
                    pullback_price=pb_low if impulse.side == PositionSide.LONG else pb_high,
                    is_structure_shift=shift,
                    is_displacement=disp,
                    is_confirmed=True,
                    has_clear_tp=True,
                    rr=rr,
                    atr_ratio=atr_ratio,
                    funding_rate=0.0001,
                )

                if breakdown.total_score < 11:
                    continue

                # 3g. Risk Manager Validation
                rej_risk = self.risk_manager.validate_new_trade(
                    symbol, current_ts, self.equity, atr_ratio
                )
                if rej_risk:
                    self.rejected_signals.append({"symbol": symbol, "reason": rej_risk.value, "ts": current_ts})
                    continue

                # 3h. Position Sizing (1% risk)
                qty, risk_amount, is_valid_size = self.risk_engine.calculate_position_size(
                    self.equity, entry_px, sl_px
                )
                if not is_valid_size or qty <= 0:
                    continue

                setup = TradeSetup(
                    symbol=symbol,
                    side=impulse.side,
                    bias_4h=bias_4h,
                    bias_1h=bias_1h,
                    impulse=impulse,
                    fib_levels=fib_levels,
                    pullback_low=pb_low,
                    pullback_high=pb_high,
                    confirmation_level=conf_lvl or 0.0,
                    entry_price=entry_px,
                    sl_price=sl_px,
                    tp_price=tp_px,
                    rr=rr,
                    score=breakdown.total_score,
                    score_breakdown=breakdown,
                    atr14=atr14_15m,
                    timestamp=current_ts,
                    setup_candle_index=i,
                    fib_zone_category=zone_cat,
                )

                active_limit_order = {
                    "setup": setup,
                    "price": entry_px,
                    "qty": qty,
                    "risk_amount": risk_amount,
                    "submit_ts": current_ts,
                }

        return MetricsCalculator.calculate(self.closed_trades, self.initial_capital)
