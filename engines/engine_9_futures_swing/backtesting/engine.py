"""
Deterministic Multi-Timeframe High-Performance Backtesting Engine.
Precomputes causal indicators without future data leakage for sub-second execution.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import uuid
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from config import Config
from strategy.structure import SwingDetector, TrendDirection
from strategy.impulse_pullback import ImpulseDetector, PullbackEngine, ImpulseMove
from strategy.confirmation import ConfirmationEngine
from strategy.scorer import SetupScorer
from strategy.indicators import (
    calculate_ema_series, calculate_atr_series, calculate_adx_series,
    calculate_average_body
)
from risk.risk_manager import RiskManager
from database.db import Database
from .metrics import MetricsEngine, PerformanceMetrics


@dataclass
class Position:
    trade_id: str
    symbol: str
    direction: str             # "LONG" or "SHORT"
    entry_price: float
    current_sl: float
    original_sl: float
    tp1: float
    tp2: Optional[float]
    quantity: float
    initial_quantity: float
    risk_amount: float
    entry_time: str
    entry_timestamp: int
    leverage: int
    setup_score: int
    partial_closed: bool = False
    breakeven_activated: bool = False
    trailing_activated: bool = False
    accumulated_funding: float = 0.0
    accumulated_fees: float = 0.0
    holding_hours: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PendingLimitOrder:
    order_id: str
    symbol: str
    direction: str
    limit_price: float
    stop_loss: float
    tp1: float
    tp2: Optional[float]
    quantity: float
    risk_amount: float
    created_timestamp: int
    bars_active: int
    setup_score: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    trades: List[Dict[str, Any]]
    metrics: PerformanceMetrics
    equity_curve: List[Dict[str, Any]]


class BacktestEngine:
    def __init__(self, config: Config, initial_equity: float = 10000.0, db: Optional[Database] = None):
        self.config = config
        self.initial_equity = initial_equity
        self.current_equity = initial_equity
        self.db = db

        self.impulse_detector = ImpulseDetector(
            body_mult=config.IMPULSE_BODY_MULTIPLIER,
            atr_mult=config.IMPULSE_ATR_MULTIPLIER
        )
        self.pullback_engine = PullbackEngine(
            max_retracement=config.MAX_RETRACEMENT,
            swing_length=config.SWING_LENGTH
        )
        self.confirm_engine = ConfirmationEngine(
            min_rr=config.MIN_RR,
            swing_length=config.SWING_LENGTH,
            sl_atr_buffer=config.SL_ATR_BUFFER_FACTOR,
            timeout_bars=config.ENTRY_TIMEOUT_HOURS
        )
        self.scorer = SetupScorer(config=config)
        self.risk_mgr = RiskManager(config=config)
        self.swing_detector = SwingDetector(swing_length=config.SWING_LENGTH)

    def _prepare_symbol_cache(self, tfs: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Precompute causal indicator arrays for a symbol."""
        cache: Dict[str, Any] = {}
        
        # 1D Cache
        df_1d = tfs.get("1d")
        if df_1d is not None and not df_1d.empty:
            c_1d = df_1d["close"].values
            h_1d = df_1d["high"].values
            l_1d = df_1d["low"].values
            ts_1d = df_1d["timestamp"].values
            ct_1d = df_1d["close_time"].values

            ema50_1d = calculate_ema_series(c_1d, self.config.DAILY_EMA_FAST)
            ema200_1d = calculate_ema_series(c_1d, self.config.DAILY_EMA_SLOW)
            swings_1d = self.swing_detector.find_swings(h_1d, l_1d, ts_1d)

            cache["1d"] = {
                "close_time": ct_1d,
                "timestamp": ts_1d,
                "open": df_1d["open"].values,
                "high": h_1d,
                "low": l_1d,
                "close": c_1d,
                "volume": df_1d["volume"].values,
                "ema50": ema50_1d,
                "ema200": ema200_1d,
                "swings": swings_1d
            }

        # 4H Cache
        df_4h = tfs.get("4h")
        if df_4h is not None and not df_4h.empty:
            c_4h = df_4h["close"].values
            h_4h = df_4h["high"].values
            l_4h = df_4h["low"].values
            o_4h = df_4h["open"].values
            v_4h = df_4h["volume"].values
            ct_4h = df_4h["close_time"].values
            ts_4h = df_4h["timestamp"].values

            ema20_4h = calculate_ema_series(c_4h, self.config.FOUR_HOUR_EMA_FAST)
            ema50_4h = calculate_ema_series(c_4h, self.config.FOUR_HOUR_EMA_SLOW)
            atr14_4h = calculate_atr_series(h_4h, l_4h, c_4h, period=14)
            adx_4h, _, _ = calculate_adx_series(h_4h, l_4h, c_4h, period=14)
            swings_4h = self.swing_detector.find_swings(h_4h, l_4h, ts_4h)

            cache["4h"] = {
                "close_time": ct_4h,
                "timestamp": ts_4h,
                "open": o_4h,
                "high": h_4h,
                "low": l_4h,
                "close": c_4h,
                "volume": v_4h,
                "ema20": ema20_4h,
                "ema50": ema50_4h,
                "atr14": atr14_4h,
                "adx": adx_4h,
                "swings": swings_4h
            }

        # 1H Cache
        df_1h = tfs.get("1h")
        if df_1h is not None and not df_1h.empty:
            h_1h = df_1h["high"].values
            l_1h = df_1h["low"].values
            ts_1h = df_1h["timestamp"].values
            swings_1h = self.swing_detector.find_swings(h_1h, l_1h, ts_1h)

            cache["1h"] = {
                "timestamp": ts_1h,
                "open": df_1h["open"].values,
                "high": h_1h,
                "low": l_1h,
                "close": df_1h["close"].values,
                "volume": df_1h["volume"].values,
                "close_time": df_1h["close_time"].values,
                "swings": swings_1h
            }

        return cache

    def run(self, symbols_data: Dict[str, Dict[str, pd.DataFrame]]) -> BacktestResult:
        closed_trades: List[Dict[str, Any]] = []
        open_positions: List[Position] = []
        pending_orders: List[PendingLimitOrder] = []
        equity_history: List[Dict[str, Any]] = []

        # Precompute indicators across all symbols
        sym_caches: Dict[str, Dict[str, Any]] = {}
        all_timestamps = set()

        for sym, tfs in symbols_data.items():
            cache = self._prepare_symbol_cache(tfs)
            sym_caches[sym] = cache
            if "1h" in cache:
                all_timestamps.update(cache["1h"]["timestamp"])

        sorted_timeline = sorted(list(all_timestamps))

        for ts in sorted_timeline:
            now_dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
            now_str = now_dt.isoformat()

            # 1. Manage Active Positions
            for pos in list(open_positions):
                cache = sym_caches[pos.symbol]
                h1_ts = cache["1h"]["timestamp"]
                idx_1h = np.searchsorted(h1_ts, ts)
                if idx_1h >= len(h1_ts) or h1_ts[idx_1h] != ts:
                    continue

                b_open = cache["1h"]["open"][idx_1h]
                b_high = cache["1h"]["high"][idx_1h]
                b_low = cache["1h"]["low"][idx_1h]
                b_close = cache["1h"]["close"][idx_1h]

                pos.holding_hours += 1.0

                if (int(ts / (1000 * 3600)) % 8) == 0:
                    pos.accumulated_funding += (pos.quantity * b_close) * 0.0001

                if pos.direction == "LONG":
                    # Check SL
                    if b_low <= pos.current_sl:
                        exit_price = min(b_open, pos.current_sl)
                        self._close_position(pos, exit_price, now_str, "STOP_LOSS", closed_trades, open_positions)
                        continue

                    # +1R Breakeven
                    r_dist = pos.entry_price - pos.original_sl
                    if not pos.breakeven_activated and (b_high >= pos.entry_price + r_dist * self.config.BREAKEVEN_AT_R):
                        pos.breakeven_activated = True
                        pos.current_sl = max(pos.current_sl, pos.entry_price + (r_dist * self.config.BREAKEVEN_BUFFER_R))

                    # +2R Partial TP
                    if not pos.partial_closed and (b_high >= pos.entry_price + r_dist * self.config.PARTIAL_TP_R):
                        partial_qty = pos.quantity * self.config.PARTIAL_CLOSE_PERCENT
                        pos.quantity -= partial_qty
                        pos.partial_closed = True
                        pos.trailing_activated = True
                        partial_exit_price = pos.entry_price + r_dist * self.config.PARTIAL_TP_R
                        gross_pnl = partial_qty * (partial_exit_price - pos.entry_price)
                        fee = partial_qty * partial_exit_price * self.config.TAKER_FEE
                        self.current_equity += (gross_pnl - fee)

                    # Trailing SL update on confirmed 4H Higher Low
                    if pos.trailing_activated:
                        idx_4h = np.searchsorted(cache["4h"]["close_time"], ts, side="right")
                        confirmed_sls = [s.price for s in cache["4h"]["swings"]
                                         if (not s.is_high) and s.confirmed_index < idx_4h and s.price > pos.current_sl and s.price < b_close]
                        if confirmed_sls:
                            pos.current_sl = max(pos.current_sl, confirmed_sls[-1])

                    # Target TP1
                    if b_high >= pos.tp1:
                        self._close_position(pos, pos.tp1, now_str, "TAKE_PROFIT", closed_trades, open_positions)
                        continue

                    # Timeout 30 days
                    if (pos.holding_hours / 24.0) >= self.config.MAX_HOLD_DAYS:
                        self._close_position(pos, b_close, now_str, "MAX_HOLD_TIMEOUT", closed_trades, open_positions)
                        continue

                else: # SHORT
                    if b_high >= pos.current_sl:
                        exit_price = max(b_open, pos.current_sl)
                        self._close_position(pos, exit_price, now_str, "STOP_LOSS", closed_trades, open_positions)
                        continue

                    r_dist = pos.original_sl - pos.entry_price
                    if not pos.breakeven_activated and (b_low <= pos.entry_price - r_dist * self.config.BREAKEVEN_AT_R):
                        pos.breakeven_activated = True
                        pos.current_sl = min(pos.current_sl, pos.entry_price - (r_dist * self.config.BREAKEVEN_BUFFER_R))

                    if not pos.partial_closed and (b_low <= pos.entry_price - r_dist * self.config.PARTIAL_TP_R):
                        partial_qty = pos.quantity * self.config.PARTIAL_CLOSE_PERCENT
                        pos.quantity -= partial_qty
                        pos.partial_closed = True
                        pos.trailing_activated = True
                        partial_exit_price = pos.entry_price - r_dist * self.config.PARTIAL_TP_R
                        gross_pnl = partial_qty * (pos.entry_price - partial_exit_price)
                        fee = partial_qty * partial_exit_price * self.config.TAKER_FEE
                        self.current_equity += (gross_pnl - fee)

                    if pos.trailing_activated:
                        idx_4h = np.searchsorted(cache["4h"]["close_time"], ts, side="right")
                        confirmed_shs = [s.price for s in cache["4h"]["swings"]
                                         if s.is_high and s.confirmed_index < idx_4h and s.price < pos.current_sl and s.price > b_close]
                        if confirmed_shs:
                            pos.current_sl = min(pos.current_sl, confirmed_shs[-1])

                    if b_low <= pos.tp1:
                        self._close_position(pos, pos.tp1, now_str, "TAKE_PROFIT", closed_trades, open_positions)
                        continue

                    if (pos.holding_hours / 24.0) >= self.config.MAX_HOLD_DAYS:
                        self._close_position(pos, b_close, now_str, "MAX_HOLD_TIMEOUT", closed_trades, open_positions)
                        continue

            # 2. Manage Pending Limit Orders
            for order in list(pending_orders):
                order.bars_active += 1
                cache = sym_caches[order.symbol]
                h1_ts = cache["1h"]["timestamp"]
                idx_1h = np.searchsorted(h1_ts, ts)
                if idx_1h >= len(h1_ts) or h1_ts[idx_1h] != ts:
                    continue

                b_high = cache["1h"]["high"][idx_1h]
                b_low = cache["1h"]["low"][idx_1h]

                filled = False
                if order.direction == "LONG" and b_low <= order.limit_price:
                    filled = True
                elif order.direction == "SHORT" and b_high >= order.limit_price:
                    filled = True

                if filled:
                    entry_fee = order.quantity * order.limit_price * self.config.MAKER_FEE
                    new_pos = Position(
                        trade_id=order.order_id,
                        symbol=order.symbol,
                        direction=order.direction,
                        entry_price=order.limit_price,
                        current_sl=order.stop_loss,
                        original_sl=order.stop_loss,
                        tp1=order.tp1,
                        tp2=order.tp2,
                        quantity=order.quantity,
                        initial_quantity=order.quantity,
                        risk_amount=order.risk_amount,
                        entry_time=now_str,
                        entry_timestamp=ts,
                        leverage=self.config.DEFAULT_LEVERAGE,
                        setup_score=order.setup_score,
                        accumulated_fees=entry_fee,
                        metadata=order.metadata
                    )
                    open_positions.append(new_pos)
                    pending_orders.remove(order)
                elif order.bars_active >= self.config.ENTRY_TIMEOUT_HOURS:
                    pending_orders.remove(order)
                    if self.db:
                        self.db.log_rejected_setup(
                            symbol=order.symbol, reason_code="REJECTED_ENTRY_TIMEOUT",
                            score=order.setup_score, direction=order.direction
                        )

            # 3. Evaluate New Setups across candidate symbols
            for symbol, cache in sym_caches.items():
                if any(p.symbol == symbol for p in open_positions) or any(o.symbol == symbol for o in pending_orders):
                    continue

                idx_1d = np.searchsorted(cache["1d"]["close_time"], ts, side="right")
                idx_4h = np.searchsorted(cache["4h"]["close_time"], ts, side="right")
                idx_1h = np.searchsorted(cache["1h"]["timestamp"], ts, side="right")

                if idx_1d < 205 or idx_4h < 60 or idx_1h < 20:
                    continue

                # 1D Trend check (Section 6)
                d_c = cache["1d"]["close"][idx_1d - 1]
                d_ema50 = cache["1d"]["ema50"][idx_1d - 1]
                d_ema50_prev = cache["1d"]["ema50"][idx_1d - 2]
                d_ema200 = cache["1d"]["ema200"][idx_1d - 1]
                d_slope = d_ema50 - d_ema50_prev

                if (d_ema50 > d_ema200) and (d_c > d_ema50) and (d_slope > 0):
                    daily_trend = TrendDirection.BULLISH
                elif (d_ema50 < d_ema200) and (d_c < d_ema50) and (d_slope < 0):
                    daily_trend = TrendDirection.BEARISH
                else:
                    daily_trend = TrendDirection.NEUTRAL

                if daily_trend == TrendDirection.NEUTRAL:
                    continue

                # 1D Structure check (Sections 7-9)
                conf_swings_1d = [s for s in cache["1d"]["swings"] if s.confirmed_index < idx_1d]
                sh_1d = [s for s in conf_swings_1d if s.is_high]
                sl_1d = [s for s in conf_swings_1d if not s.is_high]
                if len(sh_1d) < 2 or len(sl_1d) < 2:
                    continue

                if (sh_1d[-1].price > sh_1d[-2].price) and (sl_1d[-1].price > sl_1d[-2].price):
                    daily_struct = TrendDirection.BULLISH
                elif (sh_1d[-1].price < sh_1d[-2].price) and (sl_1d[-1].price < sl_1d[-2].price):
                    daily_struct = TrendDirection.BEARISH
                else:
                    daily_struct = TrendDirection.NEUTRAL

                if daily_struct != daily_trend:
                    continue

                # 4H Trend check (Section 12)
                f_c = cache["4h"]["close"][idx_4h - 1]
                f_ema20 = cache["4h"]["ema20"][idx_4h - 1]
                f_ema20_prev = cache["4h"]["ema20"][idx_4h - 2]
                f_ema50 = cache["4h"]["ema50"][idx_4h - 1]
                f_slope = f_ema20 - f_ema20_prev

                if (f_ema20 > f_ema50) and (f_c > f_ema20) and (f_slope > 0):
                    four_h_trend = TrendDirection.BULLISH
                elif (f_ema20 < f_ema50) and (f_c < f_ema20) and (f_slope < 0):
                    four_h_trend = TrendDirection.BEARISH
                else:
                    four_h_trend = TrendDirection.NEUTRAL

                if four_h_trend != daily_trend:
                    continue

                direction = "LONG" if daily_trend == TrendDirection.BULLISH else "SHORT"
                is_bullish = (direction == "LONG")

                # Volatility Check (Section 41)
                atr_slice = cache["4h"]["atr14"][:idx_4h]
                curr_atr = atr_slice[-1]
                if len(atr_slice) >= 50:
                    avg_atr50 = np.mean(atr_slice[-50:])
                    if avg_atr50 > 0 and (curr_atr / avg_atr50) > self.config.MAX_ATR_RATIO:
                        continue

                # 4H ADX trend strength (Section 42)
                adx_val = cache["4h"]["adx"][idx_4h - 1]
                if np.isnan(adx_val) or adx_val < self.config.MIN_ADX:
                    continue

                # 4H Impulse detection (Section 14)
                f_o_slice = cache["4h"]["open"][:idx_4h]
                f_h_slice = cache["4h"]["high"][:idx_4h]
                f_l_slice = cache["4h"]["low"][:idx_4h]
                f_c_slice = cache["4h"]["close"][:idx_4h]
                f_v_slice = cache["4h"]["volume"][:idx_4h]

                impulse = self.impulse_detector.detect_latest_impulse(
                    f_o_slice, f_h_slice, f_l_slice, f_c_slice, f_v_slice, is_bullish=is_bullish
                )
                if not impulse:
                    continue

                # 4H Pullback & Fibonacci (Sections 15-19)
                pullback = self.pullback_engine.evaluate_pullback(
                    f_h_slice, f_l_slice, f_c_slice, impulse, f_ema20, f_ema50
                )
                if not pullback.is_valid:
                    continue

                # 1H Confirmation (Sections 20-23, 26, 28-32)
                conf_swings_4h = [s for s in cache["4h"]["swings"] if s.confirmed_index < idx_4h]
                h1_o_slice = cache["1h"]["open"][:idx_1h]
                h1_h_slice = cache["1h"]["high"][:idx_1h]
                h1_l_slice = cache["1h"]["low"][:idx_1h]
                h1_c_slice = cache["1h"]["close"][:idx_1h]

                signal = self.confirm_engine.evaluate_1h_confirmation(
                    h1_o_slice, h1_h_slice, h1_l_slice, h1_c_slice, pullback, conf_swings_4h, is_bullish=is_bullish
                )
                if not signal.is_confirmed or signal.rr_ratio < self.config.MIN_RR:
                    continue

                # Scoring (Section 45)
                eval_res = self.scorer.score_setup(
                    symbol=symbol,
                    direction=direction,
                    daily_trend_aligned=True,
                    daily_structure_aligned=True,
                    four_h_trend_aligned=True,
                    strong_4h_impulse=True,
                    ema_fib_overlap=pullback.has_confluence_overlap,
                    valid_4h_pullback=True,
                    one_h_structure_confirm=True,
                    one_h_displacement=True,
                    adx_4h=adx_val,
                    volume_confirmed=(impulse.volume_ratio >= self.config.MIN_VOLUME_RATIO),
                    clear_structural_target=True,
                    rr_ratio=signal.rr_ratio,
                    is_extreme_volatility=False,
                    is_extreme_funding=False,
                    details={}
                )

                if not eval_res.is_valid:
                    continue

                open_pos_dicts = [{"symbol": p.symbol, "risk_amount": p.risk_amount} for p in open_positions]
                can_open, risk_reject = self.risk_mgr.can_open_new_trade(
                    candidate_symbol=symbol,
                    current_equity=self.current_equity,
                    open_positions=open_pos_dicts,
                    now_timestamp=ts / 1000.0
                )
                if not can_open:
                    continue

                size_res = self.risk_mgr.calculate_position_size(
                    symbol=symbol,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    account_equity=self.current_equity
                )
                if not size_res.is_valid:
                    continue

                order_id = f"TRADE_{symbol}_{ts}_{uuid.uuid4().hex[:6]}"
                pending_orders.append(PendingLimitOrder(
                    order_id=order_id,
                    symbol=symbol,
                    direction=direction,
                    limit_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    tp1=signal.target_tp1,
                    tp2=signal.target_tp2,
                    quantity=size_res.raw_quantity,
                    risk_amount=size_res.risk_amount,
                    created_timestamp=ts,
                    bars_active=0,
                    setup_score=eval_res.total_score,
                    metadata={
                        "daily_trend": daily_trend.value,
                        "daily_structure": daily_struct.value,
                        "daily_EMA50": d_ema50,
                        "daily_EMA200": d_ema200,
                        "four_h_trend": four_h_trend.value,
                        "four_h_EMA20": f_ema20,
                        "four_h_EMA50": f_ema50,
                        "impulse_high": impulse.end_price if impulse.is_bullish else impulse.start_price,
                        "impulse_low": impulse.start_price if impulse.is_bullish else impulse.end_price,
                        "Fibonacci_38_2": pullback.fib_382,
                        "Fibonacci_50": pullback.fib_500,
                        "Fibonacci_61_8": pullback.fib_618,
                        "Fibonacci_70_5": pullback.fib_705,
                        "pullback_depth": pullback.pullback_depth,
                        "ADX": adx_val,
                        "volume_ratio": impulse.volume_ratio,
                        "one_h_structure": "CONFIRMED",
                        "RR": signal.rr_ratio
                    }
                ))

            equity_history.append({
                "timestamp": now_str,
                "equity": self.current_equity,
                "open_positions": len(open_positions)
            })

        metrics = MetricsEngine.calculate_metrics(closed_trades, initial_equity=self.initial_equity)
        return BacktestResult(trades=closed_trades, metrics=metrics, equity_curve=equity_history)

    def _close_position(self, pos: Position, exit_price: float, exit_time: str,
                        reason: str, closed_trades: List[Dict[str, Any]],
                        open_positions: List[Position]) -> None:
        if pos.direction == "LONG":
            gross_pnl = pos.quantity * (exit_price - pos.entry_price)
        else:
            gross_pnl = pos.quantity * (pos.entry_price - exit_price)

        exit_fee = pos.quantity * exit_price * self.config.TAKER_FEE
        slippage_cost = pos.quantity * exit_price * (self.config.DEFAULT_SLIPPAGE_BPS / 10000.0)
        total_fees = pos.accumulated_fees + exit_fee
        funding_cost = pos.accumulated_funding
        net_pnl = gross_pnl - total_fees - funding_cost - slippage_cost

        self.current_equity += net_pnl
        r_multiple = net_pnl / pos.risk_amount if pos.risk_amount > 0 else 0.0

        trade_record = {
            "trade_id": pos.trade_id,
            "timestamp": pos.entry_time,
            "symbol": pos.symbol,
            "direction": pos.direction,
            "daily_trend": pos.metadata.get("daily_trend", ""),
            "daily_structure": pos.metadata.get("daily_structure", ""),
            "daily_EMA50": pos.metadata.get("daily_EMA50", 0.0),
            "daily_EMA200": pos.metadata.get("daily_EMA200", 0.0),
            "four_h_trend": pos.metadata.get("four_h_trend", ""),
            "four_h_EMA20": pos.metadata.get("four_h_EMA20", 0.0),
            "four_h_EMA50": pos.metadata.get("four_h_EMA50", 0.0),
            "four_h_swing_high": pos.metadata.get("impulse_high", 0.0),
            "four_h_swing_low": pos.metadata.get("impulse_low", 0.0),
            "impulse_high": pos.metadata.get("impulse_high", 0.0),
            "impulse_low": pos.metadata.get("impulse_low", 0.0),
            "Fibonacci_38_2": pos.metadata.get("Fibonacci_38_2", 0.0),
            "Fibonacci_50": pos.metadata.get("Fibonacci_50", 0.0),
            "Fibonacci_61_8": pos.metadata.get("Fibonacci_61_8", 0.0),
            "Fibonacci_70_5": pos.metadata.get("Fibonacci_70_5", 0.0),
            "pullback_depth": pos.metadata.get("pullback_depth", 0.0),
            "ADX": pos.metadata.get("ADX", 0.0),
            "volume_ratio": pos.metadata.get("volume_ratio", 0.0),
            "one_h_structure": pos.metadata.get("one_h_structure", ""),
            "entry": pos.entry_price,
            "SL": pos.original_sl,
            "TP1": pos.tp1,
            "TP2": pos.tp2 or 0.0,
            "risk": pos.risk_amount,
            "position_size": pos.initial_quantity,
            "leverage": pos.leverage,
            "RR": pos.metadata.get("RR", 0.0),
            "setup_score": pos.setup_score,
            "funding": funding_cost,
            "entry_time": pos.entry_time,
            "exit_time": exit_time,
            "exit_price": exit_price,
            "gross_pnl": gross_pnl,
            "fees": total_fees,
            "funding_cost": funding_cost,
            "slippage": slippage_cost,
            "net_pnl": net_pnl,
            "R_multiple": r_multiple,
            "result": "WIN" if net_pnl > 0 else ("LOSS" if net_pnl < 0 else "BREAKEVEN"),
            "exit_reason": reason,
            "holding_hours": pos.holding_hours
        }

        closed_trades.append(trade_record)
        open_positions.remove(pos)

        self.risk_mgr.on_trade_closed(net_pnl=net_pnl, risk_amount=pos.risk_amount)

        if self.db:
            self.db.record_trade(trade_record)
