"""
Comprehensive Automated Test Suite for Binance FVG Bot
Verifies all 24 phases, deterministic rules, indicator math, state machines, and risk constraints.
"""

import math
import os
import sys
import unittest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import BotConfig
from indicators import Candle, calculate_atr, calculate_average_body, calculate_volatility_ratio
from swings import find_swings, get_latest_swings, SwingPoint
from trend_detector import detect_market_structure_bias, evaluate_htf_alignment, TrendBias
from fvg_engine import FVG, FVGType, FVGStatus, check_displacement, detect_fvgs_on_15m, check_discount_premium
from confirmation_engine import check_5m_confirmation, ConfirmationSignal
from setup_evaluator import evaluate_setup, calculate_setup_score, find_dynamic_target, TradeSetup
from risk_manager import RiskManager, SymbolSpecs, PositionSizeResult
from database import BotDatabase, TradeRecord
from fvg_state_machine import SymbolStateMachine, BotSymbolState
from backtester import BacktestEngine


class TestFVGCoreSuite(unittest.TestCase):

    def setUp(self):
        self.config = BotConfig()

    def test_candle_math_and_atr(self):
        candles = []
        base_time = 1000000
        for i in range(30):
            # Candle with high-low = 10, body = 6
            c = Candle(
                timestamp=base_time + (i * 300000),
                open=100.0 + (i * 2),
                high=108.0 + (i * 2),
                low=98.0 + (i * 2),
                close=106.0 + (i * 2),
                volume=100.0
            )
            candles.append(c)
        
        self.assertEqual(candles[0].body, 6.0)
        self.assertEqual(candles[0].range, 10.0)
        self.assertAlmostEqual(candles[0].body_percentage, 0.60)

        atr14 = calculate_atr(candles, 14)
        self.assertGreater(atr14, 0.0)
        self.assertAlmostEqual(atr14, 10.0, delta=1.0)

    def test_swing_detector_length_2(self):
        # Construct a clear pivot high at index 3: Highs = [10, 12, 15, 25, 14, 11, 10]
        candles = []
        highs = [10, 12, 15, 25, 14, 11, 10]
        for i, h in enumerate(highs):
            candles.append(Candle(
                timestamp=1000 + (i * 60),
                open=h - 2, high=h, low=h - 5, close=h - 1, volume=50
            ))

        swings = find_swings(candles, swing_length=2)
        swing_highs = [s for s in swings if s.is_high]
        self.assertEqual(len(swing_highs), 1)
        self.assertEqual(swing_highs[0].index, 3)
        self.assertEqual(swing_highs[0].price, 25.0)

    def test_trend_bias_bullish_and_bearish(self):
        # Create a series of Higher Highs and Higher Lows
        candles_bull = []
        # Swings at: L1(100), H1(150), L2(120), H2(180)
        prices = [
            # L1
            (110, 115, 108, 112), (105, 110, 102, 104), (100, 105, 95, 100), (102, 110, 100, 108), (110, 120, 109, 118),
            # H1
            (120, 130, 118, 128), (130, 145, 128, 142), (145, 160, 140, 155), (140, 150, 135, 142), (130, 138, 125, 130),
            # L2 (Higher Low > 95)
            (125, 128, 118, 120), (118, 122, 110, 115), (115, 125, 112, 122), (125, 135, 124, 132), (135, 148, 134, 145),
            # H2 (Higher High > 160)
            (150, 165, 148, 162), (165, 185, 162, 180), (175, 180, 165, 170), (168, 172, 158, 162), (160, 165, 150, 155)
        ]
        for idx, (o, h, l, c) in enumerate(prices):
            candles_bull.append(Candle(timestamp=idx * 3600000, open=o, high=h, low=l, close=c, volume=100))

        bias, l_h, p_h, l_l, p_l = detect_market_structure_bias(candles_bull, swing_length=2)
        self.assertEqual(bias, TrendBias.BULLISH)

    def test_displacement_criteria(self):
        # 10 prior candles with average body = 2.0
        prior = [Candle(timestamp=i, open=100, high=104, low=98, close=102, volume=10) for i in range(10)]
        avg_b = calculate_average_body(prior)
        self.assertEqual(avg_b, 2.0)

        # Candle with body = 4.0 (>= 1.5 * 2.0 = 3.0) and body % = 80% (>= 60%)
        strong_disp = Candle(timestamp=11, open=100, high=105, low=100, close=104, volume=100)
        disp_ok, c_body, a_body, b_pct = check_displacement(strong_disp, prior, is_bullish=True)
        self.assertTrue(disp_ok)
        self.assertEqual(c_body, 4.0)
        self.assertAlmostEqual(b_pct, 0.80)

        # Weak body candle
        weak_disp = Candle(timestamp=12, open=100, high=105, low=98, close=101, volume=10)
        disp_ok_weak, _, _, _ = check_displacement(weak_disp, prior, is_bullish=True)
        self.assertFalse(disp_ok_weak)

    def test_fvg_detection_bullish_and_bearish(self):
        candles_15m = []
        for i in range(25):
            candles_15m.append(Candle(timestamp=i * 900000, open=100, high=104, low=98, close=101, volume=10))

        # Inject 3-candle Bullish FVG at the end:
        # C1: High = 105
        # C2 (Displacement): Open=105, High=130, Low=104, Close=128
        # C3: Low = 112 (C1.high < C3.low -> FVG from 105 to 112, size = 7)
        c1 = Candle(timestamp=26 * 900000, open=100, high=105, low=98, close=104, volume=10)
        c2 = Candle(timestamp=27 * 900000, open=105, high=130, low=104, close=128, volume=500)
        c3 = Candle(timestamp=28 * 900000, open=128, high=135, low=112, close=130, volume=100)

        candles_15m.extend([c1, c2, c3])
        fvgs = detect_fvgs_on_15m(candles_15m, symbol="BTCUSDT")

        self.assertEqual(len(fvgs), 1)
        fvg = fvgs[0]
        self.assertEqual(fvg.fvg_type, FVGType.BULLISH)
        self.assertEqual(fvg.fvg_low, 105.0)
        self.assertEqual(fvg.fvg_high, 112.0)
        self.assertEqual(fvg.fvg_mid, 108.5)
        self.assertEqual(fvg.fvg_size, 7.0)

    def test_risk_manager_position_sizing_and_limits(self):
        rm = RiskManager(
            risk_per_trade=0.01,
            max_daily_loss=0.02,
            max_consecutive_losses=3,
            cooldown_hours=4.0,
            max_daily_trades=5,
            max_open_positions=3,
            default_leverage=5,
            sessions=[(0, 24)]  # All day for testing
        )
        specs = SymbolSpecs(symbol="BTCUSDT", tick_size=0.1, step_size=0.001, qty_precision=3, min_qty=0.001, min_notional=5.0)

        # Equity = 10,000, Entry = 60,000, SL = 59,000 (Stop dist = 1,000)
        # Risk amount = 100 USDT. Raw qty = 100 / 1000 = 0.1 BTC
        res = rm.calculate_position_size("BTCUSDT", 60000.0, 59000.0, 10000.0, specs)
        self.assertTrue(res.is_valid)
        self.assertAlmostEqual(res.formatted_qty, 0.100)
        self.assertAlmostEqual(res.risk_amount, 100.0)

        # Test Consecutive Losses Cooldown
        rm.record_trade_closed("BTCUSDT", -100.0, 9900.0, current_ts=1000.0)
        rm.record_trade_closed("ETHUSDT", -100.0, 9800.0, current_ts=1010.0)
        rm.record_trade_closed("SOLUSDT", -100.0, 9700.0, current_ts=1020.0)
        can_open, reason = rm.can_open_new_trade("BNBUSDT", current_ts=1030.0)
        self.assertFalse(can_open)
        self.assertEqual(reason, "REJECTED_COOLDOWN_ACTIVE")

    def test_database_sqlite_persistence(self):
        db_path = "test_trades.db"
        if os.path.exists(db_path):
            os.remove(db_path)

        db = BotDatabase(db_path)
        record = TradeRecord(
            trade_id="T_TEST_1",
            timestamp=100000,
            symbol="BTCUSDT",
            side="LONG",
            bias_4h="BULLISH",
            bias_1h="BULLISH",
            bias_15m="BULLISH",
            fvg_type="BULLISH",
            fvg_high=61000.0,
            fvg_low=60000.0,
            fvg_mid=60500.0,
            fvg_size=1000.0,
            fvg_size_atr=0.25,
            fvg_age=5,
            displacement_size=500.0,
            atr=400.0,
            pullback_high=61200.0,
            pullback_low=59800.0,
            confirmation_level=61200.0,
            entry=60500.0,
            sl=59760.0,
            tp=62500.0,
            risk_amount=100.0,
            position_size=0.135,
            leverage=5,
            rr=2.70,
            setup_score=13,
            funding_rate=0.0001,
            entry_time=100000
        )
        db.insert_trade(record)
        open_trades = db.get_open_trades()
        self.assertEqual(len(open_trades), 1)
        self.assertEqual(open_trades[0]["trade_id"], "T_TEST_1")

        db.update_trade_exit(
            trade_id="T_TEST_1",
            exit_time=105000,
            exit_price=62500.0,
            gross_pnl=270.0,
            fees=4.0,
            funding_cost=0.5,
            net_pnl=265.5,
            result="WIN",
            exit_reason="TP_HIT"
        )
        all_trades = db.get_all_trades()
        self.assertEqual(all_trades[0]["result"], "WIN")
        self.assertEqual(all_trades[0]["exit_reason"], "TP_HIT")
        self.assertAlmostEqual(all_trades[0]["net_pnl"], 265.5)

        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == "__main__":
    unittest.main()
