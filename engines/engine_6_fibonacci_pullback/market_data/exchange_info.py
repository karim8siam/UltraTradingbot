"""
Dynamic Exchange Information Parser & Formatter
Section 2 Specification
"""

import math
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class SymbolFilters:
    symbol: str
    status: str
    price_precision: int
    quantity_precision: int
    tick_size: float
    step_size: float
    min_qty: float
    max_qty: float
    min_notional: float
    max_leverage: int = 20

    def format_price(self, price: float) -> str:
        """Formats price according to tick size and price precision."""
        if self.tick_size <= 0:
            return f"{price:.{self.price_precision}f}"
        ticks = round(price / self.tick_size)
        formatted_val = ticks * self.tick_size
        return f"{formatted_val:.{self.price_precision}f}"

    def format_qty(self, qty: float) -> str:
        """Formats quantity according to step size (rounded down)."""
        if self.step_size <= 0:
            return f"{qty:.{self.quantity_precision}f}"
        steps = math.floor(qty / self.step_size)
        formatted_val = steps * self.step_size
        return f"{formatted_val:.{self.quantity_precision}f}"

    def round_price(self, price: float) -> float:
        return float(self.format_price(price))

    def round_qty(self, qty: float) -> float:
        return float(self.format_qty(qty))


class ExchangeInfoManager:
    def __init__(self):
        self.symbols: Dict[str, SymbolFilters] = {}

    def parse_exchange_info(self, data: dict):
        """Parses raw Binance /fapi/v1/exchangeInfo response."""
        symbols_data = data.get("symbols", [])
        for s in symbols_data:
            symbol = s.get("symbol", "")
            status = s.get("status", "")
            price_prec = int(s.get("pricePrecision", 2))
            qty_prec = int(s.get("quantityPrecision", 3))

            tick_size = 0.01
            step_size = 0.001
            min_qty = 0.001
            max_qty = 1000000.0
            min_notional = 5.0

            for f in s.get("filters", []):
                ftype = f.get("filterType")
                if ftype == "PRICE_FILTER":
                    tick_size = float(f.get("tickSize", 0.01))
                elif ftype == "LOT_SIZE":
                    step_size = float(f.get("stepSize", 0.001))
                    min_qty = float(f.get("minQty", 0.001))
                    max_qty = float(f.get("maxQty", 1000000.0))
                elif ftype == "MIN_NOTIONAL":
                    min_notional = float(f.get("notional", 5.0))

            self.symbols[symbol] = SymbolFilters(
                symbol=symbol,
                status=status,
                price_precision=price_prec,
                quantity_precision=qty_prec,
                tick_size=tick_size,
                step_size=step_size,
                min_qty=min_qty,
                max_qty=max_qty,
                min_notional=min_notional,
                max_leverage=20,
            )

    def get(self, symbol: str) -> Optional[SymbolFilters]:
        return self.symbols.get(symbol)
