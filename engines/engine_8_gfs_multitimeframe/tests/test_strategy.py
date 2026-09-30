import unittest
from indicators import Candle
from gfs_strategy import GFSStrategyEngine, TrendDirection, GFSSetup


class TestStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = GFSStrategyEngine()

    def test_1d_trend_bullish(self):
        # 220 ascending daily candles
        candles = []
        for i in range(220):
            p = 100.0 + (i * 2.0)
            candles.append(Candle(i * 86400000, p, p + 1.0, p - 1.0, p + 0.5, 1000, (i+1)*86400000))

        trend, ema50, ema200, reason = self.strategy.evaluate_1d_trend(candles)
        self.assertEqual(trend, TrendDirection.BULLISH)
        self.assertGreater(ema50, ema200)

    def test_4h_pullback_and_invalidation(self):
        # 60 candles with EMA20 > EMA50
        candles = []
        for i in range(50):
            p = 200.0 + (i * 1.5)
            candles.append(Candle(i * 14400000, p, p + 1.0, p - 1.0, p + 0.5, 1000, (i+1)*14400000))

        # Candle that closes below EMA50 should invalidate
        invalid_candle = Candle(50 * 14400000, 200.0, 201.0, 150.0, 160.0, 1000, 51 * 14400000)
        candles.append(invalid_candle)

        in_zone, is_invalid, ema20, ema50 = self.strategy.check_4h_pullback_zone(candles, TrendDirection.BULLISH)
        self.assertTrue(is_invalid)


if __name__ == "__main__":
    unittest.main()
