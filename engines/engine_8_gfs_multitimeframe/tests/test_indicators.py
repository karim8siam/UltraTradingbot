import unittest
from indicators import (
    Candle, calculate_ema, calculate_ema_slope,
    calculate_atr, calculate_atr_ratio, find_swings, check_displacement
)


class TestIndicators(unittest.TestCase):
    def test_ema_calculation(self):
        closes = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]
        ema = calculate_ema(closes, period=3)
        self.assertEqual(len(ema), len(closes))
        self.assertAlmostEqual(ema[2], 11.0) # initial SMA (10+11+12)/3
        self.assertTrue(ema[-1] > ema[-2])

    def test_ema_slope(self):
        ema_bullish = [10.0, 11.0, 12.5, 14.0]
        diff, direction = calculate_ema_slope(ema_bullish, index=-1)
        self.assertEqual(direction, "BULLISH")
        self.assertGreater(diff, 0)

        ema_bearish = [14.0, 13.0, 12.0, 10.5]
        diff, direction = calculate_ema_slope(ema_bearish, index=-1)
        self.assertEqual(direction, "BEARISH")
        self.assertLess(diff, 0)

    def test_swing_detection_length_2(self):
        # Create candles where index 2 is a swing high (higher than 0,1 and 3,4)
        candles = [
            Candle(100, 10, 12, 9, 11, 100, 1000),
            Candle(200, 11, 14, 10, 13, 100, 2000),
            Candle(300, 13, 20, 12, 19, 100, 3000), # Swing High
            Candle(400, 18, 15, 13, 14, 100, 4000),
            Candle(500, 14, 13, 11, 12, 100, 5000), # Confirmed here at idx 4
        ]
        swings = find_swings(candles, swing_length=2)
        high_swings = [s for s in swings if s.is_high]
        self.assertEqual(len(high_swings), 1)
        self.assertEqual(high_swings[0].index, 2)
        self.assertEqual(high_swings[0].price, 20.0)
        self.assertEqual(high_swings[0].confirmed_at_index, 4)

    def test_displacement_filter(self):
        # 10 small candles followed by 1 large momentum candle
        candles = []
        for i in range(10):
            candles.append(Candle(i*100, 100.0, 102.0, 99.0, 101.0, 50.0, (i+1)*100)) # body = 1.0, range = 3.0
        # Confirmation candle with big bullish displacement
        candles.append(Candle(1000, 101.0, 106.0, 100.5, 105.5, 500.0, 1100)) # body = 4.5, range = 5.5, body% = 4.5/5.5 = 81.8%

        ok, stats = check_displacement(candles, candle_idx=10, is_long=True, body_multiplier=1.25, min_body_pct=0.55)
        self.assertTrue(ok)
        self.assertGreaterEqual(stats["current_body"], stats["required_body"])
        self.assertGreaterEqual(stats["body_pct"], 0.55)


if __name__ == "__main__":
    unittest.main()
