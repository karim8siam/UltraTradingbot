"""
Exact Mathematical Fibonacci Retracement Engine
Sections 11, 12, 13 Specification
"""

from core.types import FibLevels, PositionSide, ImpulseLeg
from config.constants import (
    FIB_0,
    FIB_236,
    FIB_382,
    FIB_500,
    FIB_618,
    FIB_786,
    FIB_1000,
)


class FibonacciCalculator:
    @staticmethod
    def calculate(impulse: ImpulseLeg) -> FibLevels:
        """
        Calculates deterministic Fibonacci retracement levels for an impulse leg.
        """
        h = impulse.high
        l = impulse.low
        r = h - l
        is_bullish = impulse.side == PositionSide.LONG

        if is_bullish:
            # Bullish retracement measures pullback downwards from High (0.0) towards Low (1.0)
            return FibLevels(
                fib_0=h - (r * FIB_0),
                fib_236=h - (r * FIB_236),
                fib_382=h - (r * FIB_382),
                fib_500=h - (r * FIB_500),
                fib_618=h - (r * FIB_618),
                fib_786=h - (r * FIB_786),
                fib_1000=h - (r * FIB_1000),
                impulse_high=h,
                impulse_low=l,
                range_val=r,
                is_bullish=True,
            )
        else:
            # Bearish retracement measures pullback upwards from Low (0.0) towards High (1.0)
            return FibLevels(
                fib_0=l + (r * FIB_0),
                fib_236=l + (r * FIB_236),
                fib_382=l + (r * FIB_382),
                fib_500=l + (r * FIB_500),
                fib_618=l + (r * FIB_618),
                fib_786=l + (r * FIB_786),
                fib_1000=l + (r * FIB_1000),
                impulse_high=h,
                impulse_low=l,
                range_val=r,
                is_bullish=False,
            )
