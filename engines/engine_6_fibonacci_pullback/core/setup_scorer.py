"""
Deterministic Setup Scoring Engine (Section 41)
Threshold: MIN_SETUP_SCORE = 11
"""

from core.types import (
    FibLevels,
    ImpulseLeg,
    PositionSide,
    SetupScoreBreakdown,
    TrendType,
)
from config.constants import MIN_SETUP_SCORE, IMPULSE_MIN_ATR, MIN_RR


class SetupScorer:
    def __init__(self, min_score: int = MIN_SETUP_SCORE):
        self.min_score = min_score

    def score_setup(
        self,
        side: PositionSide,
        bias_4h: TrendType,
        bias_1h: TrendType,
        impulse: ImpulseLeg,
        fib_levels: FibLevels,
        pullback_price: float,
        is_structure_shift: bool,
        is_displacement: bool,
        is_confirmed: bool,
        has_clear_tp: bool,
        rr: float,
        atr_ratio: float = 1.0,
        funding_rate: float = 0.0,
    ) -> SetupScoreBreakdown:
        """
        Calculates mathematical score for the setup based on Section 41 rules.
        """
        breakdown = SetupScoreBreakdown()

        # 1. 4H Trend (+2)
        if (side == PositionSide.LONG and bias_4h == TrendType.BULLISH) or (
            side == PositionSide.SHORT and bias_4h == TrendType.BEARISH
        ):
            breakdown.trend_4h_score = 2

        # 2. 1H Trend (+2)
        if (side == PositionSide.LONG and bias_1h == TrendType.BULLISH) or (
            side == PositionSide.SHORT and bias_1h == TrendType.BEARISH
        ):
            breakdown.trend_1h_score = 2

        # 3. Impulse >= 2 ATR (+1)
        if impulse.size >= (impulse.atr14 * IMPULSE_MIN_ATR):
            breakdown.impulse_size_score = 1

        # 4. Retracement reaches 50-61.8% preferred zone (+2)
        if side == PositionSide.LONG:
            if fib_levels.fib_618 <= pullback_price <= fib_levels.fib_500:
                breakdown.fib_zone_score = 2
            elif fib_levels.fib_500 < pullback_price <= fib_levels.fib_382:
                breakdown.fib_zone_score = 1  # reached 38.2%-50% primary
        else:
            if fib_levels.fib_500 <= pullback_price <= fib_levels.fib_618:
                breakdown.fib_zone_score = 2
            elif fib_levels.fib_382 <= pullback_price < fib_levels.fib_500:
                breakdown.fib_zone_score = 1

        # 5. Pullback structure shift (+2)
        if is_structure_shift:
            breakdown.structure_shift_score = 2

        # 6. Displacement (+2)
        if is_displacement:
            breakdown.displacement_score = 2

        # 7. Confirmation candle close (+1)
        if is_confirmed:
            breakdown.confirmation_score = 1

        # 8. Clear TP Target (+1)
        if has_clear_tp:
            breakdown.target_score = 1

        # 9. RR >= 2.0 (+2)
        if rr >= MIN_RR:
            breakdown.rr_score = 2

        # 10. Premium / Discount alignment (+1)
        # For Long: Discount side (pullback price <= 50% equilibrium)
        # For Short: Premium side (pullback price >= 50% equilibrium)
        if side == PositionSide.LONG and pullback_price <= fib_levels.fib_500:
            breakdown.equilibrium_score = 1
        elif side == PositionSide.SHORT and pullback_price >= fib_levels.fib_500:
            breakdown.equilibrium_score = 1

        # 11. Volatility penalty (-1 if elevated)
        if atr_ratio > 2.0:
            breakdown.volatility_penalty = -1

        # 12. Extreme funding penalty (-1 if unfavorable)
        # Unfavorable: Long paying high positive funding, or Short paying high negative funding
        if side == PositionSide.LONG and funding_rate > 0.0005:  # > 0.05%
            breakdown.funding_penalty = -1
        elif side == PositionSide.SHORT and funding_rate < -0.0005:  # < -0.05%
            breakdown.funding_penalty = -1

        return breakdown
