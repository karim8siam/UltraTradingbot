"""
Paper Trading Engine for Binance Futures GFS Strategy
Executes virtual orders against live market closed candles with zero risk.
"""

import time
import math
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from config import (
    MAKER_FEE_RATE, TAKER_FEE_RATE, SLIPPAGE_RATE,
    ESTIMATED_FUNDING_RATE, ENTRY_ORDER_TIMEOUT_MINUTES
)
from indicators import Candle
from gfs_strategy import GFSSetup, TrendDirection
from risk_manager import RiskManager
from database import GFSDatabase
from binance_client import BinanceFuturesClient


class PaperTrader:
    """
    Virtual Execution Engine simulating exact Binance Futures order book fills.
    """

    def __init__(
        self,
        db: GFSDatabase,
        risk_manager: RiskManager,
        initial_balance: float = 10000.0
    ):
        self.db = db
        self.risk_manager = risk_manager
        self.virtual_balance = initial_balance
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.pending_orders: Dict[str, Dict[str, Any]] = {}

    def submit_virtual_order(self, setup: GFSSetup, position_size: float) -> str:
        order_id = f"paper_{setup.symbol.lower()}_{int(time.time())}"
        now_ts = int(time.time() * 1000)

        record = {
            "trade_id": order_id,
            "symbol": setup.symbol,
            "direction": setup.direction.value,
            "status": "PENDING",
            "timestamp": now_ts,
            "daily_trend": setup.daily_trend.value,
            "daily_ema50": setup.daily_ema50,
            "daily_ema200": setup.daily_ema200,
            "four_hour_trend": setup.four_hour_trend.value,
            "four_hour_ema20": setup.four_hour_ema20,
            "four_hour_ema50": setup.four_hour_ema50,
            "pullback_zone_valid": 1 if setup.pullback_zone_valid else 0,
            "fifteen_m_trend": setup.direction.value,
            "fifteen_m_structure_level": setup.structure_level,
            "confirmation_candle_idx": setup.confirmation_candle_idx,
            "atr": setup.atr14_15m,
            "planned_entry": setup.entry_price,
            "entry_price": setup.entry_price,
            "stop_loss": setup.stop_loss,
            "take_profit": setup.take_profit,
            "risk_reward": setup.risk_reward,
            "risk_amount": self.virtual_balance * self.risk_manager.risk_per_trade,
            "position_size": position_size,
            "leverage": self.risk_manager.default_leverage,
            "setup_score": setup.setup_score,
            "score_breakdown": str(setup.score_breakdown),
            "funding": 0.0,
            "entry_time": now_ts,
            "client_order_id": order_id
        }

        self.pending_orders[order_id] = {
            "record": record,
            "setup": setup,
            "created_at_ms": now_ts,
            "age_minutes": 0
        }
        self.db.record_trade_entry(record)
        return order_id

    def on_15m_candle_closed(self, symbol: str, candle: Candle):
        now_ts = int(time.time() * 1000)

        # 1. Manage Active Positions for Symbol
        if symbol in self.open_positions:
            pos = self.open_positions[symbol]
            direction = pos["direction"]
            entry_price = pos["entry_price"]
            sl = pos["stop_loss"]
            tp = pos["take_profit"]
            qty = pos["position_size"]
            risk_amt = pos["risk_amount"]

            exit_price = None
            exit_reason = None

            if direction == TrendDirection.BULLISH or direction == "BULLISH":
                if candle.low <= sl:
                    exit_price = sl * (1.0 - SLIPPAGE_RATE)
                    exit_reason = "STOP_LOSS"
                elif candle.high >= tp:
                    exit_price = tp * (1.0 - SLIPPAGE_RATE)
                    exit_reason = "TAKE_PROFIT"
            else:
                if candle.high >= sl:
                    exit_price = sl * (1.0 + SLIPPAGE_RATE)
                    exit_reason = "STOP_LOSS"
                elif candle.low <= tp:
                    exit_price = tp * (1.0 + SLIPPAGE_RATE)
                    exit_reason = "TAKE_PROFIT"

            if exit_price is not None:
                # Calculate PnL and Fees
                if direction == TrendDirection.BULLISH or direction == "BULLISH":
                    gross_pnl = (exit_price - entry_price) * qty
                else:
                    gross_pnl = (entry_price - exit_price) * qty

                total_fees = (entry_price * qty * MAKER_FEE_RATE) + (exit_price * qty * TAKER_FEE_RATE)
                funding_cost = (entry_price * qty) * ESTIMATED_FUNDING_RATE
                net_pnl = gross_pnl - total_fees - funding_cost
                result = "WIN" if net_pnl > 0 else ("LOSS" if net_pnl < 0 else "BE")

                self.virtual_balance += net_pnl
                self.risk_manager.record_trade_closed(net_pnl, now_ts)
                self.risk_manager.remove_open_position(symbol)

                self.db.record_trade_exit(
                    trade_id=pos["trade_id"],
                    exit_time=now_ts,
                    exit_price=exit_price,
                    gross_pnl=gross_pnl,
                    fees=total_fees,
                    funding_cost=funding_cost,
                    net_pnl=net_pnl,
                    result=result,
                    exit_reason=exit_reason
                )
                del self.open_positions[symbol]

        # 2. Check Pending Orders for Symbol
        for order_id, order_info in list(self.pending_orders.items()):
            if order_info["record"]["symbol"] != symbol:
                continue

            order_info["age_minutes"] += 15
            setup: GFSSetup = order_info["setup"]
            planned_entry = setup.entry_price

            filled = False
            if setup.direction == TrendDirection.BULLISH:
                if candle.low <= planned_entry:
                    filled = True
            else:
                if candle.high >= planned_entry:
                    filled = True

            if filled:
                rec = order_info["record"]
                rec["status"] = "ACTIVE"
                rec["entry_time"] = now_ts
                self.open_positions[symbol] = rec
                self.risk_manager.add_open_position(symbol, rec)
                del self.pending_orders[order_id]

            elif order_info["age_minutes"] >= ENTRY_ORDER_TIMEOUT_MINUTES:
                del self.pending_orders[order_id]
                self.db.record_rejection(symbol, "PAPER_TRADING", "REJECTED_ORDER_TIMEOUT")
