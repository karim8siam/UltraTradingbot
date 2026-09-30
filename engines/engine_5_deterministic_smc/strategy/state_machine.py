import logging
from typing import Optional, Dict, Any, List, Tuple
from strategy.models import (
    SymbolState, BiasType, TradeSide, Candle, LiquidityLevel,
    SweepEvent, DisplacementEvent, MSSEvent, FVGEvent, SMCSetup
)
from strategy.market_structure import MarketStructure
from strategy.liquidity import LiquidityDetector
from strategy.sweep_detector import SweepDetector
from strategy.displacement import DisplacementDetector
from strategy.mss_detector import MSSDetector
from strategy.fvg_detector import FVGDetector
from strategy.setup_evaluator import SetupEvaluator

logger = logging.getLogger("SMC_StateMachine")

class SymbolStateMachine:
    def __init__(self, symbol: str, setup_evaluator: SetupEvaluator, swing_length: int = 2):
        self.symbol = symbol
        self.state = SymbolState.WAITING
        self.setup_evaluator = setup_evaluator

        # SMC Analysis Components
        self.structure_analyzer = MarketStructure(swing_length=swing_length)
        self.liquidity_detector = LiquidityDetector(swing_length=swing_length)
        self.sweep_detector = SweepDetector()
        self.displacement_detector = DisplacementDetector()
        self.mss_detector = MSSDetector(swing_length=swing_length)
        self.fvg_detector = FVGDetector()

        # State Context Variables
        self.bias_4h: BiasType = BiasType.NEUTRAL
        self.bias_1h: BiasType = BiasType.NEUTRAL
        self.bias_15m: BiasType = BiasType.NEUTRAL
        self.range_1h_midpoint: Optional[float] = None
        
        self.buy_side_liq: List[LiquidityLevel] = []
        self.sell_side_liq: List[LiquidityLevel] = []
        
        self.active_sweep: Optional[SweepEvent] = None
        self.active_displacement: Optional[DisplacementEvent] = None
        self.active_mss: Optional[MSSEvent] = None
        self.active_fvg: Optional[FVGEvent] = None
        self.current_setup: Optional[SMCSetup] = None
        
        self.last_transition_reason: str = "INITIALIZED"

    def transition_to(self, new_state: SymbolState, reason: str):
        if self.state != new_state:
            logger.info(f"[{self.symbol}] {self.state.value} -> {new_state.value} ({reason})")
            self.state = new_state
            self.last_transition_reason = reason

    def reset_setup_flow(self, reason: str = "RESET"):
        self.active_sweep = None
        self.active_displacement = None
        self.active_mss = None
        self.active_fvg = None
        self.current_setup = None
        self.transition_to(SymbolState.WAITING, reason)

    def process_candles(self, candles_4h: List[Candle], candles_1h: List[Candle],
                        candles_15m: List[Candle], candles_5m: List[Candle],
                        funding_rate: float = 0.0) -> Tuple[Optional[SMCSetup], str]:
        """
        Processes updated multi-timeframe candles and steps the state machine through deterministic SMC logic.
        Returns (setup, status_message)
        """
        if not candles_4h or not candles_1h or not candles_15m or not candles_5m:
            return None, "INSUFFICIENT_CANDLE_DATA"

        # 1. Update Market Biases
        self.bias_4h, _, _ = self.structure_analyzer.determine_bias(candles_4h)
        self.bias_1h, _, _ = self.structure_analyzer.determine_bias(candles_1h)
        self.bias_15m, _, _ = self.structure_analyzer.determine_bias(candles_15m)

        # Update 1H Premium / Discount Range Midpoint
        p_d_range = self.structure_analyzer.get_premium_discount_range(candles_1h)
        if p_d_range:
            _, _, self.range_1h_midpoint = p_d_range

        # Check Higher Timeframe Bias Alignment
        htf_aligned = (
            (self.bias_4h == BiasType.BULLISH and self.bias_1h == BiasType.BULLISH) or
            (self.bias_4h == BiasType.BEARISH and self.bias_1h == BiasType.BEARISH)
        )

        if not htf_aligned:
            if self.state not in (SymbolState.POSITION_OPEN, SymbolState.POSITION_MANAGEMENT, SymbolState.ENTRY_SUBMITTED):
                self.reset_setup_flow("HTF_BIAS_NOT_ALIGNED")
            return None, "HTF_BIAS_NOT_ALIGNED"

        if self.state == SymbolState.WAITING:
            self.transition_to(SymbolState.BIAS_CONFIRMED, f"4H={self.bias_4h.value}, 1H={self.bias_1h.value}")

        # 2. Update Structural Liquidity Levels
        self.buy_side_liq, self.sell_side_liq = self.liquidity_detector.get_all_liquidity_levels(
            candles_15m, candles_1h
        )

        if self.state == SymbolState.BIAS_CONFIRMED:
            if self.buy_side_liq or self.sell_side_liq:
                self.transition_to(SymbolState.LIQUIDITY_IDENTIFIED, f"Found {len(self.buy_side_liq)} BSL / {len(self.sell_side_liq)} SSL")

        # 3. Detect 15M Liquidity Sweep
        sweep = self.sweep_detector.detect_sweep(
            candles_15m, self.sell_side_liq, self.buy_side_liq, self.bias_4h, self.bias_1h
        )
        if sweep:
            self.active_sweep = sweep
            self.transition_to(SymbolState.LIQUIDITY_SWEPT, f"{sweep.side.value} sweep on {sweep.liquidity_level.details}")

        if not self.active_sweep:
            return None, "WAITING_FOR_SWEEP"

        # 4. Detect 5M Displacement
        if not self.active_displacement:
            # Check recent 5M candles after the sweep
            min_idx = max(0, len(candles_5m) - 10)
            for idx in range(len(candles_5m) - 1, min_idx - 1, -1):
                c = candles_5m[idx]
                if c.timestamp < self.active_sweep.timestamp:
                    continue
                disp = self.displacement_detector.check_displacement(candles_5m, index=idx)
                if disp:
                    is_valid_disp = (self.active_sweep.side == TradeSide.LONG and disp.is_bullish) or \
                                    (self.active_sweep.side == TradeSide.SHORT and not disp.is_bullish)
                    if is_valid_disp:
                        self.active_displacement = disp
                        self.transition_to(SymbolState.DISPLACEMENT_CONFIRMED, f"Displacement body={disp.body_size:.2f} ({disp.body_percentage*100:.1f}%)")
                        break

        if not self.active_displacement:
            return None, "WAITING_FOR_DISPLACEMENT"

        # 5. Detect 5M MSS (Market Structure Shift)
        is_bullish = (self.active_sweep.side == TradeSide.LONG)
        mss = self.mss_detector.detect_mss(candles_5m, is_bullish, self.active_displacement.timestamp)
        if mss:
            self.active_mss = mss
            self.transition_to(SymbolState.MSS_CONFIRMED, f"MSS broke {mss.broken_swing_level:.4f}")

        if not self.active_mss:
            return None, "WAITING_FOR_MSS"

        # 6. Detect 5M FVG (Fair Value Gap)
        fvg = self.fvg_detector.detect_fvg(candles_5m, is_bullish, self.active_displacement.timestamp)
        if fvg:
            self.active_fvg = fvg
            self.transition_to(SymbolState.FVG_IDENTIFIED, f"FVG range [{fvg.fvg_low:.4f} - {fvg.fvg_high:.4f}], Midpoint={fvg.midpoint:.4f}")

        if not self.active_fvg:
            return None, "WAITING_FOR_FVG"

        # Check FVG Invalidation (Price blow through)
        latest_c = candles_5m[-1]
        if self.fvg_detector.is_fvg_completely_invalidated(self.active_fvg, latest_c.close):
            self.reset_setup_flow("FVG_BLOWN_THROUGH")
            return None, "FVG_INVALIDATED"

        # 7. Setup Evaluation & Scoring
        setup, reason = self.setup_evaluator.evaluate_setup(
            symbol=self.symbol,
            bias_4h=self.bias_4h,
            bias_1h=self.bias_1h,
            bias_15m=self.bias_15m,
            sweep=self.active_sweep,
            mss=self.active_mss,
            fvg=self.active_fvg,
            candles_15m=candles_15m,
            buy_side=self.buy_side_liq,
            sell_side=self.sell_side_liq,
            range_1h_midpoint=self.range_1h_midpoint,
            funding_rate=funding_rate
        )

        if not setup:
            return None, reason

        self.current_setup = setup
        self.transition_to(SymbolState.ENTRY_READY, f"Setup Valid! Score={setup.setup_score}, RR={setup.rr:.2f}")
        return setup, "SETUP_READY"
