import unittest
from run_backtest import generate_synthetic_data
from backtester import GFSBacktestEngine


class TestBacktestEngine(unittest.TestCase):
    def test_backtest_execution(self):
        symbol_data = {"BTCUSDT": generate_synthetic_data("BTCUSDT", limit_15m=3000)}
        engine = GFSBacktestEngine(initial_equity=10000.0)
        summary, trades, rejections = engine.run_backtest(symbol_data, start_ratio=0.0, end_ratio=1.0)
        self.assertIsNotNone(summary)
        self.assertIsInstance(rejections, dict)
        self.assertGreater(len(rejections), 0)


if __name__ == "__main__":
    unittest.main()
