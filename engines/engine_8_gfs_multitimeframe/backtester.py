"""
High-Performance, Zero Look-Ahead Bias Backtesting Engine for Binance Futures GFS Strategy
Simulates multi-symbol execution, multi-timeframe synchronization, realistic fees, funding, and slippage.
"""

import time
import math
import bisect
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from config import (
    MAKER_FEE_RATE, TAKER_FEE_RATE, SLIPPAGE_RATE,
    ESTIMATED_FUNDING_RATE, ENTRY_ORDER_TIMEOUT_MINUTES,
    MAX_SETUP_AGE
)
from indicators import Candle
from gfs_strategy import GFSStrategyEngine, GFSSetup, TrendDirection
from risk_manager import RiskManager, SymbolFilters
from metrics import TradeMetric, PerformanceSummary, calculate_performance_metrics


class GFSBacktestEngine:
    """
    Tick/Candle-accurate Backtesting Engine for Multi-Timeframe GFS Trading.
    """

    def __init__(
        self,
        initial_equity: float = 10000.0,
        maker_fee: float = MAKER_FEE_RATE,
        taker_fee: float = TAKER_FEE_RATE,
        slippage: float = SLIPPAGE_RATE,
        enforce_sessions: bool = False
    ):
        self.initial_equity = initial_equity
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage = slippage
        self.strategy = GFSStrategyEngine()
        self.risk_manager = RiskManager(starting_equity=initial_equity, enforce_sessions=enforce_sessions)

    def run_backtest(
        self,
        symbol_data: Dict[str, Dict[str, List[Candle]]],
        start_ratio: float = 0.0,
        end_ratio: float = 1.0
    ) -> Tuple[PerformanceSummary, List[TradeMetric], Dict[str, int]]:
        current_equity = self.initial_equity
        completed_trades: List[TradeMetric] = []
        rejection_counts: Dict[str, int] = {}

        self.risk_manager = RiskManager(starting_equity=self.initial_equity, enforce_sessions=self.risk_manager.enforce_sessions)

        # Precompute close timestamps for binary search
        time_indexes = {}
        for sym, tfs in symbol_data.items():
            time_indexes[sym] = {
                "1d_ts": [c.close_time for c in tfs.get("1d", [])],
                "4h_ts": [c.close_time for c in tfs.get("4h", [])],
                "15m_ts": [c.close_time for c in tfs.get("15m", [])]
            }

        # Determine start and end ranges
        active_15m_symbols = {}
        for sym, tfs in symbol_data.items():
            all_15m = tfs.get("15m", [])
            n = len(all_15m)
            start_idx = int(n * start_ratio)
            end_idx = int(n * end_ratio)
            active_15m_symbols[sym] = (start_idx, end_idx)

        # Timeline
        all_15m_timestamps = set()
        for sym, (s_idx, e_idx) in active_15m_symbols.items():
            for c in symbol_data[sym]["15m"][s_idx:e_idx]:
                all_15m_timestamps.add(c.close_time)

        sorted_timeline = sorted(list(all_15m_timestamps))

        pending_orders: Dict[str, Dict[str, Any]] = {}
        active_positions: Dict[str, Dict[str, Any]] = {}

        for current_ts in sorted_timeline:
            # 1. Update and Manage Open Positions
            for sym in list(active_positions.keys()):
                pos = active_positions[sym]
                # Find current 15M candle using binary search
                ts_list = time_indexes[sym]["15m_ts"]
                idx_15m = bisect.bisect_right(ts_list, current_ts) - 1
                if idx_15m < 0 or idx_15m >= len(symbol_data[sym]["15m"]):
                    continue
                c_15m = symbol_data[sym]["15m"][idx_15m]
                if c_15m.close_time != current_ts:
                    continue

                direction = pos["direction"]
                entry_price = pos["entry_price"]
                sl = pos["stop_loss"]
                tp = pos["take_profit"]
                pos_qty = pos["position_size"]
                risk_amt = pos["risk_amount"]

                exit_price = None
                exit_reason = None

                if direction == TrendDirection.BULLISH:
                    if c_15m.low <= sl:
                        exit_price = sl * (1.0 - self.slippage)
                        exit_reason = "STOP_LOSS"
                    elif c_15m.high >= tp:
                        exit_price = tp * (1.0 - self.slippage)
                        exit_reason = "TAKE_PROFIT"
                else:
                    if c_15m.high >= sl:
                        exit_price = sl * (1.0 + self.slippage)
                        exit_reason = "STOP_LOSS"
                    elif c_15m.low <= tp:
                        exit_price = tp * (1.0 + self.slippage)
                        exit_reason = "TAKE_PROFIT"

                if exit_price is not None:
                    if direction == TrendDirection.BULLISH:
                        gross_pnl = (exit_price - entry_price) * pos_qty
                    else:
                        gross_pnl = (entry_price - exit_price) * pos_qty

                    entry_fee = (entry_price * pos_qty) * self.maker_fee
                    exit_fee = (exit_price * pos_qty) * self.taker_fee
                    total_fee = entry_fee + exit_fee

                    duration_hours = (current_ts - pos["entry_time"]) / (3600 * 1000)
                    funding_intervals = max(1, int(duration_hours / 8))
                    funding_cost = (entry_price * pos_qty) * ESTIMATED_FUNDING_RATE * funding_intervals

                    net_pnl = gross_pnl - total_fee - funding_cost
                    r_mult = net_pnl / risk_amt if risk_amt > 0 else 0.0

                    metric = TradeMetric(
                        trade_id=pos["trade_id"],
                        symbol=sym,
                        direction=direction.value,
                        entry_time=pos["entry_time"],
                        exit_time=current_ts,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        position_size=pos_qty,
                        risk_amount=risk_amt,
                        gross_pnl=gross_pnl,
                        fees=total_fee,
                        funding_cost=funding_cost,
                        net_pnl=net_pnl,
                        r_multiple=r_mult,
                        exit_reason=exit_reason,
                        setup_score=pos["setup_score"]
                    )
                    completed_trades.append(metric)
                    current_equity += net_pnl
                    self.risk_manager.record_trade_closed(net_pnl, current_ts)
                    del active_positions[sym]
                    self.risk_manager.remove_open_position(sym)

            # 2. Check Pending Limit Orders for Fill or Expiration
            for order_id in list(pending_orders.keys()):
                order = pending_orders[order_id]
                sym = order["symbol"]
                ts_list = time_indexes[sym]["15m_ts"]
                idx_15m = bisect.bisect_right(ts_list, current_ts) - 1
                if idx_15m < 0 or idx_15m >= len(symbol_data[sym]["15m"]):
                    continue
                c_15m = symbol_data[sym]["15m"][idx_15m]
                if c_15m.close_time != current_ts:
                    continue

                order["age_minutes"] += 15
                direction = order["direction"]
                planned_entry = order["planned_entry"]

                filled = False
                if direction == TrendDirection.BULLISH:
                    if c_15m.low <= planned_entry:
                        filled = True
                else:
                    if c_15m.high >= planned_entry:
                        filled = True

                if filled:
                    active_positions[sym] = {
                        "trade_id": order_id,
                        "symbol": sym,
                        "direction": direction,
                        "entry_price": planned_entry,
                        "stop_loss": order["stop_loss"],
                        "take_profit": order["take_profit"],
                        "position_size": order["position_size"],
                        "risk_amount": order["risk_amount"],
                        "entry_time": current_ts,
                        "setup_score": order["setup_score"]
                    }
                    self.risk_manager.add_open_position(sym, active_positions[sym])
                    del pending_orders[order_id]
                elif order["age_minutes"] >= ENTRY_ORDER_TIMEOUT_MINUTES:
                    del pending_orders[order_id]
                    rejection_counts["REJECTED_ORDER_TIMEOUT"] = rejection_counts.get("REJECTED_ORDER_TIMEOUT", 0) + 1

            # 3. Evaluate New Signals across Symbols
            for sym, tfs in symbol_data.items():
                s_idx, e_idx = active_15m_symbols[sym]
                candles_15m = tfs.get("15m", [])
                ts_list_15m = time_indexes[sym]["15m_ts"]
                curr_15m_idx = bisect.bisect_right(ts_list_15m, current_ts) - 1
                if curr_15m_idx < 100 or curr_15m_idx > e_idx:
                    continue

                allowed, risk_reason = self.risk_manager.check_trade_allowed(sym, current_equity, current_ts)
                if not allowed:
                    rejection_counts[risk_reason] = rejection_counts.get(risk_reason, 0) + 1
                    continue

                # Sliced closed candles with bisect
                idx_4h = bisect.bisect_right(time_indexes[sym]["4h_ts"], current_ts)
                idx_1d = bisect.bisect_right(time_indexes[sym]["1d_ts"], current_ts)

                if idx_1d < 200 or idx_4h < 50:
                    continue

                closed_15m = candles_15m[max(0, curr_15m_idx - 120):curr_15m_idx + 1]
                closed_4h = tfs.get("4h", [])[max(0, idx_4h - 120):idx_4h]
                closed_1d = tfs.get("1d", [])[max(0, idx_1d - 250):idx_1d]

                setup, signal_reason = self.strategy.evaluate_15m_entry_setup(
                    symbol=sym,
                    daily_candles=closed_1d,
                    four_hour_candles=closed_4h,
                    son_candles=closed_15m
                )

                if setup is None:
                    rejection_counts[signal_reason] = rejection_counts.get(signal_reason, 0) + 1
                    continue

                pos_qty, risk_amt, notional, size_status = self.risk_manager.calculate_position_size(
                    symbol=sym,
                    equity=current_equity,
                    entry_price=setup.entry_price,
                    stop_loss=setup.stop_loss
                )
                if size_status != "OK":
                    rejection_counts[size_status] = rejection_counts.get(size_status, 0) + 1
                    continue

                order_id = f"bt_{sym}_{current_ts}"
                pending_orders[order_id] = {
                    "symbol": sym,
                    "direction": setup.direction,
                    "planned_entry": setup.entry_price,
                    "stop_loss": setup.stop_loss,
                    "take_profit": setup.take_profit,
                    "position_size": pos_qty,
                    "risk_amount": risk_amt,
                    "setup_score": setup.setup_score,
                    "created_at_ms": current_ts,
                    "age_minutes": 0
                }

        summary = calculate_performance_metrics(completed_trades, self.initial_equity)
        return summary, completed_trades, rejection_counts
