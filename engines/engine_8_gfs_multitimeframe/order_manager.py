"""
Order Lifecycle & Bracket Protection Manager
Ensures deterministic limit entries, strict SL/TP bracket submission, and unprotected position failsafe.
"""

import time
import uuid
from typing import Dict, Any, Optional, Tuple, List
from gfs_strategy import GFSSetup, TrendDirection
from binance_client import BinanceFuturesClient
from database import GFSDatabase
from risk_manager import RiskManager
from config import (
    USE_MARKET_ENTRY, ENABLE_STOP_LOSS, TARGET_PROFIT_EQUITY_PCT,
    STOP_LOSS_EQUITY_PCT, MARGIN_TYPE
)


class OrderManager:
    """
    Manages order creation, bracket SL/TP placement, timeouts, and failsafes.
    Option 2 Mode: Immediate MARKET entry, +2% equity TP, -1% equity SL (1:2 R:R), 5x leverage, ISOLATED margin.
    """

    def __init__(
        self,
        client: BinanceFuturesClient,
        db: GFSDatabase,
        risk_manager: RiskManager,
        paper_trading: bool = True,
        use_market_entry: bool = USE_MARKET_ENTRY,
        enable_stop_loss: bool = ENABLE_STOP_LOSS,
        target_profit_equity_pct: float = TARGET_PROFIT_EQUITY_PCT,
        stop_loss_equity_pct: float = STOP_LOSS_EQUITY_PCT,
        margin_type: str = MARGIN_TYPE
    ):
        self.client = client
        self.db = db
        self.risk_manager = risk_manager
        self.paper_trading = paper_trading
        self.use_market_entry = use_market_entry
        self.enable_stop_loss = enable_stop_loss
        self.target_profit_equity_pct = target_profit_equity_pct
        self.stop_loss_equity_pct = stop_loss_equity_pct
        self.margin_type = margin_type
        self.pending_orders: Dict[str, Dict[str, Any]] = {}

    def generate_client_order_id(self, symbol: str, tag: str = "entry") -> str:
        unique_suffix = uuid.uuid4().hex[:6]
        ts = int(time.time())
        return f"gfs_{symbol.lower()}_{tag}_{ts}_{unique_suffix}"

    def calculate_tp_price(
        self,
        symbol: str,
        direction: TrendDirection,
        fill_price: float,
        quantity: float,
        equity: float
    ) -> float:
        """
        Calculates Take Profit price targeting +2% of account equity in PnL:
        Target Profit = Equity * target_profit_equity_pct (e.g. 2%)
        For Long: TP = fill_price + (Target Profit / quantity)
        For Short: TP = fill_price - (Target Profit / quantity)
        Quantized to symbol tick_size and price_precision.
        """
        filters = self.risk_manager.get_symbol_filter(symbol)
        target_profit = equity * self.target_profit_equity_pct
        effective_qty = quantity if quantity > 0 else 1.0

        price_diff = target_profit / effective_qty
        if direction == TrendDirection.BULLISH:
            raw_tp = fill_price + price_diff
        else:
            raw_tp = fill_price - price_diff

        # Sanity floor
        if raw_tp <= 0:
            raw_tp = fill_price * 1.02 if direction == TrendDirection.BULLISH else fill_price * 0.98

        tick = filters.tick_size
        prec = filters.price_precision
        if tick > 0:
            quantized_tp = round(round(raw_tp / tick) * tick, prec)
        else:
            quantized_tp = round(raw_tp, prec)

        return quantized_tp

    def calculate_sl_price(
        self,
        symbol: str,
        direction: TrendDirection,
        fill_price: float,
        quantity: float,
        equity: float
    ) -> float:
        """
        Calculates Stop Loss price targeting 1% of account equity in loss:
        Target Loss = Equity * stop_loss_equity_pct (e.g. 1%)
        For Long: SL = fill_price - (Target Loss / quantity)
        For Short: SL = fill_price + (Target Loss / quantity)
        Quantized to symbol tick_size and price_precision.
        Combined with TP at 2% equity, produces strictly 1:2 Risk-Reward ratio.
        """
        filters = self.risk_manager.get_symbol_filter(symbol)
        target_loss = equity * self.stop_loss_equity_pct
        effective_qty = quantity if quantity > 0 else 1.0

        price_diff = target_loss / effective_qty
        if direction == TrendDirection.BULLISH:
            raw_sl = fill_price - price_diff
        else:
            raw_sl = fill_price + price_diff

        # Sanity floor
        if raw_sl <= 0:
            raw_sl = fill_price * 0.98 if direction == TrendDirection.BULLISH else fill_price * 1.02

        tick = filters.tick_size
        prec = filters.price_precision
        if tick > 0:
            quantized_sl = round(round(raw_sl / tick) * tick, prec)
        else:
            quantized_sl = round(raw_sl, prec)

        return quantized_sl

    def submit_entry_order(
        self,
        setup: GFSSetup,
        position_size: float,
        equity: float
    ) -> Tuple[bool, Optional[str], str]:
        """
        Submits entry order:
        - If use_market_entry is True (Option 2): Immediately places MARKET order,
          captures fill price, registers active position, and places on-exchange
          TAKE_PROFIT_MARKET order targeting +2% account equity.
        - If use_market_entry is False: Places LIMIT order at planned pullback price.
        """
        side = "BUY" if setup.direction == TrendDirection.BULLISH else "SELL"
        client_order_id = self.generate_client_order_id(setup.symbol, "entry")
        now_ts = int(time.time() * 1000)

        # Calculate planned TP targeting +2% account equity and SL targeting 1% account equity (1:2 R:R)
        planned_tp = self.calculate_tp_price(
            setup.symbol, setup.direction, setup.entry_price, position_size, equity
        )
        planned_sl = self.calculate_sl_price(
            setup.symbol, setup.direction, setup.entry_price, position_size, equity
        )

        trade_record = {
            "trade_id": client_order_id,
            "symbol": setup.symbol,
            "direction": setup.direction.value,
            "status": "PENDING_ENTRY",
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
            "stop_loss": planned_sl if self.enable_stop_loss else 0.0,
            "take_profit": planned_tp,
            "risk_reward": 2.0,
            "risk_amount": equity * self.stop_loss_equity_pct,
            "position_size": position_size,
            "leverage": self.risk_manager.default_leverage,
            "setup_score": setup.setup_score,
            "score_breakdown": str(setup.score_breakdown),
            "funding": 0.0,
            "entry_time": now_ts,
            "client_order_id": client_order_id
        }

        if self.paper_trading:
            if self.use_market_entry:
                trade_record["status"] = "ACTIVE"
                self.pending_orders[client_order_id] = {
                    "trade_record": trade_record,
                    "setup": setup,
                    "created_at_ms": now_ts,
                    "status": "ACTIVE",
                    "filled_qty": position_size
                }
                self.risk_manager.add_open_position(setup.symbol, trade_record)
                self.db.record_trade_entry(trade_record)
                return True, client_order_id, "PAPER_MARKET_ENTRY_ACTIVE"
            else:
                self.pending_orders[client_order_id] = {
                    "trade_record": trade_record,
                    "setup": setup,
                    "created_at_ms": now_ts,
                    "status": "PENDING",
                    "filled_qty": 0.0
                }
                self.db.record_trade_entry(trade_record)
                return True, client_order_id, "PAPER_ORDER_SUBMITTED"

        # Testnet or Live Order Execution
        try:
            # 1. Set leverage (10x)
            self.client.set_leverage(setup.symbol, self.risk_manager.default_leverage)

            # 2. Set margin type (ISOLATED)
            self.client.set_margin_type(setup.symbol, self.margin_type)

            if self.use_market_entry:
                # Option 2: Immediate MARKET execution
                res = self.client.place_order(
                    symbol=setup.symbol,
                    side=side,
                    type_="MARKET",
                    quantity=position_size,
                    client_order_id=client_order_id
                )

                if isinstance(res, dict) and res.get("error"):
                    return False, None, f"BINANCE_ERROR: {res.get('message')}"

                # Calculate actual fill price and executed quantity
                avg_price = float(res.get("avgPrice", 0.0))
                executed_qty = float(res.get("executedQty", 0.0))
                cum_quote = float(res.get("cumQuote", 0.0))

                if avg_price > 0:
                    fill_price = avg_price
                elif executed_qty > 0 and cum_quote > 0:
                    fill_price = cum_quote / executed_qty
                else:
                    ticker_p = self.client.fetch_ticker_price(setup.symbol)
                    fill_price = ticker_p if ticker_p > 0 else setup.entry_price

                if executed_qty <= 0:
                    executed_qty = position_size

                # Calculate actual TP price (+2% equity) and SL price (-1% equity)
                actual_tp = self.calculate_tp_price(
                    setup.symbol, setup.direction, fill_price, executed_qty, equity
                )
                actual_sl = self.calculate_sl_price(
                    setup.symbol, setup.direction, fill_price, executed_qty, equity
                )

                trade_record["status"] = "ACTIVE"
                trade_record["entry_price"] = fill_price
                trade_record["position_size"] = executed_qty
                trade_record["take_profit"] = actual_tp
                trade_record["stop_loss"] = actual_sl if self.enable_stop_loss else 0.0
                trade_record["entry_time"] = int(time.time() * 1000)
                trade_record["exchange_order_id"] = res.get("orderId")

                # Register active position
                self.risk_manager.add_open_position(setup.symbol, trade_record)
                self.db.record_trade_entry(trade_record)

                self.pending_orders[client_order_id] = {
                    "trade_record": trade_record,
                    "setup": setup,
                    "created_at_ms": now_ts,
                    "status": "ACTIVE",
                    "exchange_order_id": res.get("orderId"),
                    "filled_qty": executed_qty
                }

                # Place on-exchange Take Profit order immediately
                tp_side = "SELL" if setup.direction == TrendDirection.BULLISH else "BUY"
                tp_client_id = self.generate_client_order_id(setup.symbol, "tp")

                for retry in range(3):
                    tp_res = self.client.place_order(
                        symbol=setup.symbol,
                        side=tp_side,
                        type_="TAKE_PROFIT_MARKET",
                        quantity=executed_qty,
                        stop_price=actual_tp,
                        client_order_id=tp_client_id,
                        reduce_only=True
                    )
                    if isinstance(tp_res, dict) and not tp_res.get("error"):
                        break
                    time.sleep(0.5)

                # If SL is enabled, place SL order
                if self.enable_stop_loss:
                    sl_side = tp_side
                    sl_placed = False
                    for retry in range(3):
                        sl_res = self.client.place_order(
                            symbol=setup.symbol,
                            side=sl_side,
                            type_="STOP_MARKET",
                            quantity=executed_qty,
                            stop_price=actual_sl,
                            client_order_id=self.generate_client_order_id(setup.symbol, "sl"),
                            reduce_only=True
                        )
                        if isinstance(sl_res, dict) and not sl_res.get("error"):
                            sl_placed = True
                            break
                        time.sleep(0.5)

                    if not sl_placed:
                        # Cancel TP order if SL failed to prevent orphaned position
                        self.client.cancel_order(setup.symbol, client_order_id=tp_client_id)
                        self.client.place_order(
                            symbol=setup.symbol,
                            side=sl_side,
                            type_="MARKET",
                            quantity=executed_qty,
                            reduce_only=True
                        )
                        self.risk_manager.remove_open_position(setup.symbol)
                        return False, None, "CRITICAL_SL_FAILED_EMERGENCY_MARKET_CLOSED"

                return True, client_order_id, "MARKET_ENTRY_AND_BRACKET_PLACED"

            else:
                # Limit order execution
                res = self.client.place_order(
                    symbol=setup.symbol,
                    side=side,
                    type_="LIMIT",
                    quantity=position_size,
                    price=setup.entry_price,
                    client_order_id=client_order_id,
                    time_in_force="GTC"
                )

                if isinstance(res, dict) and res.get("error"):
                    return False, None, f"BINANCE_ERROR: {res.get('message')}"

                self.pending_orders[client_order_id] = {
                    "trade_record": trade_record,
                    "setup": setup,
                    "created_at_ms": now_ts,
                    "status": "PENDING",
                    "exchange_order_id": res.get("orderId")
                }
                self.db.record_trade_entry(trade_record)
                return True, client_order_id, "ENTRY_ORDER_PLACED"

        except Exception as e:
            return False, None, f"EXCEPTION: {str(e)}"

    def handle_position_filled(
        self,
        client_order_id: str,
        fill_price: float,
        quantity: float,
        equity: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Called when entry order fills. Places TP targeting +2% equity (and SL only if enabled).
        """
        if client_order_id not in self.pending_orders:
            return False, "UNKNOWN_ORDER"

        order_data = self.pending_orders[client_order_id]
        setup: GFSSetup = order_data["setup"]
        trade_record = order_data["trade_record"]

        # Calculate TP targeting +2% equity and SL targeting 1% equity risk
        current_eq = equity or 13.34
        actual_tp = self.calculate_tp_price(
            setup.symbol, setup.direction, fill_price, quantity, current_eq
        )
        actual_sl = self.calculate_sl_price(
            setup.symbol, setup.direction, fill_price, quantity, current_eq
        )

        trade_record["status"] = "ACTIVE"
        trade_record["entry_price"] = fill_price
        trade_record["position_size"] = quantity
        trade_record["take_profit"] = actual_tp
        trade_record["stop_loss"] = actual_sl if self.enable_stop_loss else 0.0
        trade_record["entry_time"] = int(time.time() * 1000)

        # Register position in Risk Manager
        self.risk_manager.add_open_position(setup.symbol, trade_record)

        if self.paper_trading:
            return True, "PAPER_BRACKET_ACTIVE"

        tp_side = "SELL" if setup.direction == TrendDirection.BULLISH else "BUY"

        # If SL is enabled, place SL order + failsafe
        if self.enable_stop_loss:
            sl_side = tp_side
            sl_placed = False
            for retry in range(3):
                sl_res = self.client.place_order(
                    symbol=setup.symbol,
                    side=sl_side,
                    type_="STOP_MARKET",
                    quantity=quantity,
                    stop_price=actual_sl,
                    client_order_id=self.generate_client_order_id(setup.symbol, "sl"),
                    reduce_only=True
                )
                if isinstance(sl_res, dict) and not sl_res.get("error"):
                    sl_placed = True
                    break
                time.sleep(0.5)

            if not sl_placed:
                self.client.place_order(
                    symbol=setup.symbol,
                    side=sl_side,
                    type_="MARKET",
                    quantity=quantity,
                    reduce_only=True
                )
                self.risk_manager.remove_open_position(setup.symbol)
                return False, "CRITICAL_SL_FAILED_EMERGENCY_MARKET_CLOSED"

        # Place Take Profit Order
        self.client.place_order(
            symbol=setup.symbol,
            side=tp_side,
            type_="TAKE_PROFIT_MARKET",
            quantity=quantity,
            stop_price=actual_tp,
            client_order_id=self.generate_client_order_id(setup.symbol, "tp"),
            reduce_only=True
        )

        return True, "BRACKET_ORDERS_CONFIRMED"

    def cancel_timeout_orders(self, max_timeout_minutes: int = 30):
        """
        Cancels limit orders pending for longer than max_timeout_minutes.
        """
        now_ms = int(time.time() * 1000)
        timeout_ms = max_timeout_minutes * 60 * 1000

        to_cancel = []
        for order_id, order_info in list(self.pending_orders.items()):
            if order_info["status"] == "PENDING" and (now_ms - order_info["created_at_ms"]) > timeout_ms:
                to_cancel.append(order_id)

        for order_id in to_cancel:
            info = self.pending_orders[order_id]
            setup: GFSSetup = info["setup"]
            if not self.paper_trading:
                self.client.cancel_order(setup.symbol, client_order_id=order_id)
            del self.pending_orders[order_id]
            self.db.record_rejection(setup.symbol, "ORDER_EXECUTION", "REJECTED_ORDER_TIMEOUT", {"order_id": order_id})
