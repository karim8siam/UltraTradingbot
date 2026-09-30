"""
FVG State Machine per Symbol
Implements Section 74 (17 States) and Sections 75/76 State Flows.
"""

from enum import Enum
from typing import Dict, List, Optional
from indicators import Candle
from trend_detector import TrendBias, evaluate_htf_alignment
from fvg_engine import FVG, FVGStatus, detect_fvgs_on_15m
from confirmation_engine import ConfirmationSignal, check_5m_confirmation
from setup_evaluator import TradeSetup, evaluate_setup


class BotSymbolState(str, Enum):
    WAITING = "WAITING"
    TREND_CONFIRMED = "TREND_CONFIRMED"
    DISPLACEMENT_DETECTED = "DISPLACEMENT_DETECTED"
    FVG_DETECTED = "FVG_DETECTED"
    FVG_VALIDATED = "FVG_VALIDATED"
    WAITING_FOR_RETRACE = "WAITING_FOR_RETRACE"
    FVG_ZONE_REACHED = "FVG_ZONE_REACHED"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    STRUCTURE_SHIFT_CONFIRMED = "STRUCTURE_SHIFT_CONFIRMED"
    ENTRY_READY = "ENTRY_READY"
    ENTRY_SUBMITTED = "ENTRY_SUBMITTED"
    POSITION_OPEN = "POSITION_OPEN"
    POSITION_MANAGEMENT = "POSITION_MANAGEMENT"
    TRADE_COMPLETE = "TRADE_COMPLETE"
    FVG_INVALIDATED = "FVG_INVALIDATED"
    FVG_EXPIRED = "FVG_EXPIRED"
    COOLDOWN = "COOLDOWN"


