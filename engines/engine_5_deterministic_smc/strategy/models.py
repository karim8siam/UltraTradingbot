from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

class BiasType(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

class SwingType(Enum):
    HIGH = "HIGH"
    LOW = "LOW"

class LiquidityType(Enum):
    SWING_HIGH = "SWING_HIGH"
    SWING_LOW = "SWING_LOW"
    EQUAL_HIGHS = "EQUAL_HIGHS"
    EQUAL_LOWS = "EQUAL_LOWS"
    PDH = "PDH"
    PDL = "PDL"

class TradeSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class SymbolState(Enum):
    WAITING = "WAITING"
    BIAS_CONFIRMED = "BIAS_CONFIRMED"
    LIQUIDITY_IDENTIFIED = "LIQUIDITY_IDENTIFIED"
    LIQUIDITY_SWEPT = "LIQUIDITY_SWEPT"
    DISPLACEMENT_CONFIRMED = "DISPLACEMENT_CONFIRMED"
    MSS_CONFIRMED = "MSS_CONFIRMED"
    FVG_IDENTIFIED = "FVG_IDENTIFIED"
    WAITING_FOR_RETRACE = "WAITING_FOR_RETRACE"
    ENTRY_READY = "ENTRY_READY"
    ENTRY_SUBMITTED = "ENTRY_SUBMITTED"
    POSITION_OPEN = "POSITION_OPEN"
    POSITION_MANAGEMENT = "POSITION_MANAGEMENT"
    TRADE_COMPLETE = "TRADE_COMPLETE"
    COOLDOWN = "COOLDOWN"
    INVALIDATED = "INVALIDATED"

@dataclass
class Candle:
    timestamp: int       # Milliseconds UTC
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = True

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def candle_range(self) -> float:
        return self.high - self.low

    @property
    def body_percentage(self) -> float:
        r = self.candle_range
        return (self.body_size / r) if r > 0 else 0.0

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
    swing_type: SwingType
    confirmed: bool = True

@dataclass
class LiquidityLevel:
    price: float
    level_type: LiquidityType
    timestamp: int
    is_swept: bool = False
    details: str = ""

@dataclass
class SweepEvent:
    timestamp: int
    side: TradeSide  # LONG if sell-side swept; SHORT if buy-side swept
    liquidity_level: LiquidityLevel
    sweep_high: float
    sweep_low: float
    sweep_candle_close: float
    atr_14: float

@dataclass
class DisplacementEvent:
    timestamp: int
    is_bullish: bool
    body_size: float
    avg_body: float
    body_percentage: float

@dataclass
class MSSEvent:
    timestamp: int
    is_bullish: bool
    broken_swing_level: float
    break_candle_close: float

@dataclass
class FVGEvent:
    timestamp: int
    is_bullish: bool
    fvg_low: float
    fvg_high: float
    midpoint: float
    candle1_time: int
    candle3_time: int

@dataclass
class SMCSetup:
    symbol: str
    side: TradeSide
    timestamp: int
    bias_4h: BiasType
    bias_1h: BiasType
    bias_15m: BiasType
    sweep_event: SweepEvent
    mss_event: MSSEvent
    fvg_event: FVGEvent
    entry_price: float
    stop_loss: float
    take_profit: float
    target_liquidity: LiquidityLevel
    risk_amount: float
    position_size: float
    leverage: int
    rr: float
    setup_score: int
    atr: float
    funding_rate: float
    in_discount: bool
    in_premium: bool
    created_at_iso: str
