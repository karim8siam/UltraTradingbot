import logging
from typing import List, Dict, Any
from strategy.models import Candle
from backtesting.engine import BacktestEngine
from backtesting.metrics import PerformanceMetrics
from config import Config

logger = logging.getLogger("SplitTester")

class SplitTester:
    def __init__(self, config: Config):
        self.config = config
        self.engine = BacktestEngine(config)

    def run_split_tests(self, symbol: str, candles_4h: List[Candle], candles_1h: List[Candle],
                        candles_15m: List[Candle], candles_5m: List[Candle]) -> Dict[str, Any]:
        """
        Runs 60% Development, 20% Validation, 20% Out-Of-Sample Backtests.
        """
        n_5m = len(candles_5m)
        dev_end_idx = int(n_5m * 0.60)
        val_end_idx = int(n_5m * 0.80)

        dev_5m = candles_5m[:dev_end_idx]
        val_5m = candles_5m[dev_end_idx:val_end_idx]
        oos_5m = candles_5m[val_end_idx:]

        # Function to slice matching timeframe bars
        def slice_tf(candles: List[Candle], end_ts: int, start_ts: int = 0):
            return [c for c in candles if start_ts <= c.timestamp <= end_ts]

        # 1. Development Split (60%)
        dev_res = self.engine.run_backtest(
            symbol,
            slice_tf(candles_4h, dev_5m[-1].timestamp),
            slice_tf(candles_1h, dev_5m[-1].timestamp),
            slice_tf(candles_15m, dev_5m[-1].timestamp),
            dev_5m,
            initial_capital=self.config.INITIAL_EQUITY
        )

        # 2. Validation Split (20%)
        val_res = self.engine.run_backtest(
            symbol,
            slice_tf(candles_4h, val_5m[-1].timestamp, val_5m[0].timestamp - 4*3600*1000*50),
            slice_tf(candles_1h, val_5m[-1].timestamp, val_5m[0].timestamp - 3600*1000*50),
            slice_tf(candles_15m, val_5m[-1].timestamp, val_5m[0].timestamp - 15*60*1000*50),
            val_5m,
            initial_capital=self.config.INITIAL_EQUITY
        )

        # 3. Out-of-Sample Split (20%)
        oos_res = self.engine.run_backtest(
            symbol,
            slice_tf(candles_4h, oos_5m[-1].timestamp, oos_5m[0].timestamp - 4*3600*1000*50),
            slice_tf(candles_1h, oos_5m[-1].timestamp, oos_5m[0].timestamp - 3600*1000*50),
            slice_tf(candles_15m, oos_5m[-1].timestamp, oos_5m[0].timestamp - 15*60*1000*50),
            oos_5m,
            initial_capital=self.config.INITIAL_EQUITY
        )

        return {
            "symbol": symbol,
            "development_60": dev_res["metrics"],
            "validation_20": val_res["metrics"],
            "out_of_sample_20": oos_res["metrics"]
        }
