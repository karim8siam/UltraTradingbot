"""
Unit and Integration Tests for Binance Futures Systematic Swing Strategy.
"""

import unittest
import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG
from strategy.indicators import (
    calculate_ema_series, calculate_atr_series, calculate_adx_series,
    calculate_average_body, is_displacement_candle
)
from strategy.structure import SwingDetector, MarketStructureEngine, TrendDirection
from strategy.impulse_pullback import ImpulseDetector, PullbackEngine, ImpulseMove
from strategy.scorer import SetupScorer
from risk.risk_manager import RiskManager
from exchange.binance_client import SymbolInfo


class TestIndicators(unittest.TestCase):
    def test_ema_calculation(self):
        prices = np.array([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0])
        ema = calculate_ema_series(prices, period=5)
        self.assertEqual(len(ema), len(prices))
        self.assertTrue(np.isnan(ema[0]))
        self.assertEqual(ema[4], 12.0)  # Initial SMA
        self.assertGreater(ema[-1], ema[-2])  # Positive slope

    def test_displacement_candle(self):
        avg_body = 10.0
        # Valid bullish displacement: body = 15 (>= 1.25 * 10), range = 20 (15/20 = 75% >= 55%)
        valid, metrics = is_displacement_candle(
            open_price=100.0, high=120.0, low=100.0, close=115.0,
            avg_body=avg_body, is_bullish=True
        )
        self.assertTrue(valid)
        self.assertEqual(metrics["body"], 15.0)

        # Invalid displacement (weak body percentage, large wicks: open=100, close=115, high=150, low=90 -> body=15, range=60 -> 25% < 55%)
        invalid, metrics2 = is_displacement_candle(
            open_price=100.0, high=150.0, low=90.0, close=115.0,
            avg_body=avg_body, is_bullish=True
        )
        self.assertFalse(invalid)


class TestStructureAndSwings(unittest.TestCase):
    def test_zero_lookahead_swing_detection(self):
        highs = np.array([10.0, 12.0, 15.0, 13.0, 11.0, 14.0, 12.0])
        lows = np.array([5.0, 6.0, 8.0, 7.0, 6.0, 8.0, 7.0])
        detector = SwingDetector(swing_length=2)

        # Bar index 2 is a peak (15.0 > 10, 12 and > 13, 11)
        # It must only be confirmed at index 4 (i + 2)
        swings = detector.find_swings(highs, lows)
        self.assertTrue(any(s.index == 2 and s.is_high and s.price == 15.0 for s in swings))
        sh = [s for s in swings if s.is_high and s.index == 2][0]
        self.assertEqual(sh.confirmed_index, 4)

    def test_daily_trend_rules(self):
        struct = MarketStructureEngine(daily_ema_fast=5, daily_ema_slow=10)
        # Strictly increasing prices
        closes = np.linspace(100, 200, 50)
        trend, info = struct.evaluate_daily_trend(closes)
        self.assertEqual(trend, TrendDirection.BULLISH)
        self.assertGreater(info["daily_ema50"], info["daily_ema200"])
        self.assertGreater(info["ema50_slope"], 0)


class TestFibonacciAndPullback(unittest.TestCase):
    def test_bullish_pullback_confluence(self):
        engine = PullbackEngine(max_retracement=0.705)
        impulse = ImpulseMove(
            start_index=0, end_index=5,
            start_price=100.0, end_price=200.0,
            is_bullish=True, atr14=10.0, avg_body=8.0,
            volume=1000.0, avg_volume=800.0, volume_ratio=1.25
        )
        # Pullback from 200 down to 150 (50% retracement)
        highs = np.array([200.0, 190.0, 180.0, 170.0, 160.0, 150.0])
        lows = np.array([190.0, 180.0, 170.0, 160.0, 150.0, 150.0])
        closes = np.array([195.0, 185.0, 175.0, 165.0, 155.0, 150.0])

        pb = engine.evaluate_pullback(highs, lows, closes, impulse, four_h_ema20=165.0, four_h_ema50=145.0)
        self.assertTrue(pb.is_valid)
        self.assertAlmostEqual(pb.pullback_depth, 0.50, places=2)
        self.assertAlmostEqual(pb.fib_500, 150.0, places=2)
        self.assertTrue(pb.has_confluence_overlap)


class TestRiskManager(unittest.TestCase):
    def test_position_sizing(self):
        rm = RiskManager(DEFAULT_CONFIG)
        # 1% of $10,000 = $100 risk
        # Entry = 100, SL = 95 -> Stop Distance = 5
        # Quantity = 100 / 5 = 20 units
        res = rm.calculate_position_size(
            symbol="BTCUSDT",
            entry_price=100.0,
            stop_loss=95.0,
            account_equity=10000.0
        )
        self.assertTrue(res.is_valid)
        self.assertAlmostEqual(res.risk_amount, 100.0)
        self.assertAlmostEqual(res.raw_quantity, 20.0)
        self.assertEqual(res.leverage, 3)

    def test_portfolio_limits(self):
        rm = RiskManager(DEFAULT_CONFIG)
        # 3 existing positions -> reject 4th
        open_positions = [
            {"symbol": "BTCUSDT", "risk_amount": 100.0},
            {"symbol": "ETHUSDT", "risk_amount": 100.0},
            {"symbol": "SOLUSDT", "risk_amount": 100.0}
        ]
        can_open, reason = rm.can_open_new_trade(
            candidate_symbol="BNBUSDT",
            current_equity=10000.0,
            open_positions=open_positions
        )
        self.assertFalse(can_open)
        self.assertEqual(reason, "REJECTED_MAX_POSITIONS")


class TestScorer(unittest.TestCase):
    def test_setup_score_threshold(self):
        scorer = SetupScorer(DEFAULT_CONFIG)
        # Perfect bullish setup with score >= 14
        eval_res = scorer.score_setup(
            symbol="BTCUSDT",
            direction="LONG",
            daily_trend_aligned=True,       # +2
            daily_structure_aligned=True,   # +2
            four_h_trend_aligned=True,      # +2
            strong_4h_impulse=True,         # +2
            ema_fib_overlap=True,           # +2
            valid_4h_pullback=True,         # +2
            one_h_structure_confirm=True,   # +2
            one_h_displacement=True,        # +2
            adx_4h=26.0,                    # +1
            volume_confirmed=True,          # +1
            clear_structural_target=True,   # +1
            rr_ratio=3.0,                   # +2
            is_extreme_volatility=False,
            is_extreme_funding=False,
            details={}
        )
        self.assertTrue(eval_res.is_valid)
        self.assertEqual(eval_res.total_score, 21)
        self.assertGreaterEqual(eval_res.total_score, 14)


if __name__ == "__main__":
    unittest.main()
