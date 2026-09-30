import math
from typing import Dict, Any, List, Optional
import config
from binance_client import BinanceFuturesClient

class RiskManager:
    def __init__(self, client: BinanceFuturesClient):
        self.client = client

    def can_open_new_trade(self, symbol: str, active_positions: List[Dict[str, Any]]) -> bool:
        """
        Enforce max 4 concurrent trades and avoid duplicate positions on same symbol.
        """
        if len(active_positions) >= config.MAX_CONCURRENT_TRADES:
            print(f"[RISK] Max concurrent trades reached ({len(active_positions)}/{config.MAX_CONCURRENT_TRADES}). Cannot enter {symbol}.")
            return False

        for pos in active_positions:
            if pos["symbol"] == symbol and abs(pos.get("positionAmt", 0.0)) > 0:
                print(f"[RISK] Active position already exists for {symbol}. Skipping.")
                return False

        return True

    def calculate_order_quantity(self, symbol: str, current_price: float, balance_usdt: float) -> Optional[float]:
        """
        Calculate order quantity based on 1% margin and 5x leverage, adhering to stepSize and minNotional.
        """
        if balance_usdt <= 0 or current_price <= 0:
            print(f"[RISK] Invalid balance (${balance_usdt}) or price (${current_price}) for {symbol}.")
            return None

        # 1% margin allocation with 5x leverage
        target_margin = balance_usdt * config.MARGIN_FRACTION
        target_notional = target_margin * config.LEVERAGE

        rules = self.client.get_symbol_rules(symbol)
        min_notional = rules.get("min_notional", 5.0)
        step_size = rules.get("step_size", 0.001)
        min_qty = rules.get("min_qty", 0.001)
        qty_precision = rules.get("quantity_precision", 3)

        # Buffer min notional by 2% to prevent rounding below 5.0 USDT (e.g. 5.10 USDT)
        effective_min_notional = max(min_notional * 1.02, 5.10)
        if target_notional < effective_min_notional:
            target_notional = effective_min_notional

        raw_qty = target_notional / current_price

        # Quantize UP to next step size so notional is strictly >= minimum requirement
        if step_size > 0:
            precision_factor = int(round(1.0 / step_size))
            qty = math.ceil(raw_qty * precision_factor) / precision_factor
        else:
            qty = round(raw_qty, qty_precision)

        if qty < min_qty:
            qty = min_qty

        qty = round(qty, qty_precision)
        return qty
