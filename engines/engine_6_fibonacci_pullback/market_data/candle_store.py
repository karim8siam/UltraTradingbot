"""
Multi-Timeframe Historical & Live Closed Candle Buffer
Section 2 & 57 Specification
"""

from typing import Dict, List, Optional
from core.types import Candle
from config.constants import MIN_CANDLES, TIMEFRAMES


class CandleStore:
    def __init__(self, max_buffer_size: int = 5000):
        self.max_buffer_size = max_buffer_size
        # {symbol: {timeframe: [Candle]}}
        self.store: Dict[str, Dict[str, List[Candle]]] = {}

    def _ensure_symbol(self, symbol: str):
        if symbol not in self.store:
            self.store[symbol] = {tf: [] for tf in TIMEFRAMES}

    def add_candle(self, symbol: str, timeframe: str, candle: Candle):
        """Adds a closed candle, ensuring sorted order and deduplication."""
        self._ensure_symbol(symbol)
        buffer = self.store[symbol][timeframe]

        if not buffer:
            buffer.append(candle)
            return

        # Check if updating last candle or appending new
        if candle.timestamp == buffer[-1].timestamp:
            buffer[-1] = candle
        elif candle.timestamp > buffer[-1].timestamp:
            buffer.append(candle)
            if len(buffer) > self.max_buffer_size:
                buffer.pop(0)
        else:
            # Re-sort if out of order
            buffer.append(candle)
            buffer.sort(key=lambda c: c.timestamp)
            # Remove duplicate timestamps
            dedup = []
            seen = set()
            for c in buffer:
                if c.timestamp not in seen:
                    dedup.append(c)
                    seen.add(c.timestamp)
            self.store[symbol][timeframe] = dedup[-self.max_buffer_size :]

    def add_candles(self, symbol: str, timeframe: str, candles: List[Candle]):
        for c in candles:
            self.add_candle(symbol, timeframe, c)

    def get_candles(self, symbol: str, timeframe: str) -> List[Candle]:
        self._ensure_symbol(symbol)
        return self.store[symbol][timeframe]

    def has_sufficient_data(self, symbol: str) -> bool:
        """Checks whether minimum candle counts are satisfied across all 4 timeframes."""
        self._ensure_symbol(symbol)
        for tf, min_req in MIN_CANDLES.items():
            if len(self.store[symbol].get(tf, [])) < min_req:
                return False
        return True

    def get_candle_counts(self, symbol: str) -> Dict[str, int]:
        self._ensure_symbol(symbol)
        return {tf: len(self.store[symbol][tf]) for tf in TIMEFRAMES}
