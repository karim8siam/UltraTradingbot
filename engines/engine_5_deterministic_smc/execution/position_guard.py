import time
import logging
from typing import Dict, Any, Optional
from market_data.binance_client import BinanceFuturesClient
from execution.order_manager import OrderManager
from strategy.models import TradeSide

logger = logging.getLogger("SMC_PositionGuard")

class PositionGuard:
    def __init__(self, client: BinanceFuturesClient, order_manager: OrderManager):
        self.client = client
        self.order_manager = order_manager

    def place_protective_orders(self, symbol: str, side: TradeSide, quantity: float,
                                stop_loss_price: float, take_profit_price: float,
                                tick_size: float, price_precision: int) -> Dict[str, Any]:
        """
        Immediately places protective STOP_MARKET and TAKE_PROFIT_MARKET orders.
        If SL placement fails after 3 retries, closes the position with an EMERGENCY MARKET ORDER.
        """
        exit_side = "SELL" if side == TradeSide.LONG else "BUY"
        formatted_sl = self.order_manager.format_price(stop_loss_price, tick_size, price_precision)
        formatted_tp = self.order_manager.format_price(take_profit_price, tick_size, price_precision)

        sl_order_id = None
        tp_order_id = None

        # 1. Place Stop Loss with up to 3 retries
        sl_placed = False
        for attempt in range(1, 4):
            try:
                sl_client_id = self.order_manager.generate_client_order_id(symbol, side, "SL")
                sl_res = self.client.place_order(
                    symbol=symbol,
                    side=exit_side,
                    order_type="STOP_MARKET",
                    quantity=quantity,
                    stop_price=formatted_sl,
                    client_order_id=sl_client_id,
                    reduce_only=True
                )
                sl_order_id = sl_res.get("orderId")
                sl_placed = True
                logger.info(f"[{symbol}] Protective SL placed successfully at {formatted_sl}")
                break
            except Exception as e:
                logger.error(f"[{symbol}] Failed to place SL (attempt {attempt}/3): {e}")
                time.sleep(0.5)

        # Emergency Fallback: If SL placement fails, close position immediately
        if not sl_placed:
            logger.critical(f"[{symbol}] EMERGENCY: Protective SL could not be placed! Closing position with MARKET order.")
            try:
                close_res = self.client.place_order(
                    symbol=symbol,
                    side=exit_side,
                    order_type="MARKET",
                    quantity=quantity,
                    reduce_only=True
                )
                return {
                    "status": "EMERGENCY_CLOSED",
                    "reason": "SL_PLACEMENT_FAILED",
                    "close_order": close_res
                }
            except Exception as close_err:
                logger.critical(f"[{symbol}] FATAL: Failed to execute emergency market close: {close_err}")
                return {
                    "status": "FATAL_ERROR",
                    "reason": f"SL_FAILED_AND_MARKET_CLOSE_FAILED: {close_err}"
                }

        # 2. Place Take Profit
        try:
            tp_client_id = self.order_manager.generate_client_order_id(symbol, side, "TP")
            tp_res = self.client.place_order(
                symbol=symbol,
                side=exit_side,
                order_type="TAKE_PROFIT_MARKET",
                quantity=quantity,
                stop_price=formatted_tp,
                client_order_id=tp_client_id,
                reduce_only=True
            )
            tp_order_id = tp_res.get("orderId")
            logger.info(f"[{symbol}] Protective TP placed successfully at {formatted_tp}")
        except Exception as e:
            logger.warning(f"[{symbol}] Warning: TP order placement failed: {e}")

        return {
            "status": "PROTECTED",
            "sl_order_id": sl_order_id,
            "tp_order_id": tp_order_id,
            "stop_loss": formatted_sl,
            "take_profit": formatted_tp
        }
