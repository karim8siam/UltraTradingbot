"""
4H Impulse Detection, Fibonacci Retracement, and Pullback Zone Confluence Engine.
"""

from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np

from .indicators import calculate_average_body, calculate_atr_series, calculate_ema_series
from .structure import SwingDetector, SwingPoint


@dataclass
class ImpulseMove:
    start_index: int
    end_index: int
    start_price: float   # Impulse low for bullish, impulse high for bearish
    end_price: float     # Impulse high for bullish, impulse low for bearish
    is_bullish: bool
    atr14: float
    avg_body: float
    volume: float
    avg_volume: float
    volume_ratio: float


@dataclass
class PullbackZone:
    impulse: ImpulseMove
    fib_382: float
    fib_500: float
    fib_618: float
    fib_705: float
    ema20: float
    ema50: float
    ema_zone_low: float
    ema_zone_high: float
    has_confluence_overlap: bool
    current_pullback_low: float
    current_pullback_high: float
    pullback_depth: float  # Percentage retraced (0.0 to 1.0)
    is_valid: bool
    rejection_reason: Optional[str] = None


class ImpulseDetector:
    def __init__(self, avg_body_period: int = 10, atr_period: int = 14,
                 body_mult: float = 1.25, atr_mult: float = 1.0):
        self.avg_body_period = avg_body_period
        self.atr_period = atr_period
        self.body_mult = body_mult
        self.atr_mult = atr_mult

    def detect_latest_impulse(self, opens: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                              closes: np.ndarray, volumes: np.ndarray,
                              is_bullish: bool, lookback: int = 30) -> Optional[ImpulseMove]:
        """
        Section 14: Identify a strong directional 4H move.
        Bullish: Close > Open, Body >= AvgBody10 * 1.25, Move >= ATR14 * 1.0
        Bearish: Close < Open, Body >= AvgBody10 * 1.25, Move >= ATR14 * 1.0
        """
        n = len(closes)
        if n < max(self.avg_body_period, self.atr_period) + 5:
            return None

        atr_series = calculate_atr_series(highs, lows, closes, period=self.atr_period)
        search_start = max(0, n - lookback)

        for i in range(n - 1, search_start, -1):
            if np.isnan(atr_series[i]):
                continue

            open_p = opens[i]
            high_p = highs[i]
            low_p = lows[i]
            close_p = closes[i]
            current_body = abs(close_p - open_p)
            current_move = high_p - low_p
            current_atr = atr_series[i]

            prev_opens = opens[:i]
            prev_closes = closes[:i]
            if len(prev_opens) < self.avg_body_period:
                continue

            avg_body = calculate_average_body(prev_opens, prev_closes, period=self.avg_body_period)
            is_large_body = current_body >= (avg_body * self.body_mult)
            is_large_move = current_move >= (current_atr * self.atr_mult)

            # Volume ratio check
            prev_vols = volumes[:i]
            avg_vol = float(np.mean(prev_vols[-20:])) if len(prev_vols) >= 20 else float(np.mean(prev_vols))
            vol_ratio = (volumes[i] / avg_vol) if avg_vol > 0 else 1.0

            if is_bullish:
                if (close_p > open_p) and is_large_body and is_large_move:
                    return ImpulseMove(
                        start_index=i,
                        end_index=i,
                        start_price=low_p,
                        end_price=high_p,
                        is_bullish=True,
                        atr14=float(current_atr),
                        avg_body=float(avg_body),
                        volume=float(volumes[i]),
                        avg_volume=float(avg_vol),
                        volume_ratio=float(vol_ratio)
                    )
            else:
                if (close_p < open_p) and is_large_body and is_large_move:
                    return ImpulseMove(
                        start_index=i,
                        end_index=i,
                        start_price=high_p,
                        end_price=low_p,
                        is_bullish=False,
                        atr14=float(current_atr),
                        avg_body=float(avg_body),
                        volume=float(volumes[i]),
                        avg_volume=float(avg_vol),
                        volume_ratio=float(vol_ratio)
                    )
        return None


