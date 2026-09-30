import unittest
from strategy import Momentum3CandleStrategy
from risk_manager import RiskManager

class MockClient:
    def get_symbol_rules(self, symbol: str):
        return {
            "step_size": 0.001,
            "min_qty": 0.001,
            "min_notional": 5.0,
            "quantity_precision": 3,
        }

class TestStrategyLogic(unittest.TestCase):

    def test_3_healthy_green_candles_returns_buy(self):
        """Preceded by red, followed by 3 healthy green candles -> BUY"""
        klines = [
            {"open": 100, "close": 98, "high": 101, "low": 97, "open_time": 1},   # c_prev: Red
            {"open": 98, "close": 102, "high": 102.5, "low": 97.8, "open_time": 2}, # c1: Green (healthy)
            {"open": 102, "close": 106, "high": 106.8, "low": 101.5, "open_time": 3},# c2: Green (healthy)
            {"open": 106, "close": 110, "high": 110.8, "low": 105.5, "open_time": 4},# c3: Green (healthy)
            {"open": 110, "close": 111, "high": 112, "low": 109, "open_time": 5},   # Live unclosed
        ]
        signal = Momentum3CandleStrategy.evaluate_klines(klines)
        self.assertEqual(signal, "BUY")

    def test_3_healthy_red_candles_returns_sell(self):
        """Preceded by green, followed by 3 healthy red candles -> SELL"""
        klines = [
            {"open": 98, "close": 100, "high": 101, "low": 97, "open_time": 1},   # c_prev: Green
            {"open": 100, "close": 96, "high": 100.5, "low": 95.8, "open_time": 2}, # c1: Red (healthy)
            {"open": 96, "close": 92, "high": 96.5, "low": 91.5, "open_time": 3},  # c2: Red (healthy)
            {"open": 92, "close": 88, "high": 92.5, "low": 87.5, "open_time": 4},  # c3: Red (healthy)
            {"open": 88, "close": 87, "high": 89, "low": 86, "open_time": 5},     # Live unclosed
        ]
        signal = Momentum3CandleStrategy.evaluate_klines(klines)
        self.assertEqual(signal, "SELL")

    def test_4th_green_candle_rejected(self):
        """If 4th consecutive green candle, must NOT trigger trade"""
        klines = [
            {"open": 90, "close": 95, "high": 95.5, "low": 89.5, "open_time": 1},  # c_prev: Also GREEN!
            {"open": 95, "close": 100, "high": 100.5, "low": 94.5, "open_time": 2}, # c1: Green
            {"open": 100, "close": 105, "high": 105.5, "low": 99.5, "open_time": 3},# c2: Green
            {"open": 105, "close": 110, "high": 110.5, "low": 104.5, "open_time": 4},# c3: Green
            {"open": 110, "close": 112, "high": 113, "low": 109, "open_time": 5},   # Live unclosed
        ]
        signal = Momentum3CandleStrategy.evaluate_klines(klines)
        self.assertIsNone(signal)

    def test_doji_candle_rejected(self):
        """If any of the 3 candles is a doji / weak body, must NOT trigger"""
        klines = [
            {"open": 100, "close": 98, "high": 101, "low": 97, "open_time": 1},
            {"open": 98, "close": 102, "high": 102.5, "low": 97.8, "open_time": 2},
            # Doji: Open 102, Close 102.1, High 106, Low 99 (tiny body, large range)
            {"open": 102, "close": 102.1, "high": 106, "low": 99, "open_time": 3},
            {"open": 102.1, "close": 106, "high": 106.5, "low": 101.5, "open_time": 4},
            {"open": 106, "close": 107, "high": 108, "low": 105, "open_time": 5},
        ]
        signal = Momentum3CandleStrategy.evaluate_klines(klines)
        self.assertIsNone(signal)

    def test_candle_with_wick_accepted_if_not_doji(self):
        """Candles with moderate wicks are accepted as long as they are not flat Dojis"""
        klines = [
            {"open": 100, "close": 98, "high": 101, "low": 97, "open_time": 1},   # c_prev: Red
            {"open": 98, "close": 102, "high": 105, "low": 97, "open_time": 2},   # c1: Green with wick (Body: 4/8 = 50%)
            {"open": 102, "close": 104, "high": 108, "low": 101, "open_time": 3},  # c2: Green with wick (Body: 2/7 = 28%, not doji)
            {"open": 104, "close": 107, "high": 109, "low": 103, "open_time": 4},  # c3: Green with wick
            {"open": 107, "close": 108, "high": 109, "low": 106, "open_time": 5},
        ]
        signal = Momentum3CandleStrategy.evaluate_klines(klines)
        self.assertEqual(signal, "BUY")

    def test_risk_manager_sizing(self):
        client = MockClient()
        rm = RiskManager(client)
        # Sizing with $10,000 balance at $100 price: 0.1% margin = $10.00 * 5x = $50.00 notional -> 50.00 / 100 = 0.5
        qty = rm.calculate_order_quantity("ETHUSDT", 100.0, 10000.0)
        self.assertEqual(qty, 0.5)

if __name__ == "__main__":
    unittest.main()
