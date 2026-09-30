from typing import List, Optional
from strategy.models import Candle, FVGEvent

class FVGDetector:
    def __init__(self, min_fvg_size_pct: float = 0.0002):
        self.min_fvg_size_pct = min_fvg_size_pct

    def detect_fvg(self, candles_5m: List[Candle], is_bullish: bool, 
                   displacement_ts: int) -> Optional[FVGEvent]:
        """
        Detects 3-candle Fair Value Gap associated with the displacement move.
        Candle 1, Candle 2 (Displacement candle), Candle 3.
        """
        if len(candles_5m) < 3:
            return None

        # Find displacement index
        disp_idx = None
        for i, c in enumerate(candles_5m):
            if c.timestamp == displacement_ts:
                disp_idx = i
                break

        if disp_idx is None or disp_idx < 1 or disp_idx >= len(candles_5m) - 1:
            return None

        c1 = candles_5m[disp_idx - 1]
        c2 = candles_5m[disp_idx]
        c3 = candles_5m[disp_idx + 1]

        if is_bullish:
            # Bullish FVG: Candle 1 High < Candle 3 Low
            if c1.high < c3.low:
                gap_size = c3.low - c1.high
                if gap_size / c2.close >= self.min_fvg_size_pct:
                    fvg_low = c1.high
                    fvg_high = c3.low
                    midpoint = (fvg_high + fvg_low) / 2.0
                    return FVGEvent(
                        timestamp=c3.timestamp,
                        is_bullish=True,
                        fvg_low=fvg_low,
                        fvg_high=fvg_high,
                        midpoint=midpoint,
                        candle1_time=c1.timestamp,
                        candle3_time=c3.timestamp
                    )
        else:
            # Bearish FVG: Candle 1 Low > Candle 3 High
            if c1.low > c3.high:
                gap_size = c1.low - c3.high
                if gap_size / c2.close >= self.min_fvg_size_pct:
                    fvg_low = c3.high
                    fvg_high = c1.low
                    midpoint = (fvg_high + fvg_low) / 2.0
                    return FVGEvent(
                        timestamp=c3.timestamp,
                        is_bullish=False,
                        fvg_low=fvg_low,
                        fvg_high=fvg_high,
                        midpoint=midpoint,
                        candle1_time=c1.timestamp,
                        candle3_time=c3.timestamp
                    )

        return None

    def is_fvg_completely_invalidated(self, fvg: FVGEvent, current_price: float) -> bool:
        """
        If price blows through the entire FVG (below fvg_low for Long, above fvg_high for Short),
        the FVG is invalidated.
        """
        if fvg.is_bullish and current_price < fvg.fvg_low:
            return True
        elif (not fvg.is_bullish) and current_price > fvg.fvg_high:
            return True
        return False
