import unittest
from datetime import datetime, timezone
from risk_manager import RiskManager, SymbolFilters


class TestRiskManager(unittest.TestCase):
    def setUp(self):
        self.rm = RiskManager(starting_equity=10000.0, enforce_sessions=False)
        self.rm.set_symbol_filter("BTCUSDT", SymbolFilters(
            symbol="BTCUSDT",
            price_precision=2,
            quantity_precision=3,
            step_size=0.001,
            min_qty=0.001,
            min_notional=5.0
        ))

    def test_position_sizing_1_percent_risk(self):
        # Equity = 10,000 -> 1% Risk = $100
        # Entry = 50,000, SL = 49,000 -> Stop Distance = 1,000
        # Position size = 100 / 1000 = 0.10 BTC
        qty, risk_amt, notional, status = self.rm.calculate_position_size(
            symbol="BTCUSDT",
            equity=10000.0,
            entry_price=50000.0,
            stop_loss=49000.0
        )
        self.assertEqual(status, "OK")
        self.assertAlmostEqual(qty, 0.10)
        self.assertAlmostEqual(risk_amt, 100.0)
        self.assertAlmostEqual(notional, 5000.0)

    def test_daily_loss_limit(self):
        # 2% Max Daily Loss of 10,000 = $200
        # Equity drops to 9,750 (-$250 loss)
        allowed, reason = self.rm.check_trade_allowed("BTCUSDT", current_equity=9750.0)
        self.assertFalse(allowed)
        self.assertEqual(reason, "REJECTED_DAILY_LOSS_LIMIT_REACHED")

    def test_consecutive_losses_cooldown(self):
        # 3 consecutive losses
        self.rm.record_trade_closed(-50.0)
        self.rm.record_trade_closed(-50.0)
        self.rm.record_trade_closed(-50.0)

        self.assertEqual(self.rm.daily_state.consecutive_losses, 3)
        allowed, reason = self.rm.check_trade_allowed("BTCUSDT", current_equity=9850.0)
        self.assertFalse(allowed)
        self.assertEqual(reason, "REJECTED_CONSECUTIVE_LOSS_COOLDOWN")


if __name__ == "__main__":
    unittest.main()
