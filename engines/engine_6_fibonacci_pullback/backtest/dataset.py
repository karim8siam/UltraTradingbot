"""
Dataset Loader, Partitioner & Synthetic Market Generator
Sections 57, 58, 62 Specification
"""

import datetime
import math
import random
from typing import Dict, List, Tuple
from core.types import Candle
from config.constants import (
    TRAIN_SPLIT_RATIO,
    VAL_SPLIT_RATIO,
    OOS_SPLIT_RATIO,
)


class HistoricalDataset:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.candles_4h: List[Candle] = []
        self.candles_1h: List[Candle] = []
        self.candles_15m: List[Candle] = []
        self.candles_5m: List[Candle] = []

    def partition_data(self) -> Tuple['HistoricalDataset', 'HistoricalDataset', 'HistoricalDataset']:
        """
        Splits data according to Section 62:
        60% Development (Train)
        20% Validation (Val)
        20% Out-of-Sample (OOS - strictly unseen)
        """
        n_5m = len(self.candles_5m)
        train_end_5m = int(n_5m * TRAIN_SPLIT_RATIO)
        val_end_5m = int(n_5m * (TRAIN_SPLIT_RATIO + VAL_SPLIT_RATIO))

        train_ts_end = self.candles_5m[train_end_5m - 1].timestamp if train_end_5m > 0 else 0
        val_ts_end = self.candles_5m[val_end_5m - 1].timestamp if val_end_5m > 0 else 0

        def _split_by_ts(candles: List[Candle]):
            c_train = [c for c in candles if c.timestamp <= train_ts_end]
            c_val = [c for c in candles if train_ts_end < c.timestamp <= val_ts_end]
            c_oos = [c for c in candles if c.timestamp > val_ts_end]
            return c_train, c_val, c_oos

        train_set = HistoricalDataset(self.symbol)
        val_set = HistoricalDataset(self.symbol)
        oos_set = HistoricalDataset(self.symbol)

        train_set.candles_4h, val_set.candles_4h, oos_set.candles_4h = _split_by_ts(self.candles_4h)
        train_set.candles_1h, val_set.candles_1h, oos_set.candles_1h = _split_by_ts(self.candles_1h)
        train_set.candles_15m, val_set.candles_15m, oos_set.candles_15m = _split_by_ts(self.candles_15m)
        train_set.candles_5m, val_set.candles_5m, oos_set.candles_5m = _split_by_ts(self.candles_5m)

        return train_set, val_set, oos_set

    @staticmethod
    def generate_synthetic_data(
        symbol: str = "BTCUSDT",
        num_5m_candles: int = 5000,
        base_price: float = 50000.0,
        volatility: float = 0.003,
        seed: int = 42,
    ) -> 'HistoricalDataset':
        """
        Generates realistic multi-timeframe geometric Brownian motion market data with
        emergent swing trends and pullbacks for deterministic testing.
        """
        random.seed(seed)
        start_ts = 1700000000000  # Nov 2023 in ms
        interval_5m = 5 * 60 * 1000

        candles_5m: List[Candle] = []
        current_price = base_price

        # Multi-frequency cycles for realistic trend swings
        for i in range(num_5m_candles):
            ts = start_ts + (i * interval_5m)
            # Trend component + random walk
            macro_trend = math.sin(i / 600.0) * 0.0008 + math.cos(i / 150.0) * 0.0005
            shock = random.gauss(0, volatility)
            ret = macro_trend + shock

            o = current_price
            c = o * (1.0 + ret)
            h = max(o, c) * (1.0 + abs(random.gauss(0, volatility * 0.5)))
            l = min(o, c) * (1.0 - abs(random.gauss(0, volatility * 0.5)))
            v = random.uniform(10.0, 100.0)

            candles_5m.append(
                Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=v, close_time=ts + interval_5m - 1)
            )
            current_price = c

        # Resample into 15M, 1H, 4H
        def _resample(candles: List[Candle], group_size: int, tf_ms: int) -> List[Candle]:
            res = []
            for k in range(0, len(candles) - group_size + 1, group_size):
                grp = candles[k : k + group_size]
                o = grp[0].open
                h = max(c.high for c in grp)
                l = min(c.low for c in grp)
                c_close = grp[-1].close
                v = sum(c.volume for c in grp)
                ts = grp[0].timestamp
                res.append(
                    Candle(timestamp=ts, open=o, high=h, low=l, close=c_close, volume=v, close_time=ts + tf_ms - 1)
                )
            return res

        ds = HistoricalDataset(symbol)
        ds.candles_5m = candles_5m
        ds.candles_15m = _resample(candles_5m, 3, 15 * 60 * 1000)
        ds.candles_1h = _resample(candles_5m, 12, 60 * 60 * 1000)
        ds.candles_4h = _resample(candles_5m, 48, 4 * 60 * 60 * 1000)
        return ds
