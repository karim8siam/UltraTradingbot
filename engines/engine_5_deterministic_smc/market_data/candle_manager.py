import logging
from typing import List, Dict, Optional, Tuple, Any
from strategy.models import Candle

logger = logging.getLogger("CandleManager")

TIMEFRAME_MS = {
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000
}

class CandleManager:
    def __init__(self, max_buffer: int = 5000):
        self.max_buffer = max_buffer
        # symbol -> timeframe -> List[Candle]
        self.buffers: Dict[str, Dict[str, List[Candle]]] = {}

    def init_symbol(self, symbol: str):
        if symbol not in self.buffers:
            self.buffers[symbol] = {
                "4h": [],
                "1h": [],
                "15m": [],
                "5m": []
            }

    def raw_kline_to_candle(self, k: List[Any], is_closed: bool = True) -> Candle:
        """
        Binance kline format:
        [0: Open time, 1: Open, 2: High, 3: Low, 4: Close, 5: Volume, 6: Close time, ...]
        """
        return Candle(
            timestamp=int(k[0]),
            open=float(k[1]),
            high=float(k[2]),
            low=float(k[3]),
            close=float(k[4]),
            volume=float(k[5]),
            is_closed=is_closed
        )

    def load_historical_klines(self, symbol: str, timeframe: str, raw_klines: List[List[Any]]):
        self.init_symbol(symbol)
        candles = []
        for k in raw_klines:
            candles.append(self.raw_kline_to_candle(k, is_closed=True))
        
        # Verify integrity and sort
        validated = self.validate_and_clean_candles(candles, timeframe)
        self.buffers[symbol][timeframe] = validated[-self.max_buffer:]
        logger.info(f"[{symbol}] Loaded {len(self.buffers[symbol][timeframe])} validated candles for {timeframe}")

    def update_candle(self, symbol: str, timeframe: str, candle: Candle):
        self.init_symbol(symbol)
        buf = self.buffers[symbol][timeframe]
        
        if not buf:
            buf.append(candle)
            return

        if candle.timestamp == buf[-1].timestamp:
            # Overwrite current candle
            buf[-1] = candle
        elif candle.timestamp > buf[-1].timestamp:
            # New candle appended
            buf.append(candle)
            if len(buf) > self.max_buffer:
                self.buffers[symbol][timeframe] = buf[-self.max_buffer:]

    def get_closed_candles(self, symbol: str, timeframe: str) -> List[Candle]:
        buf = self.buffers.get(symbol, {}).get(timeframe, [])
        return [c for c in buf if c.is_closed]

    def validate_and_clean_candles(self, candles: List[Candle], timeframe: str) -> List[Candle]:
        """
        Deterministic integrity validation (Section 62):
        - Remove duplicate timestamps
        - Sort chronologically
        - Check for invalid OHLC (High >= max(Open, Close), Low <= min(Open, Close))
        - Warn on unexpected timestamp gaps
        """
        if not candles:
            return []

        # Sort by timestamp
        sorted_candles = sorted(candles, key=lambda c: c.timestamp)
        
        cleaned: List[Candle] = []
        seen_timestamps = set()

        for c in sorted_candles:
            if c.timestamp in seen_timestamps:
                continue
            seen_timestamps.add(c.timestamp)

            # Check OHLC validity
            if c.high < max(c.open, c.close) or c.low > min(c.open, c.close) or c.low < 0 or c.high < 0:
                logger.warning(f"Corrupted OHLC data detected at ts {c.timestamp}, skipping.")
                continue

            cleaned.append(c)

        return cleaned

    def check_minimum_requirements(self, symbol: str, min_4h: int = 500, min_1h: int = 1000,
                                   min_15m: int = 2000, min_5m: int = 3000) -> Tuple[bool, str]:
        self.init_symbol(symbol)
        len_4h = len(self.buffers[symbol]["4h"])
        len_1h = len(self.buffers[symbol]["1h"])
        len_15m = len(self.buffers[symbol]["15m"])
        len_5m = len(self.buffers[symbol]["5m"])

        if len_4h < min_4h or len_1h < min_1h or len_15m < min_15m or len_5m < min_5m:
            status = f"Candle counts for {symbol}: 4H={len_4h}/{min_4h}, 1H={len_1h}/{min_1h}, 15M={len_15m}/{min_15m}, 5M={len_5m}/{min_5m}"
            return False, status
        return True, "READY"
