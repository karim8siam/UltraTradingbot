"""
Market Data Downloader & Cache Manager.
Fetches, stores, and synchronizes 1D, 4H, and 1H candles for systematic swing trading.
"""

import os
import time
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import pandas as pd
import requests

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    timestamp: int       # Open time (ms)
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int      # Close time (ms)
    quote_volume: float
    trades_count: int


class DataFetcher:
    def __init__(self, config: Config):
        self.config = config
        self.data_dir = config.DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
        # Use Binance public Futures endpoint (no auth needed for market data)
        self.base_url = "https://fapi.binance.com"
        self.session = requests.Session()

    def _get_cache_filepath(self, symbol: str, interval: str) -> str:
        return os.path.join(self.data_dir, f"{symbol}_{interval}.csv")

    def fetch_raw_klines(self, symbol: str, interval: str, limit: int = 1000,
                         start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[List[Any]]:
        url = f"{self.base_url}/fapi/v1/klines"
        params: Dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1000)
        }
        if start_time:
            params["startTime"] = int(start_time)
        if end_time:
            params["endTime"] = int(end_time)

        res = self.session.get(url, params=params, timeout=15)
        res.raise_for_status()
        return res.json()

    def download_historical_candles(self, symbol: str, interval: str, total_candles: int = 2000,
                                     end_time: Optional[int] = None) -> pd.DataFrame:
        """Download historical candles with pagination going backward in time."""
        logger.info(f"Downloading {total_candles} candles for {symbol} on {interval}...")
        all_klines: List[List[Any]] = []
        current_end_time = end_time or int(time.time() * 1000)
        batch_size = 1000
        fetched = 0

        while fetched < total_candles:
            limit = min(batch_size, total_candles - fetched)
            klines = self.fetch_raw_klines(symbol, interval, limit=limit, end_time=current_end_time)
            if not klines:
                break
            all_klines = klines + all_klines
            fetched += len(klines)
            # Oldest timestamp in current batch minus 1ms becomes new end_time
            oldest_open_time = klines[0][0]
            current_end_time = oldest_open_time - 1

            if len(klines) < limit:
                break  # Reached earliest available data
            time.sleep(0.1)  # Rate limiting courtesy

        # Deduplicate and sort
        df = self._klines_to_dataframe(all_klines)
        self.save_to_cache(symbol, interval, df)
        return df

    def _klines_to_dataframe(self, klines: List[List[Any]]) -> pd.DataFrame:
        if not klines:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "close_time"])

        columns = [
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades_count",
            "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
        ]
        df = pd.DataFrame(klines, columns=columns)
        df["timestamp"] = pd.to_numeric(df["timestamp"])
        df["open"] = pd.to_numeric(df["open"])
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])
        df["close"] = pd.to_numeric(df["close"])
        df["volume"] = pd.to_numeric(df["volume"])
        df["close_time"] = pd.to_numeric(df["close_time"])
        
        # Deduplicate by timestamp and sort ascending
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        return df[["timestamp", "open", "high", "low", "close", "volume", "close_time"]]

    def save_to_cache(self, symbol: str, interval: str, df: pd.DataFrame) -> None:
        filepath = self._get_cache_filepath(symbol, interval)
        df.to_csv(filepath, index=False)
        logger.info(f"Saved {len(df)} candles to {filepath}")

    def load_from_cache(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        filepath = self._get_cache_filepath(symbol, interval)
        if os.path.exists(filepath):
            try:
                df = pd.read_csv(filepath)
                df["timestamp"] = pd.to_numeric(df["timestamp"])
                df["open"] = pd.to_numeric(df["open"])
                df["high"] = pd.to_numeric(df["high"])
                df["low"] = pd.to_numeric(df["low"])
                df["close"] = pd.to_numeric(df["close"])
                df["volume"] = pd.to_numeric(df["volume"])
                df["close_time"] = pd.to_numeric(df["close_time"])
                return df.sort_values("timestamp").reset_index(drop=True)
            except Exception as e:
                logger.warning(f"Failed to read cache {filepath}: {e}")
        return None

    def get_candles(self, symbol: str, interval: str, min_candles: int = 500,
                    force_refresh: bool = False) -> pd.DataFrame:
        """Get candles from cache if valid, otherwise fetch from Binance."""
        if not force_refresh:
            cached_df = self.load_from_cache(symbol, interval)
            if cached_df is not None and not cached_df.empty:
                return cached_df
        
        return self.download_historical_candles(symbol, interval, total_candles=min_candles)