class SymbolStateMachine:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.state: BotSymbolState = BotSymbolState.WAITING
        self.bias_4h: TrendBias = TrendBias.NEUTRAL
        self.bias_1h: TrendBias = TrendBias.NEUTRAL
        self.htf_direction: Optional[str] = None  # "LONG", "SHORT", or None
        self.active_fvg: Optional[FVG] = None
        self.active_setup: Optional[TradeSetup] = None
        self.confirmation_signal: Optional[ConfirmationSignal] = None
        self.last_rejection_reason: Optional[str] = None
        self.status_message: str = "Initialized"

        # Cache timestamp keys
        self._last_4h_ts: int = 0
        self._last_1h_ts: int = 0
        self._last_15m_ts: int = 0
        self._cached_fvgs: List[FVG] = []
        self.processed_fvg_ids: set = set()

    def reset_fvg_state(self, new_state: BotSymbolState = BotSymbolState.WAITING, reason: Optional[str] = None) -> None:
        if self.active_fvg:
            self.processed_fvg_ids.add(self.active_fvg.fvg_id)
        self.state = new_state
        self.active_fvg = None
        self.active_setup = None
        self.confirmation_signal = None
        if reason:
            self.last_rejection_reason = reason

    def update(
        self,
        candles_4h: List[Candle],
        candles_1h: List[Candle],
        candles_15m: List[Candle],
        candles_5m: List[Candle],
        current_price: float,
        funding_rate: float = 0.0001,
        min_fvg_atr: float = 0.05,
        impulse_min_atr: float = 1.5,
        min_rr: float = 2.0,
        min_score: int = 11,
        max_entry_dev_atr: float = 0.25,
        sl_atr_buffer: float = 0.10,
        swing_length: int = 2
    ) -> Optional[TradeSetup]:
        """
        Step through deterministic state transitions based on closed candles.
        Returns a TradeSetup if ENTRY_READY is reached, otherwise None.
        """
        if self.state in (BotSymbolState.POSITION_OPEN, BotSymbolState.POSITION_MANAGEMENT, BotSymbolState.ENTRY_SUBMITTED):
            return None

        # 1. Evaluate HTF Bias (4H & 1H) with caching
        c4_ts = candles_4h[-1].timestamp if candles_4h else 0
        c1_ts = candles_1h[-1].timestamp if candles_1h else 0

        if c4_ts != self._last_4h_ts or c1_ts != self._last_1h_ts:
            htf_dir, b_4h, b_1h = evaluate_htf_alignment(candles_4h, candles_1h, swing_length=swing_length)
            self.bias_4h = b_4h
            self.bias_1h = b_1h
            self.htf_direction = htf_dir
            self._last_4h_ts = c4_ts
            self._last_1h_ts = c1_ts
        else:
            htf_dir = self.htf_direction

        if not htf_dir:
            self.reset_fvg_state(BotSymbolState.WAITING, "REJECTED_HTF_ALIGNMENT_NEUTRAL")
            self.status_message = f"HTF Disagree or Neutral: 4H={self.bias_4h.value}, 1H={self.bias_1h.value}"
            return None

        self.state = BotSymbolState.TREND_CONFIRMED

        # 2. Check or Discover Active 15M FVG
        c15_ts = candles_15m[-1].timestamp if candles_15m else 0
        if self.active_fvg is None or self.active_fvg.status != FVGStatus.ACTIVE:
            if c15_ts != self._last_15m_ts:
                self._cached_fvgs = detect_fvgs_on_15m(
                    candles_15m,
                    symbol=self.symbol,
                    min_fvg_atr=min_fvg_atr,
                    impulse_min_atr=impulse_min_atr
                )
                self._last_15m_ts = c15_ts

            curr_15m_idx = len(candles_15m) - 1
            # Filter fresh FVGs strictly aligned with HTF direction and not previously processed
            valid_fvgs = [
                f for f in self._cached_fvgs
                if f.fvg_id not in self.processed_fvg_ids
                and (curr_15m_idx - f.created_index_15m) <= 10
                and ((htf_dir == "LONG" and f.is_bullish) or (htf_dir == "SHORT" and f.is_bearish))
            ]

            if not valid_fvgs:
                self.state = BotSymbolState.WAITING
                self.last_rejection_reason = "REJECTED_NO_VALID_FVG"
                self.status_message = f"Trend {htf_dir} confirmed. Searching for 15M FVG..."
                return None

            self.active_fvg = valid_fvgs[-1]
            self.state = BotSymbolState.FVG_VALIDATED
            self.status_message = f"Discovered {self.active_fvg.fvg_type.value} FVG [{self.active_fvg.fvg_low:.4f} - {self.active_fvg.fvg_high:.4f}]"

        fvg = self.active_fvg

        # Check FVG age on 5M (Section 44)
        candles_since = [c for c in candles_5m if c.timestamp >= fvg.created_timestamp]
        fvg.age_5m = len(candles_since)
        if fvg.age_5m > 50:
            fvg.status = FVGStatus.EXPIRED
            self.reset_fvg_state(BotSymbolState.FVG_EXPIRED, "REJECTED_FVG_EXPIRED")
            self.status_message = f"FVG expired (age: {fvg.age_5m} candles > 50)"
            return None

        # 3. Check Retracement & Lower Timeframe 5M Confirmation
        self.state = BotSymbolState.WAITING_FOR_RETRACE
        signal = check_5m_confirmation(
            fvg=fvg,
            candles_5m=candles_5m,
            swing_length=swing_length
        )

        if signal is None:
            # Check if FVG was invalidated by price closing through boundaries
            if candles_15m:
                latest_15m = candles_15m[-1]
                if fvg.is_bullish and latest_15m.close < fvg.fvg_low:
                    fvg.status = FVGStatus.INVALIDATED
                    self.reset_fvg_state(BotSymbolState.FVG_INVALIDATED, "REJECTED_FVG_INVALIDATED")
                    self.status_message = "Bullish FVG invalidated by 15M close below low."
                    return None
                elif fvg.is_bearish and latest_15m.close > fvg.fvg_high:
                    fvg.status = FVGStatus.INVALIDATED
                    self.reset_fvg_state(BotSymbolState.FVG_INVALIDATED, "REJECTED_FVG_INVALIDATED")
                    self.status_message = "Bearish FVG invalidated by 15M close above high."
                    return None

            self.status_message = f"Waiting for 5M pullback into FVG [{fvg.fvg_low:.4f} - {fvg.fvg_high:.4f}] (Age: {fvg.age_5m})"
            return None

        # 4. Confirmation Achieved -> Structure Shift & Displacement Confirmed
        self.confirmation_signal = signal
        self.state = BotSymbolState.STRUCTURE_SHIFT_CONFIRMED

        # 5. Evaluate Setup (Entry, SL, TP, RR, Quality Score)
        setup = evaluate_setup(
            fvg=fvg,
            signal=signal,
            candles_15m=candles_15m,
            candles_1h=candles_1h,
            candles_4h=candles_4h,
            bias_4h=self.bias_4h,
            bias_1h=self.bias_1h,
            current_price=current_price,
            funding_rate=funding_rate,
            min_rr=min_rr,
            min_score=min_score,
            max_entry_dev_atr=max_entry_dev_atr,
            sl_atr_buffer=sl_atr_buffer,
            swing_length=swing_length
        )

        self.active_setup = setup
        if not setup.is_valid:
            self.last_rejection_reason = setup.rejection_reason
            self.status_message = f"Setup rejected: {setup.rejection_reason} (Score: {setup.setup_score})"
            return None

        self.state = BotSymbolState.ENTRY_READY
        self.status_message = f"ENTRY READY: {setup.side} @ {setup.entry_price:.4f}, SL={setup.sl_price:.4f}, TP={setup.tp_price:.4f}, RR={setup.rr:.2f}, Score={setup.setup_score}"
        return setup
