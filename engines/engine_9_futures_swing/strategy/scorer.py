"""
Swing Setup Scoring Engine.
Calculates point breakdown according to Section 45 rules.
"""

from typing import Dict, Any, Tuple
from dataclasses import dataclass, field
import numpy as np

from config import Config


@dataclass
class SetupEvaluation:
    symbol: str
    direction: str              # "LONG" or "SHORT"
    total_score: int
    is_valid: bool
    rejection_reason: str
    score_breakdown: Dict[str, int] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)


class SetupScorer:
    def __init__(self, config: Config):
        self.config = config

    def score_setup(
        self,
        symbol: str,
        direction: str,
        daily_trend_aligned: bool,
        daily_structure_aligned: bool,
        four_h_trend_aligned: bool,
        strong_4h_impulse: bool,
        ema_fib_overlap: bool,
        valid_4h_pullback: bool,
        one_h_structure_confirm: bool,
        one_h_displacement: bool,
        adx_4h: float,
        volume_confirmed: bool,
        clear_structural_target: bool,
        rr_ratio: float,
        is_extreme_volatility: bool,
        is_extreme_funding: bool,
        details: Dict[str, Any]
    ) -> SetupEvaluation:
        """
        Section 45: Complete Point Breakdown Engine
        """
        breakdown: Dict[str, int] = {}
        total = 0

        # Trend and Structure
        if daily_trend_aligned:
            breakdown["daily_trend"] = 2
            total += 2
        else:
            breakdown["daily_trend"] = 0

        if daily_structure_aligned:
            breakdown["daily_structure"] = 2
            total += 2
        else:
            breakdown["daily_structure"] = 0

        if four_h_trend_aligned:
            breakdown["four_h_trend"] = 2
            total += 2
        else:
            breakdown["four_h_trend"] = 0

        # Impulse & Pullback
        if strong_4h_impulse:
            breakdown["strong_impulse"] = 2
            total += 2
        else:
            breakdown["strong_impulse"] = 0

        if ema_fib_overlap:
            breakdown["ema_fib_overlap"] = 2
            total += 2
        else:
            breakdown["ema_fib_overlap"] = 0

        if valid_4h_pullback:
            breakdown["valid_pullback"] = 2
            total += 2
        else:
            breakdown["valid_pullback"] = 0

        # 1H Confirmation & Displacement
        if one_h_structure_confirm:
            breakdown["one_h_structure"] = 2
            total += 2
        else:
            breakdown["one_h_structure"] = 0

        if one_h_displacement:
            breakdown["one_h_displacement"] = 2
            total += 2
        else:
            breakdown["one_h_displacement"] = 0

        # Trend Strength Bonus
        if adx_4h >= self.config.STRONG_ADX:
            breakdown["strong_adx"] = 1
            total += 1
        else:
            breakdown["strong_adx"] = 0

        # Volume Confirmation Bonus
        if volume_confirmed:
            breakdown["volume_confirmation"] = 1
            total += 1
        else:
            breakdown["volume_confirmation"] = 0

        # Structural Target Bonus
        if clear_structural_target:
            breakdown["clear_target"] = 1
            total += 1
        else:
            breakdown["clear_target"] = 0

        # RR Bonus
        if rr_ratio >= self.config.MIN_RR:
            breakdown["rr_valid"] = 2
            total += 2
        else:
            breakdown["rr_valid"] = 0

        # Penalties
        if is_extreme_volatility:
            breakdown["extreme_volatility_penalty"] = -2
            total -= 2

        if is_extreme_funding:
            breakdown["extreme_funding_penalty"] = -1
            total -= 1

        is_valid = (total >= self.config.MIN_SETUP_SCORE) and not is_extreme_volatility and (rr_ratio >= self.config.MIN_RR)
        rejection_reason = "" if is_valid else ("REJECTED_LOW_SCORE" if total < self.config.MIN_SETUP_SCORE else "REJECTED_HIGH_VOLATILITY")

        return SetupEvaluation(
            symbol=symbol,
            direction=direction,
            total_score=total,
            is_valid=is_valid,
            rejection_reason=rejection_reason,
            score_breakdown=breakdown,
            details=details
        )
