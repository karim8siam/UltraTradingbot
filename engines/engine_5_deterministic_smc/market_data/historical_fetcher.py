import time
import logging
from typing import List, Dict, Any, Optional
from market_data.binance_client import BinanceFuturesClient
from market_data.candle_manager import CandleManager

logger = logging.getLogger("HistoricalFetcher")

class HistoricalFetcher:
    def __init__(self, client: BinanceFuturesClient, candle_manager: CandleManager):
        self.client = client
        self.candle_manager = candle_manager

    def fetch_all_timeframes_for_symbol(self, symbol: str,
                                        limit_4h: int = 500,
                                        limit_1h: int = 1000,
                                        limit_15m: int = 2000,
                                        limit_5m: int = 3000):
        """
        Fetches full warm-up history across 4H, 1H, 15M, and 5M.
        """
        tf_targets = [
            ("4h", limit_4h),
            ("1h", limit_1h),
            ("15m", limit_15m),
            ("5m", limit_5m)
        ]

        logger.info(f"[{symbol}] Starting historical data warm-up...")
        for tf, target_count in tf_targets:
            klines = self.fetch_paginated_klines(symbol, tf, target_count)
            self.candle_manager.load_historical_klines(symbol, tf, klines)
            time.sleep(0.1)  # Respect rate limits

    def fetch_paginated_klines(self, symbol: str, interval: str, target_count: int) -> List[List[Any]]:
        import json
        import urllib.request
        import urllib.parse
        
        all_klines: List[List[Any]] = []
        batch_size = 1000
        mirrors = [
            ("https://api.binance.com", "/api/v3/klines"),
            ("https://data-api.binance.vision", "/api/v3/klines"),
            ("https://fapi.binance.com", "/fapi/v1/klines")
        ]

        while len(all_klines) < target_count:
            fetch_limit = min(batch_size, target_count - len(all_klines))
            params: dict = {
                "symbol": symbol,
                "interval": interval,
                "limit": fetch_limit
            }
            if all_klines:
                oldest_ts = all_klines[0][0]
                params["endTime"] = oldest_ts - 1

            batch = None
            query_str = urllib.parse.urlencode(params)
            
            for base_host, endpoint in mirrors:
                url = f"{base_host}{endpoint}?{query_str}"
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        batch = json.loads(resp.read().decode("utf-8"))
                        if batch and isinstance(batch, list):
                            break
                except Exception:
                    continue

            if not batch:
                break

            if all_klines:
                all_klines = batch + all_klines
            else:
                all_klines = batch

            if len(batch) < fetch_limit:
                break

            time.sleep(0.05)

        return all_klines
