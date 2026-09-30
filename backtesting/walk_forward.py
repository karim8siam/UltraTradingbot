"""
Walk-Forward & Out-of-Sample Validation Engine.
Implements 60/20/20 data split and rolling walk-forward evaluation (Sections 67 & 68).
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import pandas as pd

from config import Config
from .engine import BacktestEngine, BacktestResult
from .metrics import PerformanceMetrics


@dataclass
class WindowPerformance:
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_metrics: PerformanceMetrics
    test_metrics: PerformanceMetrics


@dataclass
class WalkForwardResult:
    windows: List[WindowPerformance]
    dev_split_metrics: PerformanceMetrics
    val_split_metrics: PerformanceMetrics
    oos_split_metrics: PerformanceMetrics


class WalkForwardEngine:
    def __init__(self, config: Config):
        self.config = config

    def split_data_60_20_20(self, symbols_data: Dict[str, Dict[str, pd.DataFrame]]) -> Tuple[
        Dict[str, Dict[str, pd.DataFrame]],
        Dict[str, Dict[str, pd.DataFrame]],
        Dict[str, Dict[str, pd.DataFrame]]
    ]:
        """
        Splits data chronologically into 60% Development, 20% Validation, and 20% Out-of-Sample.
        """
        dev_data: Dict[str, Dict[str, pd.DataFrame]] = {}
        val_data: Dict[str, Dict[str, pd.DataFrame]] = {}
        oos_data: Dict[str, Dict[str, pd.DataFrame]] = {}

        for sym, tfs in symbols_data.items():
            dev_data[sym] = {}
            val_data[sym] = {}
            oos_data[sym] = {}

            for tf, df in tfs.items():
                if df.empty:
                    continue
                n = len(df)
                idx_60 = int(n * 0.60)
                idx_80 = int(n * 0.80)

                dev_data[sym][tf] = df.iloc[:idx_60].copy().reset_index(drop=True)
                val_data[sym][tf] = df.iloc[idx_60:idx_80].copy().reset_index(drop=True)
                oos_data[sym][tf] = df.iloc[idx_80:].copy().reset_index(drop=True)

        return dev_data, val_data, oos_data

    def run_split_evaluation(self, symbols_data: Dict[str, Dict[str, pd.DataFrame]]) -> Tuple[BacktestResult, BacktestResult, BacktestResult]:
        """Runs backtest separately across Dev (60%), Validation (20%), and OOS (20%)."""
        dev_data, val_data, oos_data = self.split_data_60_20_20(symbols_data)

        engine_dev = BacktestEngine(config=self.config)
        res_dev = engine_dev.run(dev_data)

        engine_val = BacktestEngine(config=self.config)
        res_val = engine_val.run(val_data)

        engine_oos = BacktestEngine(config=self.config)
        res_oos = engine_oos.run(oos_data)

        return res_dev, res_val, res_oos
