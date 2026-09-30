import unittest
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from strategy.models import Candle, BiasType, SwingType, TradeSide, LiquidityType, LiquidityLevel, SweepEvent, MSSEvent, FVGEvent
from strategy.swing_detector import SwingDetector
from strategy.market_structure import MarketStructure
from strategy.liquidity import LiquidityDetector
from strategy.displacement import DisplacementDetector
from strategy.mss_detector import MSSDetector
from strategy.fvg_detector import FVGDetector
from strategy.setup_evaluator import SetupEvaluator
from execution.risk_manager import RiskManager
from database import Database

class TestSMCBot(unittest.TestCase):
    def test_swing_detector(self):
        detector = SwingDetector(swing_length=2)
        # Create a peak at index 2
        candles = [
            Candle(1000, 100, 105, 95, 100, 10),
            Candle(2000, 100, 110, 95, 105, 10),
            Candle(3000, 105, 125, 100, 120, 10), # Swing High (125 > 105, 110, 115, 110)
            Candle(4000, 120, 115, 100, 110, 10),
            Candle(5000, 110, 110, 95, 100, 10),
            Candle(6000, 100, 105, 90, 95, 10)
        ]
        swings = detector.find_swings(candles)
        self.assertTrue(any(s.swing_type == SwingType.HIGH and s.price == 125 for s in swings))

    def test_displacement_detector(self):
        disp_detector = DisplacementDetector(avg_body_period=5, multiplier=1.5, min_body_pct=0.60)
        # 5 small candles with body size 2
        candles = [Candle(i * 1000, 100, 104, 98, 102, 10) for i in range(5)]
        # 6th candle: huge displacement body 10 (100 -> 110, High 111, Low 99.5, body% = 10 / 11.5 = 87%)
        candles.append(Candle(6000, 100, 111, 99.5, 110, 50))

        disp = disp_detector.check_displacement(candles)
        self.assertIsNotNone(disp)
        self.assertTrue(disp.is_bullish)
        self.assertGreaterEqual(disp.body_percentage, 0.60)

    def test_fvg_detector(self):
        fvg_detector = FVGDetector()
        # Candle 1: High = 105
        # Candle 2: Big bullish move 105 -> 120 (Displacement at ts 2000)
        # Candle 3: Low = 112 (Gap between C1 High 105 and C3 Low 112)
        candles = [
            Candle(1000, 100, 105, 98, 104, 10),
            Candle(2000, 104, 122, 103, 120, 50),
            Candle(3000, 120, 128, 112, 125, 20)
        ]
        fvg = fvg_detector.detect_fvg(candles, is_bullish=True, displacement_ts=2000)
        self.assertIsNotNone(fvg)
        self.assertEqual(fvg.fvg_low, 105)
        self.assertEqual(fvg.fvg_high, 112)
        self.assertEqual(fvg.midpoint, 108.5)

    def test_risk_manager_limits(self):
        rm = RiskManager(risk_per_trade=0.01, max_daily_loss=0.02, max_consecutive_losses=3, max_daily_trades=5, max_open_positions=3)
        now_utc = datetime.now(timezone.utc)

        # Normal trade check
        ok, reason = rm.check_trade_allowed(10000, 10000, 0.0, 0, 0, False, now_utc)
        self.assertTrue(ok)

        # Exceed daily loss limit (Loss -2.5% > -2%)
        ok_loss, reason_loss = rm.check_trade_allowed(9750, 10000, -250.0, 2, 0, False, now_utc)
        self.assertFalse(ok_loss)
        self.assertIn("DAILY_LOSS_LIMIT", reason_loss)

        # Exceed max daily trades (5 trades reached)
        ok_trades, reason_trades = rm.check_trade_allowed(10100, 10000, 100.0, 5, 0, False, now_utc)
        self.assertFalse(ok_trades)
        self.assertIn("MAX_DAILY_TRADES", reason_trades)

        # Exceed max open positions (3 positions reached)
        ok_pos, reason_pos = rm.check_trade_allowed(10100, 10000, 100.0, 3, 3, False, now_utc)
        self.assertFalse(ok_pos)
        self.assertIn("MAX_OPEN_POSITIONS", reason_pos)

        # Consecutive loss cooldown
        rm.record_trade_outcome(False, now_utc)
        rm.record_trade_outcome(False, now_utc)
        rm.record_trade_outcome(False, now_utc)
        ok_cd, reason_cd = rm.check_trade_allowed(10000, 10000, 0.0, 3, 0, False, now_utc)
        self.assertFalse(ok_cd)
        self.assertIn("COOLDOWN_ACTIVE", reason_cd)

    def test_database_logging(self):
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name
        try:
            db = Database(db_path)
            db.log_rejected_signal("BTCUSDT", "REJECTED_LOW_RR", "BULLISH", "BULLISH", 10, 1.5)
            db.record_trade_opened({
                "trade_id": "TEST_001",
                "symbol": "BTCUSDT",
                "side": "LONG",
                "bias_4h": "BULLISH",
                "bias_1h": "BULLISH",
                "bias_15m": "BULLISH",
                "liquidity_type": "SWING_LOW",
                "liquidity_level": 60000.0,
                "sweep_high": 60200.0,
                "sweep_low": 59800.0,
                "mss_level": 60500.0,
                "displacement_size": 60400.0,
                "fvg_high": 60600.0,
                "fvg_low": 60200.0,
                "fvg_midpoint": 60400.0,
                "entry": 60400.0,
                "stop_loss": 59750.0,
                "take_profit": 62000.0,
                "risk_amount": 100.0,
                "position_size": 0.15,
                "leverage": 5,
                "rr": 2.46,
                "setup_score": 12,
                "atr": 500.0,
                "funding_rate": 0.0001,
                "entry_time": "2026-09-01T00:00:00Z",
                "result": "OPEN",
                "client_order_id": "TEST_001",
                "sl_order_id": "SL_001",
                "tp_order_id": "TP_001",
                "mode": "DRY_RUN"
            })
            open_trades = db.get_open_trades()
            self.assertEqual(len(open_trades), 1)
            self.assertEqual(open_trades[0]["trade_id"], "TEST_001")
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

if __name__ == "__main__":
    unittest.main()
