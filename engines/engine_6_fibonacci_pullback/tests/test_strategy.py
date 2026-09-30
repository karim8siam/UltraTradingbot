"""
Comprehensive Test Suite for Binance Fibonacci Pullback Trading Bot
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.types import (
    Candle,
    FibZoneCategory,
    ImpulseLeg,
    PositionSide,
    SetupRejectReason,
    SwingPoint,
    TradeRecord,
    TrendType,
)
from core.swings import SwingDetector
from core.trend import TrendDetector
from core.impulse import ImpulseDetector
from core.fibonacci import FibonacciCalculator
from core.pullback import PullbackDetector
from core.confirmation import ConfirmationEngine
from core.setup_scorer import SetupScorer
from core.risk_engine import RiskEngine
from core.indicators import calculate_atr, calculate_average_body, calculate_atr_ratio
from risk.risk_manager import RiskManager
from storage.database import Database


class TestFibonacciBot(unittest.TestCase):
    def setUp(self):
        # Create sample deterministic synthetic candles
        self.candles = []
        base_price = 50000.0
        for i in range(100):
            # Up-down-up wave
            if i < 20:
                p = base_price + (i * 100)
            elif i < 40:
                p = base_price + 2000 - ((i - 20) * 80)
            elif i < 60:
                p = base_price + 400 + ((i - 40) * 150)
            else:
                p = base_price + 3400 - ((i - 60) * 50)
            self.candles.append(
                Candle(
                    timestamp=1700000000000 + (i * 300000),
                    open=p,
                    high=p + 20,
                    low=p - 20,
                    close=p + 5,
                    volume=100.0,
                )
            )

    def test_indicators(self):
        atr_vals = calculate_atr(self.candles, period=14)
        self.assertEqual(len(atr_vals), 100)
        self.assertGreater(atr_vals[-1], 0)

        avg_body = calculate_average_body(self.candles, period=10)
        self.assertGreater(avg_body, 0)

        atr_ratio = calculate_atr_ratio(self.candles)
        self.assertGreater(atr_ratio, 0)

    def test_swing_detector(self):
        detector = SwingDetector(swing_length=2)
        swings = detector.find_all_swings(self.candles, '5m')
        self.assertGreater(len(swings), 0)
        highs = [s for s in swings if s.is_high]
        lows = [s for s in swings if s.is_low]
        self.assertGreater(len(highs), 0)
        self.assertGreater(len(lows), 0)

    def test_trend_detector(self):
        detector = TrendDetector()
        trend, highs, lows = detector.classify_trend(self.candles, '5m')
        self.assertIn(trend, [TrendType.BULLISH, TrendType.BEARISH, TrendType.NEUTRAL])

    def test_fibonacci_calculator(self):
        start_swing = SwingPoint(index=0, timestamp=1700000000000, price=50000.0, is_high=False, is_low=True, timeframe='15m')
        end_swing = SwingPoint(index=10, timestamp=1700000010000, price=60000.0, is_high=True, is_low=False, timeframe='15m')
        impulse_long = ImpulseLeg(
            symbol='BTCUSDT',
            side=PositionSide.LONG,
            start_swing=start_swing,
            end_swing=end_swing,
            high=60000.0,
            low=50000.0,
            size=10000.0,
            atr14=500.0,
            timestamp=1700000010000,
        )

        fibs_long = FibonacciCalculator.calculate(impulse_long)
        self.assertAlmostEqual(fibs_long.fib_0, 60000.0)
        self.assertAlmostEqual(fibs_long.fib_382, 60000.0 - (10000.0 * 0.382))
        self.assertAlmostEqual(fibs_long.fib_500, 55000.0)
        self.assertAlmostEqual(fibs_long.fib_618, 60000.0 - (10000.0 * 0.618))
        self.assertAlmostEqual(fibs_long.fib_786, 60000.0 - (10000.0 * 0.786))
        self.assertAlmostEqual(fibs_long.fib_1000, 50000.0)

        # Test Bearish Fibonacci
        impulse_short = ImpulseLeg(
            symbol='BTCUSDT',
            side=PositionSide.SHORT,
            start_swing=end_swing,
            end_swing=start_swing,
            high=60000.0,
            low=50000.0,
            size=10000.0,
            atr14=500.0,
            timestamp=1700000010000,
        )
        fibs_short = FibonacciCalculator.calculate(impulse_short)
        self.assertAlmostEqual(fibs_short.fib_0, 50000.0)
        self.assertAlmostEqual(fibs_short.fib_382, 50000.0 + (10000.0 * 0.382))
        self.assertAlmostEqual(fibs_short.fib_500, 55000.0)
        self.assertAlmostEqual(fibs_short.fib_618, 50000.0 + (10000.0 * 0.618))
        self.assertAlmostEqual(fibs_short.fib_786, 50000.0 + (10000.0 * 0.786))
        self.assertAlmostEqual(fibs_short.fib_1000, 60000.0)

    def test_pullback_and_invalidation(self):
        detector = PullbackDetector()
        start_swing = SwingPoint(index=0, timestamp=1000, price=100.0, is_high=False, is_low=True, timeframe='15m')
        end_swing = SwingPoint(index=10, timestamp=2000, price=200.0, is_high=True, is_low=False, timeframe='15m')
        impulse = ImpulseLeg('BTCUSDT', PositionSide.LONG, start_swing, end_swing, 200.0, 100.0, 100.0, 5.0, 2000)
        fibs = FibonacciCalculator.calculate(impulse)

        # Normal pullback to 150 (50%)
        pb_candles = [
            Candle(timestamp=2100, open=190, high=195, low=150, close=155, volume=10),
        ]
        is_v, is_p, is_inv, pb_l, pb_h, z_cat = detector.evaluate_pullback(pb_candles, fibs, 0)
        self.assertTrue(is_v)
        self.assertTrue(is_p)
        self.assertFalse(is_inv)
        self.assertEqual(z_cat, FibZoneCategory.ZONE_500_618)

        # Invalidated pullback (closing below 78.6% = 121.4)
        inv_candles = [
            Candle(timestamp=2100, open=190, high=195, low=110, close=115, volume=10),
        ]
        is_v2, is_p2, is_inv2, _, _, _ = detector.evaluate_pullback(inv_candles, fibs, 0)
        self.assertTrue(is_inv2)

    def test_risk_engine_geometry(self):
        engine = RiskEngine(risk_per_trade=0.01, min_rr=2.0)
        conf_candle = Candle(timestamp=1000, open=150, high=160, low=148, close=158, volume=10)
        entry_px, rej = engine.calculate_entry_price(conf_candle, current_price=154.0, atr14=5.0, side=PositionSide.LONG)
        self.assertEqual(entry_px, 154.0)
        self.assertIsNone(rej)

        sl_px, rej_sl = engine.calculate_stop_loss(PositionSide.LONG, pullback_low=150.0, pullback_high=160.0, entry_price=154.0, atr14=5.0)
        self.assertEqual(sl_px, 149.5)  # 150 - (5.0 * 0.10)
        self.assertIsNone(rej_sl)

        start_s = SwingPoint(0, 1000, 100.0, False, True, '15m')
        end_s = SwingPoint(10, 2000, 170.0, True, False, '15m')
        impulse = ImpulseLeg('BTCUSDT', PositionSide.LONG, start_s, end_s, 170.0, 100.0, 70.0, 5.0, 2000)

        tp_px, rr, rej_tp = engine.calculate_take_profit(PositionSide.LONG, entry_px, sl_px, impulse)
        self.assertEqual(tp_px, 170.0)
        self.assertGreaterEqual(rr, 2.0)
        self.assertIsNone(rej_tp)

        # Sizing
        qty, risk_amt, is_valid = engine.calculate_position_size(10000.0, entry_px, sl_px)
        self.assertTrue(is_valid)
        self.assertEqual(risk_amt, 100.0)  # 1% of 10000

    def test_risk_manager_controls(self):
        mgr = RiskManager(max_daily_loss=0.02, max_consecutive_losses=3, max_daily_trades=5, max_open_positions=3)
        # Enable all sessions for testing
        mgr.trading_sessions = [(0, 0, 23, 59)]

        ts = 1700000000000
        # Valid trade
        rej = mgr.validate_new_trade('BTCUSDT', ts, 10000.0)
        self.assertIsNone(rej)

        # Max open positions
        mgr.on_trade_opened('BTCUSDT', ts)
        mgr.on_trade_opened('ETHUSDT', ts)
        mgr.on_trade_opened('SOLUSDT', ts)
        rej_pos = mgr.validate_new_trade('BNBUSDT', ts, 10000.0)
        self.assertEqual(rej_pos, SetupRejectReason.REJECTED_MAX_POSITIONS)

        # One position per symbol
        rej_dup = mgr.validate_new_trade('BTCUSDT', ts, 10000.0)
        self.assertEqual(rej_dup, SetupRejectReason.REJECTED_MAX_POSITIONS)

    def test_database(self):
        db_path = 'data/test_bot.db'
        if os.path.exists(db_path):
            os.remove(db_path)
        db = Database(db_path)

        record = TradeRecord(
            trade_id='test-123',
            timestamp=1700000000000,
            symbol='BTCUSDT',
            side='LONG',
            bias_4h='BULLISH',
            bias_1h='BULLISH',
            impulse_low=50000.0,
            impulse_high=55000.0,
            impulse_size=5000.0,
            atr=200.0,
            fib_236=53820.0,
            fib_382=53090.0,
            fib_500=52500.0,
            fib_618=51910.0,
            fib_786=51070.0,
            pullback_low=52000.0,
            pullback_high=55000.0,
            confirmation_level=52500.0,
            entry=52600.0,
            sl=51980.0,
            tp=55000.0,
            risk_amount=100.0,
            position_size=0.161,
            leverage=5,
            rr=3.87,
            setup_score=14,
            funding_rate=0.0001,
            entry_time=1700000000000,
            exit_time=1700003600000,
            exit_price=55000.0,
            gross_pnl=386.4,
            fees=4.5,
            funding_cost=0.0,
            net_pnl=381.9,
            result='WIN',
            exit_reason='TAKE_PROFIT',
            fib_zone='50.0-61.8%',
        )
        db.record_trade(record)
        trades = db.get_all_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]['trade_id'], 'test-123')
        self.assertEqual(trades[0]['result'], 'WIN')

        db.log_rejection('BTCUSDT', SetupRejectReason.REJECTED_LOW_RR, 'RR 1.5 < 2.0', 1700000000000)
        rejections = db.get_recent_rejections(10)
        self.assertEqual(len(rejections), 1)
        self.assertEqual(rejections[0]['reason'], 'REJECTED_LOW_RR')

        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == '__main__':
    unittest.main()
