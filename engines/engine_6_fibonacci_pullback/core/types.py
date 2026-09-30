"""
Core Domain Models, Enums, and Data Classes
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class TrendType(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class OrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class StrategyState(str, Enum):
    WAITING_FOR_TREND = "WAITING_FOR_TREND"
    TREND_CONFIRMED = "TREND_CONFIRMED"
    WAITING_FOR_IMPULSE = "WAITING_FOR_IMPULSE"
    IMPULSE_CONFIRMED = "IMPULSE_CONFIRMED"
    FIB_LEVELS_CALCULATED = "FIB_LEVELS_CALCULATED"
    WAITING_FOR_PULLBACK = "WAITING_FOR_PULLBACK"
    FIB_ZONE_REACHED = "FIB_ZONE_REACHED"
    PULLBACK_CONFIRMATION = "PULLBACK_CONFIRMATION"
    STRUCTURE_SHIFT_CONFIRMED = "STRUCTURE_SHIFT_CONFIRMED"
    DISPLACEMENT_CONFIRMED = "DISPLACEMENT_CONFIRMED"
    ENTRY_READY = "ENTRY_READY"
    ENTRY_SUBMITTED = "ENTRY_SUBMITTED"
    POSITION_OPEN = "POSITION_OPEN"
    POSITION_MANAGEMENT = "POSITION_MANAGEMENT"
    TRADE_COMPLETE = "TRADE_COMPLETE"
    INVALIDATED = "INVALIDATED"
    COOLDOWN = "COOLDOWN"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"


class SetupRejectReason(str, Enum):
    REJECTED_NO_4H_TREND = "REJECTED_NO_4H_TREND"
    REJECTED_NO_1H_TREND = "REJECTED_NO_1H_TREND"
    REJECTED_HTF_MISMATCH = "REJECTED_HTF_MISMATCH"
    REJECTED_NO_IMPULSE = "REJECTED_NO_IMPULSE"
    REJECTED_IMPULSE_TOO_SMALL = "REJECTED_IMPULSE_TOO_SMALL"
    REJECTED_NO_FIB_ZONE = "REJECTED_NO_FIB_ZONE"
    REJECTED_FIB_INVALIDATED = "REJECTED_FIB_INVALIDATED"
    REJECTED_NO_PULLBACK_CONFIRMATION = "REJECTED_NO_PULLBACK_CONFIRMATION"
    REJECTED_NO_DISPLACEMENT = "REJECTED_NO_DISPLACEMENT"
    REJECTED_LOW_RR = "REJECTED_LOW_RR"
    REJECTED_LOW_SCORE = "REJECTED_LOW_SCORE"
    REJECTED_HIGH_VOLATILITY = "REJECTED_HIGH_VOLATILITY"
    REJECTED_DAILY_LIMIT = "REJECTED_DAILY_LIMIT"
    REJECTED_CONSECUTIVE_LOSS_COOLDOWN = "REJECTED_CONSECUTIVE_LOSS_COOLDOWN"
    REJECTED_MAX_POSITIONS = "REJECTED_MAX_POSITIONS"
    REJECTED_EXISTING_POSITION = "REJECTED_EXISTING_POSITION"
    REJECTED_SESSION = "REJECTED_SESSION"
    REJECTED_STALE_SETUP = "REJECTED_STALE_SETUP"
    REJECTED_CHASE_DEVIATION = "REJECTED_CHASE_DEVIATION"
    REJECTED_INVALID_SL_TP = "REJECTED_INVALID_SL_TP"
    REJECTED_EMERGENCY_STOP = "REJECTED_EMERGENCY_STOP"


class FibZoneCategory(str, Enum):
    ZONE_382_500 = "38.2-50.0%"
    ZONE_500_618 = "50.0-61.8%"
    ZONE_618_786 = "61.8-78.6%"
    OUT_OF_ZONE = "OUT_OF_ZONE"


@dataclass
class Candle:
    timestamp: int  # Open time in ms
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int = 0
    is_closed: bool = True

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def total_range(self) -> float:
        return max(self.high - self.low, 1e-9)

    @property
    def body_percentage(self) -> float:
        return self.body_size / self.total_range

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


@dataclass
class SwingPoint:
    index: int
    timestamp: int
    price: float
    is_high: bool
    is_low: bool
    timeframe: str


@dataclass
class FibLevels:
    fib_0: float
    fib_236: float
    fib_382: float
    fib_500: float
    fib_618: float
    fib_786: float
    fib_1000: float
    impulse_high: float
    impulse_low: float
    range_val: float
    is_bullish: bool

    def get_zone_category(self, price: float) -> FibZoneCategory:
        """Classifies pullback price into Fib retracement zones."""
        if self.is_bullish:
            # Bullish: price pulls down from High
            if self.fib_500 < price <= self.fib_382:
                return FibZoneCategory.ZONE_382_500
            elif self.fib_618 <= price <= self.fib_500:
                return FibZoneCategory.ZONE_500_618
            elif self.fib_786 <= price < self.fib_618:
                return FibZoneCategory.ZONE_618_786
        else:
            # Bearish: price pulls up from Low
            if self.fib_382 <= price < self.fib_500:
                return FibZoneCategory.ZONE_382_500
            elif self.fib_500 <= price <= self.fib_618:
                return FibZoneCategory.ZONE_500_618
            elif self.fib_618 < price <= self.fib_786:
                return FibZoneCategory.ZONE_618_786
        return FibZoneCategory.OUT_OF_ZONE


@dataclass
class ImpulseLeg:
    symbol: str
    side: PositionSide  # LONG or SHORT
    start_swing: SwingPoint
    end_swing: SwingPoint
    high: float
    low: float
    size: float
    atr14: float
    timestamp: int


@dataclass
class SetupScoreBreakdown:
    trend_4h_score: int = 0
    trend_1h_score: int = 0
    impulse_size_score: int = 0
    fib_zone_score: int = 0
    structure_shift_score: int = 0
    displacement_score: int = 0
    confirmation_score: int = 0
    target_score: int = 0
    rr_score: int = 0
    equilibrium_score: int = 0
    volatility_penalty: int = 0
    funding_penalty: int = 0

    @property
    def total_score(self) -> int:
        return (
            self.trend_4h_score
            + self.trend_1h_score
            + self.impulse_size_score
            + self.fib_zone_score
            + self.structure_shift_score
            + self.displacement_score
            + self.confirmation_score
            + self.target_score
            + self.rr_score
            + self.equilibrium_score
            + self.volatility_penalty
            + self.funding_penalty
        )


@dataclass
class TradeSetup:
    symbol: str
    side: PositionSide  # LONG or SHORT
    bias_4h: TrendType
    bias_1h: TrendType
    impulse: ImpulseLeg
    fib_levels: FibLevels
    pullback_low: float
    pullback_high: float
    confirmation_level: float
    entry_price: float
    sl_price: float
    tp_price: float
    rr: float
    score: int
    score_breakdown: SetupScoreBreakdown
    atr14: float
    timestamp: int
    setup_candle_index: int
    fib_zone_category: FibZoneCategory


@dataclass
class Position:
    trade_id: str
    symbol: str
    side: PositionSide
    entry_price: float
    quantity: float
    sl_price: float
    tp_price: float
    leverage: int
    risk_amount: float
    entry_time: int
    client_order_id: str
    status: OrderStatus = OrderStatus.FILLED
    exit_time: Optional[int] = None
    exit_price: Optional[float] = None
    gross_pnl: float = 0.0
    fees: float = 0.0
    funding_cost: float = 0.0
    net_pnl: float = 0.0
    exit_reason: str = ""


@dataclass
class TradeRecord:
    trade_id: str
    timestamp: int
    symbol: str
    side: str
    bias_4h: str
    bias_1h: str
    impulse_low: float
    impulse_high: float
    impulse_size: float
    atr: float
    fib_236: float
    fib_382: float
    fib_500: float
    fib_618: float
    fib_786: float
    pullback_low: float
    pullback_high: float
    confirmation_level: float
    entry: float
    sl: float
    tp: float
    risk_amount: float
    position_size: float
    leverage: int
    rr: float
    setup_score: int
    funding_rate: float
    entry_time: int
    exit_time: int
    exit_price: float
    gross_pnl: float
    fees: float
    funding_cost: float
    net_pnl: float
    result: str  # WIN, LOSS, BREAKEVEN
    exit_reason: str
    fib_zone: str
