"""
Strategy package initialization.
"""
from .indicators import (
    calculate_ema, calculate_ema_series, calculate_atr_series,
    calculate_adx_series, calculate_average_body, is_displacement_candle
)
from .structure import SwingDetector, MarketStructureEngine, TrendDirection
from .impulse_pullback import ImpulseDetector, PullbackEngine, ImpulseMove, PullbackZone
from .confirmation import ConfirmationEngine, ConfirmationSignal
from .scorer import SetupScorer, SetupEvaluation
from .state_machine import StrategyStateMachine, State

__all__ = [
    "calculate_ema", "calculate_ema_series", "calculate_atr_series",
    "calculate_adx_series", "calculate_average_body", "is_displacement_candle",
    "SwingDetector", "MarketStructureEngine", "TrendDirection",
    "ImpulseDetector", "PullbackEngine", "ImpulseMove", "PullbackZone",
    "ConfirmationEngine", "ConfirmationSignal",
    "SetupScorer", "SetupEvaluation",
    "StrategyStateMachine", "State"
]
