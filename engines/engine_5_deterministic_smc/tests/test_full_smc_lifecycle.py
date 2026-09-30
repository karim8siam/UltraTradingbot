import unittest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from strategy.models import Candle, BiasType, SwingType, TradeSide
from strategy.setup_evaluator import SetupEvaluator
from strategy.state_machine import SymbolStateMachine

class TestFullSMCLifecycle(unittest.TestCase):
    def test_complete_smc_sequence(self):
        evaluator = SetupEvaluator(
            min_rr=2.0,
            min_score=11,
            sl_atr_multiplier=0.10,
            max_atr_ratio=2.5,
            allowed_sessions=[(0, 24)]
        )
        sm = SymbolStateMachine("BTCUSDT", evaluator, swing_length=2)

        # 1. 4H Bullish Market Structure: Swings L1=85, H1=120, L2=92, H2=130 (HH & HL)
        c4h = [
            Candle(1000, 100, 105, 100, 102, 10),
            Candle(2000, 102, 104, 95, 98, 10),
            Candle(3000, 98, 100, 85, 95, 10),    # Swing Low 1: 85
            Candle(4000, 95, 105, 95, 102, 10),
            Candle(5000, 102, 120, 100, 118, 10), # Swing High 1: 120
            Candle(6000, 118, 115, 98, 105, 10),
            Candle(7000, 105, 110, 92, 100, 10),  # Swing Low 2: 92 (HL)
            Candle(8000, 100, 115, 98, 112, 10),
            Candle(9000, 112, 130, 110, 128, 10), # Swing High 2: 130 (HH)
            Candle(10000, 128, 125, 118, 122, 10),
            Candle(11000, 122, 120, 115, 118, 10)
        ]
        # 2. 1H Bullish Market Structure
        c1h = list(c4h)

        # 3. 15M candles: Confirmed Swing Low at index 2 (Low=105), target Swing High at index 5 (High=135)
        # Latest 15M candle (index 8) sweeps below 105 (Low=103, Close=112)
        c15m = [
            Candle(1000, 110, 112, 108, 110, 10),
            Candle(2000, 110, 111, 107, 109, 10),
            Candle(3000, 109, 110, 105, 108, 10), # Swing Low at 105
            Candle(4000, 108, 115, 107, 114, 10),
            Candle(5000, 114, 120, 113, 119, 10),
            Candle(6000, 119, 145, 118, 142, 10), # Obvious Target Buy-Side Swing High at 145
            Candle(7000, 132, 130, 120, 122, 10),
            Candle(8000, 122, 124, 115, 116, 10),
            Candle(9000, 116, 118, 103, 112, 50)  # Liquidity Sweep Candle (Low 103 < 105, Close 112 > 105)
        ]

        # 4. 5M candles:
        # Pre-displacement swing high at index 4 (High=114)
        # Displacement candle at index 12 (Close=118 > 114 -> MSS!)
        # FVG at index 13 (C1 High=113, C3 Low=115 -> Midpoint=114)
        c5m = [
            Candle(1000, 110, 112, 109, 111, 10),
            Candle(2000, 111, 113, 110, 112, 10),
            Candle(3000, 112, 113.5, 111, 113, 10),
            Candle(4000, 113, 113.8, 112, 113.5, 10),
            Candle(5000, 113.5, 114.0, 112.5, 113.8, 10), # Swing High: 114.0
            Candle(6000, 113.8, 113.5, 111.0, 112.0, 10),
            Candle(7000, 112.0, 112.5, 110.0, 111.0, 10),
            Candle(8000, 111.0, 111.5, 108.0, 109.0, 10),
            Candle(9000, 109.0, 110.0, 105.0, 108.0, 10),
            Candle(10000, 108.0, 109.0, 104.0, 107.0, 10),
            Candle(11000, 107.0, 113.0, 106.5, 112.8, 10), # C1 for FVG: High = 113.0
            Candle(12000, 112.8, 118.5, 112.5, 118.0, 100),# Displacement (Body 5.2 >= 1.5x, Body% 86%), Closes at 118.0 > 114.0 (MSS!)
            Candle(13000, 118.0, 120.0, 115.0, 119.5, 30)  # C3 for FVG: Low = 115.0 (FVG: [113.0, 115.0], Midpoint=114.0)
        ]

        setup, status = sm.process_candles(c4h, c1h, c15m, c5m)
        self.assertIsNotNone(setup)
        self.assertEqual(setup.side, TradeSide.LONG)
        self.assertEqual(setup.entry_price, 114.0)
        self.assertGreaterEqual(setup.setup_score, 11)
        self.assertGreaterEqual(setup.rr, 2.0)
        print(f"\n[SUCCESS] Deterministic SMC Setup Fully Verified!")
        print(f"  Symbol: {setup.symbol}")
        print(f"  Side: {setup.side.value}")
        print(f"  4H Bias: {setup.bias_4h.value}")
        print(f"  1H Bias: {setup.bias_1h.value}")
        print(f"  Sweep Low: {setup.sweep_event.sweep_low}")
        print(f"  MSS Broken Level: {setup.mss_event.broken_swing_level}")
        print(f"  FVG Midpoint (Entry): {setup.entry_price}")
        print(f"  Stop Loss: {setup.stop_loss:.2f}")
        print(f"  Target Take Profit: {setup.take_profit}")
        print(f"  Calculated RR: {setup.rr:.2f}")
        print(f"  Setup Score: {setup.setup_score}/14")

if __name__ == "__main__":
    unittest.main()