class PullbackEngine:
    def __init__(self, max_retracement: float = 0.705, swing_length: int = 2):
        self.max_retracement = max_retracement
        self.swing_detector = SwingDetector(swing_length=swing_length)

    def evaluate_pullback(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                          impulse: ImpulseMove, four_h_ema20: float, four_h_ema50: float) -> PullbackZone:
        """
        Sections 15-19: Pullback Zone, Fibonacci Retracement, Quality, and Depth check.
        """
        n = len(closes)
        post_impulse_highs = highs[impulse.start_index:]
        post_impulse_lows = lows[impulse.start_index:]
        post_impulse_closes = closes[impulse.start_index:]

        current_close = float(closes[-1])
        ema_low = min(four_h_ema20, four_h_ema50)
        ema_high = max(four_h_ema20, four_h_ema50)

        if impulse.is_bullish:
            # Bullish impulse: Start=Low, End=High
            # Check highest high reached since impulse start
            impulse_low = impulse.start_price
            impulse_high = float(np.max(post_impulse_highs))
            impulse_range = impulse_high - impulse_low

            if impulse_range <= 0:
                return PullbackZone(
                    impulse=impulse, fib_382=0, fib_500=0, fib_618=0, fib_705=0,
                    ema20=four_h_ema20, ema50=four_h_ema50, ema_zone_low=ema_low, ema_zone_high=ema_high,
                    has_confluence_overlap=False, current_pullback_low=0, current_pullback_high=0,
                    pullback_depth=0.0, is_valid=False, rejection_reason="REJECTED_NO_IMPULSE"
                )

            # Fibonacci levels from High down toward Low
            fib_382 = impulse_high - (impulse_range * 0.382)
            fib_500 = impulse_high - (impulse_range * 0.500)
            fib_618 = impulse_high - (impulse_range * 0.618)
            fib_705 = impulse_high - (impulse_range * self.max_retracement)

            # Find pullback lowest point since highest high
            highest_high_idx = int(np.argmax(post_impulse_highs))
            pullback_lows = post_impulse_lows[highest_high_idx:]
            current_pullback_low = float(np.min(pullback_lows)) if len(pullback_lows) > 0 else float(lows[-1])
            current_pullback_high = impulse_high

            retraced_dist = impulse_high - current_pullback_low
            pullback_depth = retraced_dist / impulse_range

            # Confluence check: overlap between [fib_618, fib_382] and [ema_low, ema_high]
            fib_zone_low = fib_618
            fib_zone_high = fib_382
            has_overlap = not (ema_high < fib_zone_low or ema_low > fib_zone_high)

            # Invalidation rules
            is_valid = True
            rejection_reason = None

            if pullback_depth < 0.20:
                is_valid = False
                rejection_reason = "REJECTED_NO_PULLBACK"
            elif pullback_depth > self.max_retracement:
                is_valid = False
                rejection_reason = "REJECTED_PULLBACK_TOO_DEEP"
            elif current_pullback_low <= impulse_low:
                is_valid = False
                rejection_reason = "REJECTED_STRUCTURE_INVALIDATED"

            return PullbackZone(
                impulse=impulse,
                fib_382=fib_382,
                fib_500=fib_500,
                fib_618=fib_618,
                fib_705=fib_705,
                ema20=four_h_ema20,
                ema50=four_h_ema50,
                ema_zone_low=ema_low,
                ema_zone_high=ema_high,
                has_confluence_overlap=has_overlap,
                current_pullback_low=current_pullback_low,
                current_pullback_high=current_pullback_high,
                pullback_depth=pullback_depth,
                is_valid=is_valid,
                rejection_reason=rejection_reason
            )

        else:
            # Bearish impulse: Start=High, End=Low
            impulse_high = impulse.start_price
            impulse_low = float(np.min(post_impulse_lows))
            impulse_range = impulse_high - impulse_low

            if impulse_range <= 0:
                return PullbackZone(
                    impulse=impulse, fib_382=0, fib_500=0, fib_618=0, fib_705=0,
                    ema20=four_h_ema20, ema50=four_h_ema50, ema_zone_low=ema_low, ema_zone_high=ema_high,
                    has_confluence_overlap=False, current_pullback_low=0, current_pullback_high=0,
                    pullback_depth=0.0, is_valid=False, rejection_reason="REJECTED_NO_IMPULSE"
                )

            # Fibonacci levels from Low up toward High
            fib_382 = impulse_low + (impulse_range * 0.382)
            fib_500 = impulse_low + (impulse_range * 0.500)
            fib_618 = impulse_low + (impulse_range * 0.618)
            fib_705 = impulse_low + (impulse_range * self.max_retracement)

            lowest_low_idx = int(np.argmin(post_impulse_lows))
            pullback_highs = post_impulse_highs[lowest_low_idx:]
            current_pullback_high = float(np.max(pullback_highs)) if len(pullback_highs) > 0 else float(highs[-1])
            current_pullback_low = impulse_low

            retraced_dist = current_pullback_high - impulse_low
            pullback_depth = retraced_dist / impulse_range

            fib_zone_low = fib_382
            fib_zone_high = fib_618
            has_overlap = not (ema_high < fib_zone_low or ema_low > fib_zone_high)

            is_valid = True
            rejection_reason = None

            if pullback_depth < 0.20:
                is_valid = False
                rejection_reason = "REJECTED_NO_PULLBACK"
            elif pullback_depth > self.max_retracement:
                is_valid = False
                rejection_reason = "REJECTED_PULLBACK_TOO_DEEP"
            elif current_pullback_high >= impulse_high:
                is_valid = False
                rejection_reason = "REJECTED_STRUCTURE_INVALIDATED"

            return PullbackZone(
                impulse=impulse,
                fib_382=fib_382,
                fib_500=fib_500,
                fib_618=fib_618,
                fib_705=fib_705,
                ema20=four_h_ema20,
                ema50=four_h_ema50,
                ema_zone_low=ema_low,
                ema_zone_high=ema_high,
                has_confluence_overlap=has_overlap,
                current_pullback_low=current_pullback_low,
                current_pullback_high=current_pullback_high,
                pullback_depth=pullback_depth,
                is_valid=is_valid,
                rejection_reason=rejection_reason
            )
