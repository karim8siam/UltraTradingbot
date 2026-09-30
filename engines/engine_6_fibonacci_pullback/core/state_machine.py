"""
Symbol-Specific Finite State Machine (FSM)
Sections 67, 68, 69, 70 Specification
"""

import logging
from typing import Dict, List, Optional, Tuple
from core.types import (
    Candle,
    FibLevels,
    ImpulseLeg,
    Position,
    PositionSide,
    SetupRejectReason,
    StrategyState,
    TradeSetup,
    TrendType,
)

logger = logging.getLogger("StateMachine")


class SymbolStateMachine:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.state = StrategyState.WAITING_FOR_TREND
        self.bias_4h = TrendType.NEUTRAL
        self.bias_1h = TrendType.NEUTRAL
        self.current_impulse: Optional[ImpulseLeg] = None
        self.fib_levels: Optional[FibLevels] = None
        self.current_setup: Optional[TradeSetup] = None
        self.active_position: Optional[Position] = None
        self.state_history: List[Tuple[StrategyState, str, int]] = []
        self.cooldown_until: int = 0
        self.setup_age_candles: int = 0

    def transition_to(self, new_state: StrategyState, reason: str = "", timestamp: int = 0):
        """Executes and logs state transition."""
        prev = self.state
        self.state = new_state
        self.state_history.append((new_state, reason, timestamp))
        logger.info(f"[{self.symbol}] State: {prev.value} -> {new_state.value} | {reason}")

    def reset_to_waiting_impulse(self, reason: str = "", timestamp: int = 0):
        """Resets pullback and setup tracking back to waiting for a new impulse."""
        self.current_impulse = None
        self.fib_levels = None
        self.current_setup = None
        self.setup_age_candles = 0
        self.transition_to(StrategyState.WAITING_FOR_IMPULSE, reason, timestamp)

    def reset_to_waiting_trend(self, reason: str = "", timestamp: int = 0):
        """Resets full strategy state back to waiting for trend."""
        self.current_impulse = None
        self.fib_levels = None
        self.current_setup = None
        self.active_position = None
        self.setup_age_candles = 0
        self.transition_to(StrategyState.WAITING_FOR_TREND, reason, timestamp)


class StateMachineManager:
    """Manages independent state machines for all active symbols."""
    def __init__(self, symbols: List[str]):
        self.machines: Dict[str, SymbolStateMachine] = {s: SymbolStateMachine(s) for s in symbols}

    def get(self, symbol: str) -> SymbolStateMachine:
        if symbol not in self.machines:
            self.machines[symbol] = SymbolStateMachine(symbol)
        return self.machines[symbol]

    def all(self) -> Dict[str, SymbolStateMachine]:
        return self.machines
