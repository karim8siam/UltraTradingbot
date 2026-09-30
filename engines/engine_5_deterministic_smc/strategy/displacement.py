from typing import List, Optional
from strategy.models import Candle, DisplacementEvent

class DisplacementDetector:
    def __init__(self, avg_body_period: int = 10, multiplier: float = 1.5, min_body_pct: float = 0.60):
        self.avg_body_period = avg_body_period
        self.multiplier = multiplier
        self.min_body_pct = min_body_pct

    def check_displacement(self, candles: List[Candle], index: Optional[int] = None) -> Optional[DisplacementEvent]:
        """
        Evaluates candle at given index (default: latest closed candle) for displacement.
        Requires at least avg_body_period preceding candles.
        """
        if index is None:
            index = len(candles) - 1

        if index < self.avg_body_period or index >= len(candles):
            return None

        c = candles[index]
        prev_candles = candles[index - self.avg_body_period:index]
        avg_body = sum(pc.body_size for pc in prev_candles) / self.avg_body_period

        if avg_body <= 0:
            avg_body = 1e-6

        current_body = c.body_size
        body_pct = c.body_percentage

        is_displaced = (current_body >= (self.multiplier * avg_body)) and (body_pct >= self.min_body_pct)
        if not is_displaced:
            return None

        if c.is_bullish:
            return DisplacementEvent(
                timestamp=c.timestamp,
                is_bullish=True,
                body_size=current_body,
                avg_body=avg_body,
                body_percentage=body_pct
            )
        elif c.is_bearish:
            return DisplacementEvent(
                timestamp=c.timestamp,
                is_bullish=False,
                body_size=current_body,
                avg_body=avg_body,
                body_percentage=body_pct
            )

        return None
