"""
Safety Enforcer & Unprotected Position Guard
Sections 45, 50, 52 Specification
"""

import logging
import time
from typing import Optional
from market_data.binance_client import BinanceClient
from market_data.exchange_info import SymbolFilters

logger = logging.getLogger("SafetyManager")


class SafetyManager:
    def __init__(self, client: Optional[BinanceClient] = None):
        self.client = client

    def ensure_position_protected(
        self,
        symbol: str,
        side: str,  # BUY or SELL
        quantity: float,
        sl_price: float,
        filters: SymbolFilters,
        max_retries: int = 3,
    ) -> bool:
        """
        Section 45: If an entry fills and SL placement fails:
        Retry immediately up to max_retries.
        If SL placement continues to fail, close the position immediately with a MARKET order!
        Never maintain OPEN POSITION + NO STOP LOSS.
        """
        if not self.client or not self.client.api_key:
            return True

        sl_side = "SELL" if side == "BUY" else "BUY"
        formatted_sl = filters.round_price(sl_price)
        formatted_qty = filters.round_qty(quantity)

        for attempt in range(1, max_retries + 1):
            try:
                res = self.client.create_order(
                    symbol=symbol,
                    side=sl_side,
                    order_type="STOP_MARKET",
                    quantity=formatted_qty,
                    stop_price=formatted_sl,
                    reduce_only=True,
                )
                logger.info(f"[{symbol}] Protective SL placed successfully on attempt {attempt}: {res}")
                return True
            except Exception as e:
                logger.error(f"[{symbol}] Failed to place protective SL (attempt {attempt}/{max_retries}): {e}")
                time.sleep(0.5)

        # Retries failed: Trigger Emergency Market Close!
        logger.critical(f"[{symbol}] EMERGENCY CLOSE: Protective SL failed to place! Closing position via MARKET order.")
        try:
            self.client.create_order(
                symbol=symbol,
                side=sl_side,
                order_type="MARKET",
                quantity=formatted_qty,
                reduce_only=True,
            )
            logger.info(f"[{symbol}] Position emergency closed successfully.")
        except Exception as e:
            logger.critical(f"[{symbol}] CRITICAL FAILURE: Could not emergency close position: {e}")

        return False
