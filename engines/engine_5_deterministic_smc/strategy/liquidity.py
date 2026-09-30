from typing import List, Optional, Tuple
from datetime import datetime, timezone
from strategy.models import Candle, LiquidityLevel, LiquidityType, SwingType
from strategy.swing_detector import SwingDetector

class LiquidityDetector:
    def __init__(self, swing_length: int = 2, equal_level_tolerance: float = 0.001):
        self.swing_detector = SwingDetector(swing_length=swing_length)
        self.equal_level_tolerance = equal_level_tolerance

    def calculate_pdh_pdl(self, candles: List[Candle]) -> Tuple[Optional[LiquidityLevel], Optional[LiquidityLevel]]:
        """
        Calculate PDH and PDL using strict Binance UTC day boundaries (00:00:00 to 23:59:59 UTC).
        Only completed trading days are used.
        """
        if not candles:
            return None, None

        latest_time = datetime.fromtimestamp(candles[-1].timestamp / 1000.0, tz=timezone.utc)
        current_day = latest_time.date()

        # Group candles by UTC date
        daily_candles: dict = {}
        for c in candles:
            dt = datetime.fromtimestamp(c.timestamp / 1000.0, tz=timezone.utc)
            d = dt.date()
            if d not in daily_candles:
                daily_candles[d] = []
            daily_candles[d].append(c)

        completed_days = [d for d in daily_candles.keys() if d < current_day]
        if not completed_days:
            return None, None

        prev_day = max(completed_days)
        prev_candles = daily_candles[prev_day]

        pdh_val = max(c.high for c in prev_candles)
        pdl_val = min(c.low for c in prev_candles)
        last_prev_ts = prev_candles[-1].timestamp

        pdh = LiquidityLevel(
            price=pdh_val,
            level_type=LiquidityType.PDH,
            timestamp=last_prev_ts,
            details=f"PDH for UTC {prev_day.isoformat()}"
        )
        pdl = LiquidityLevel(
            price=pdl_val,
            level_type=LiquidityType.PDL,
            timestamp=last_prev_ts,
            details=f"PDL for UTC {prev_day.isoformat()}"
        )
        return pdh, pdl

    def find_equal_highs_lows(self, candles: List[Candle]) -> Tuple[List[LiquidityLevel], List[LiquidityLevel]]:
        """
        Find Equal Highs and Equal Lows among confirmed swings within equal_level_tolerance (0.1%).
        """
        swings = self.swing_detector.find_swings(candles)
        swing_highs = [s for s in swings if s.swing_type == SwingType.HIGH]
        swing_lows = [s for s in swings if s.swing_type == SwingType.LOW]

        equal_highs: List[LiquidityLevel] = []
        equal_lows: List[LiquidityLevel] = []

        # Equal Highs
        for i in range(len(swing_highs)):
            for j in range(i + 1, len(swing_highs)):
                h1, h2 = swing_highs[i], swing_highs[j]
                diff = abs(h1.price - h2.price) / ((h1.price + h2.price) / 2.0)
                if diff <= self.equal_level_tolerance:
                    avg_p = (h1.price + h2.price) / 2.0
                    equal_highs.append(LiquidityLevel(
                        price=avg_p,
                        level_type=LiquidityType.EQUAL_HIGHS,
                        timestamp=h2.timestamp,
                        details=f"Equal Highs at {avg_p:.4f} (diff {diff*100:.3f}%)"
                    ))

        # Equal Lows
        for i in range(len(swing_lows)):
            for j in range(i + 1, len(swing_lows)):
                l1, l2 = swing_lows[i], swing_lows[j]
                diff = abs(l1.price - l2.price) / ((l1.price + l2.price) / 2.0)
                if diff <= self.equal_level_tolerance:
                    avg_p = (l1.price + l2.price) / 2.0
                    equal_lows.append(LiquidityLevel(
                        price=avg_p,
                        level_type=LiquidityType.EQUAL_LOWS,
                        timestamp=l2.timestamp,
                        details=f"Equal Lows at {avg_p:.4f} (diff {diff*100:.3f}%)"
                    ))

        return equal_highs, equal_lows

    def get_all_liquidity_levels(self, candles_15m: List[Candle], daily_or_1h_candles: List[Candle]) -> Tuple[List[LiquidityLevel], List[LiquidityLevel]]:
        """
        Returns (buy_side_liquidity_levels, sell_side_liquidity_levels)
        """
        buy_side: List[LiquidityLevel] = []
        sell_side: List[LiquidityLevel] = []

        # 1. Confirmed Swings on 15M
        swings = self.swing_detector.find_swings(candles_15m)
        for s in swings:
            if s.swing_type == SwingType.HIGH:
                buy_side.append(LiquidityLevel(
                    price=s.price,
                    level_type=LiquidityType.SWING_HIGH,
                    timestamp=s.timestamp,
                    details=f"15M Swing High at {s.price:.4f}"
                ))
            else:
                sell_side.append(LiquidityLevel(
                    price=s.price,
                    level_type=LiquidityType.SWING_LOW,
                    timestamp=s.timestamp,
                    details=f"15M Swing Low at {s.price:.4f}"
                ))

        # 2. Equal Highs / Lows on 15M
        eq_highs, eq_lows = self.find_equal_highs_lows(candles_15m)
        buy_side.extend(eq_highs)
        sell_side.extend(eq_lows)

        # 3. PDH / PDL
        pdh, pdl = self.calculate_pdh_pdl(daily_or_1h_candles)
        if pdh:
            buy_side.append(pdh)
        if pdl:
            sell_side.append(pdl)

        return buy_side, sell_side
