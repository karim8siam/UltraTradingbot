from typing import List, Optional
from strategy.models import Candle, MSSEvent, SwingType, DisplacementEvent
from strategy.swing_detector import SwingDetector

class MSSDetector:
    def __init__(self, swing_length: int = 2):
        self.swing_detector = SwingDetector(swing_length=swing_length)

    def detect_mss(self, candles_5m: List[Candle], is_bullish: bool, 
                   displacement_ts: int) -> Optional[MSSEvent]:
        """
        Detects 5M Market Structure Shift (MSS) based on closing candle price past pre-displacement swing level.
        """
        # Find 5M swings that were confirmed before displacement
        swings = self.swing_detector.find_swings(candles_5m)
        pre_displacement_swings = [s for s in swings if s.timestamp < displacement_ts]

        if not pre_displacement_swings:
            return None

        # Find displacement candle and subsequent candles
        target_candles = [c for c in candles_5m if c.timestamp >= displacement_ts]
        if not target_candles:
            return None

        if is_bullish:
            # Bullish MSS: Break the most recent confirmed 5M swing high before displacement
            swing_highs = [s for s in pre_displacement_swings if s.swing_type == SwingType.HIGH]
            if not swing_highs:
                return None
            target_high_level = swing_highs[-1].price

            for c in target_candles:
                # Candle must CLOSE above the swing high
                if c.close > target_high_level:
                    return MSSEvent(
                        timestamp=c.timestamp,
                        is_bullish=True,
                        broken_swing_level=target_high_level,
                        break_candle_close=c.close
                    )
        else:
            # Bearish MSS: Break the most recent confirmed 5M swing low before displacement
            swing_lows = [s for s in pre_displacement_swings if s.swing_type == SwingType.LOW]
            if not swing_lows:
                return None
            target_low_level = swing_lows[-1].price

            for c in target_candles:
                # Candle must CLOSE below the swing low
                if c.close < target_low_level:
                    return MSSEvent(
                        timestamp=c.timestamp,
                        is_bullish=False,
                        broken_swing_level=target_low_level,
                        break_candle_close=c.close
                    )

        return None
