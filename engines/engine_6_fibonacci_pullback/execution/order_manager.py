"""
Order Execution Manager
Sections 44, 46, 52 Specification
"""

import logging
import time
import uuid
from typing import Dict, Optional, Tuple
from core.types import OrderSide, OrderStatus, Position, PositionSide, TradeSetup
from execution.safety import SafetyManager
from market_data.binance_client import BinanceClient
from market_data.exchange_info import ExchangeInfoManager

logger = logging.getLogger("OrderManager")


class OrderManager:
    def __init__(
        self,
        client: Optional[BinanceClient],
        exchange_info: ExchangeInfoManager,
        safety_manager: SafetyManager,
        mode: str = "DRY_RUN",
    ):
        self.client = client
        self.exchange_info = exchange_info
        self.safety = safety_manager
        self.mode = mode
        # Tracks pending limit orders: {symbol: {order_id, timestamp, setup, qty}}
        self.pending_orders: Dict[str, Dict] = {}

    def generate_client_order_id(self, symbol: str) -> str:
        """Generates unique idempotent client order ID (Section 52)."""
        uid = uuid.uuid4().hex[:8]
        return f"fib_{symbol.lower()}_{int(time.time())}_{uid}"

    def submit_setup_entry(
        self,
        setup: TradeSetup,
        position_qty: float,
        risk_amount: float,
        leverage: int = 5,
    ) -> Optional[Position]:
        """
        Submits entry order following Section 44 rules.
        In DRY_RUN / PAPER mode, simulates execution.
        In TESTNET / LIVE mode, executes via Binance API.
        """
        symbol = setup.symbol
        side_str = "BUY" if setup.side == PositionSide.LONG else "SELL"
        filters = self.exchange_info.get(symbol)
        trade_id = str(uuid.uuid4())
        client_oid = self.generate_client_order_id(symbol)

        if self.mode in ("DRY_RUN", "PAPER"):
            # Simulated Fill
            logger.info(f"[{self.mode}] [{symbol}] Simulated Entry {side_str} Qty={position_qty} Price={setup.entry_price} SL={setup.sl_price} TP={setup.tp_price}")
            return Position(
                trade_id=trade_id,
                symbol=symbol,
                side=setup.side,
                entry_price=setup.entry_price,
                quantity=position_qty,
                sl_price=setup.sl_price,
                tp_price=setup.tp_price,
                leverage=leverage,
                risk_amount=risk_amount,
                entry_time=setup.timestamp,
                client_order_id=client_oid,
                status=OrderStatus.FILLED,
            )

        if not self.client or not filters:
            logger.error(f"[{symbol}] Cannot execute order: client or filters unavailable")
            return None

        # 1. Set leverage
        try:
            self.client.set_leverage(symbol, leverage)
        except Exception as e:
            logger.warning(f"[{symbol}] Leverage setting error: {e}")

        # 2. Place Limit Entry Order
        formatted_price = filters.round_price(setup.entry_price)
        formatted_qty = filters.round_qty(position_qty)

        try:
            res = self.client.create_order(
                symbol=symbol,
                side=side_str,
                order_type="LIMIT",
                quantity=formatted_qty,
                price=formatted_price,
                client_order_id=client_oid,
                time_in_force="GTC",
            )
            logger.info(f"[{symbol}] Limit entry submitted: {res}")

            # In live bot, position is monitored for fill before setting protective SL
            # For immediate safety verification:
            pos = Position(
                trade_id=trade_id,
                symbol=symbol,
                side=setup.side,
                entry_price=formatted_price,
                quantity=formatted_qty,
                sl_price=setup.sl_price,
                tp_price=setup.tp_price,
                leverage=leverage,
                risk_amount=risk_amount,
                entry_time=int(time.time() * 1000),
                client_order_id=client_oid,
                status=OrderStatus.NEW,
            )
            return pos
        except Exception as e:
            logger.error(f"[{symbol}] Order submission failed: {e}")
            return None
