import time
import uuid
import logging
from typing import Dict, Any, Optional
from strategy.models import TradeSide

logger = logging.getLogger("SMC_OrderManager")

class OrderManager:
    def __init__(self, timeout_minutes: int = 30):
        self.timeout_minutes = timeout_minutes

    def generate_client_order_id(self, symbol: str, side: TradeSide, tag: str = "ENTRY") -> str:
        unique_suffix = uuid.uuid4().hex[:8]
        ts = int(time.time())
        return f"SMC_{symbol}_{side.value}_{tag}_{ts}_{unique_suffix}"[:36]

    def format_price(self, price: float, tick_size: float, precision: int = 2) -> float:
        if tick_size <= 0:
            return round(price, precision)
        steps = round(price / tick_size)
        return round(steps * tick_size, precision)

    def format_quantity(self, qty: float, step_size: float, precision: int = 3) -> float:
        if step_size <= 0:
            return round(qty, precision)
        steps = int(qty / step_size)
        return round(steps * step_size, precision)

    def is_order_expired(self, submission_time_ms: int, current_time_ms: Optional[int] = None) -> bool:
        now_ms = current_time_ms if current_time_ms is not None else int(time.time() * 1000)
        elapsed_mins = (now_ms - submission_time_ms) / (60.0 * 1000.0)
        return elapsed_mins >= self.timeout_minutes
