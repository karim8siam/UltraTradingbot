"""
Deterministic Strategy State Machine.
Implements the 20 lifecycle states defined in Section 73.
"""

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import time


class State(str, Enum):
    WAITING = "WAITING"
    DAILY_TREND_CONFIRMED = "DAILY_TREND_CONFIRMED"
    FOUR_HOUR_TREND_CONFIRMED = "FOUR_HOUR_TREND_CONFIRMED"
    IMPULSE_DETECTED = "IMPULSE_DETECTED"
    WAITING_FOR_PULLBACK = "WAITING_FOR_PULLBACK"
    PULLBACK_ACTIVE = "PULLBACK_ACTIVE"
    PULLBACK_ZONE_REACHED = "PULLBACK_ZONE_REACHED"
    SON_CONFIRMATION_PENDING = "SON_CONFIRMATION_PENDING"
    STRUCTURE_CONFIRMED = "STRUCTURE_CONFIRMED"
    ENTRY_READY = "ENTRY_READY"
    ENTRY_SUBMITTED = "ENTRY_SUBMITTED"
    POSITION_OPEN = "POSITION_OPEN"
    TP1_REACHED = "TP1_REACHED"
    BREAKEVEN_ACTIVE = "BREAKEVEN_ACTIVE"
    TRAILING_ACTIVE = "TRAILING_ACTIVE"
    TRADE_COMPLETE = "TRADE_COMPLETE"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    COOLDOWN = "COOLDOWN"


@dataclass
class StateContext:
    symbol: str
    current_state: State = State.WAITING
    previous_state: Optional[State] = None
    state_entry_time: float = field(default_factory=time.time)
    direction: Optional[str] = None
    entry_order_id: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    original_sl: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    risk_amount: float = 0.0
    position_size: float = 0.0
    entry_bar_count: int = 0
    invalidation_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class StrategyStateMachine:
    def __init__(self, symbol: str):
        self.context = StateContext(symbol=symbol)

    @property
    def current_state(self) -> State:
        return self.context.current_state

    def transition_to(self, new_state: State, reason: Optional[str] = None) -> None:
        """Execute a state transition with audit tracking."""
        self.context.previous_state = self.context.current_state
        self.context.current_state = new_state
        self.context.state_entry_time = time.time()
        if reason:
            self.context.invalidation_reason = reason

    def reset_to_waiting(self) -> None:
        """Reset state machine for a new cycle."""
        symbol = self.context.symbol
        self.context = StateContext(symbol=symbol, current_state=State.WAITING)
