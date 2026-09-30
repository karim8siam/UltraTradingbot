"""
GFS Finite State Machine for Symbol Lifecycle Management
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import time


class BotState(Enum):
    WAITING = 'WAITING'
    DAILY_TREND_CONFIRMED = 'DAILY_TREND_CONFIRMED'
    FOUR_HOUR_TREND_CONFIRMED = 'FOUR_HOUR_TREND_CONFIRMED'
    WAITING_FOR_PULLBACK = 'WAITING_FOR_PULLBACK'
    PULLBACK_ACTIVE = 'PULLBACK_ACTIVE'
    SON_TIMEFRAME_MONITORING = 'SON_TIMEFRAME_MONITORING'
    STRUCTURE_SHIFT_CONFIRMED = 'STRUCTURE_SHIFT_CONFIRMED'
    ENTRY_READY = 'ENTRY_READY'
    ENTRY_SUBMITTED = 'ENTRY_SUBMITTED'
    POSITION_OPEN = 'POSITION_OPEN'
    POSITION_MANAGEMENT = 'POSITION_MANAGEMENT'
    TRADE_COMPLETE = 'TRADE_COMPLETE'
    INVALIDATED = 'INVALIDATED'
    EXPIRED = 'EXPIRED'
    COOLDOWN = 'COOLDOWN'


@dataclass
class StateTransition:
    from_state: BotState
    to_state: BotState
    timestamp_ms: int
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class SymbolStateMachine:
    """
    Tracks and executes state transitions for a single trading symbol.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.current_state: BotState = BotState.WAITING
        self.history: List[StateTransition] = []
        self.state_entered_time_ms: int = int(time.time() * 1000)
        self.active_setup: Optional[Any] = None
        self.active_order_id: Optional[str] = None
        self.setup_age_candles: int = 0

    def transition_to(
        self,
        new_state: BotState,
        reason: str,
        timestamp_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        ts = timestamp_ms if timestamp_ms else int(time.time() * 1000)
        transition = StateTransition(
            from_state=self.current_state,
            to_state=new_state,
            timestamp_ms=ts,
            reason=reason,
            metadata=metadata or {}
        )
        self.history.append(transition)
        self.current_state = new_state
        self.state_entered_time_ms = ts

    def reset_to_waiting(self, reason: str, timestamp_ms: Optional[int] = None):
        self.active_setup = None
        self.active_order_id = None
        self.setup_age_candles = 0
        self.transition_to(BotState.WAITING, reason=reason, timestamp_ms=timestamp_ms)

    def increment_setup_age(self, max_age: int = 20) -> bool:
        """
        Increments setup age when monitoring 15M candles.
        Returns True if expired.
        """
        if self.current_state in (
            BotState.SON_TIMEFRAME_MONITORING,
            BotState.STRUCTURE_SHIFT_CONFIRMED,
            BotState.ENTRY_READY
        ):
            self.setup_age_candles += 1
            if self.setup_age_candles >= max_age:
                self.transition_to(BotState.EXPIRED, reason=f'Setup exceeded max age of {max_age} candles')
                return True
        return False
