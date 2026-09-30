"""
Dynamic -3% Drawdown Counter-Recovery Engine
State machine that switches between Normal Reverse Mode and Aggressive Original-Direction Counter-Recovery.

Rules:
1. Normal State (STATE_NORMAL_REVERSE):
   - Trades OPPOSITE of bot predictions with 1:1 TP/SL.
   - Uncapped capacity (No maximum, no minimum).
2. Counter-Recovery State (STATE_COUNTER_RECOVERY):
   - Triggered when total portfolio unrealized PnL <= -3.0%.
   - Immediately trades in the ORIGINAL BOT PREDICTION DIRECTION (No reverse, no strict score filter).
   - Deploys across available pairs (3-4+ pairs) to aggressively ride strong market momentum.
3. 0.0% Break-Even Flush:
   - When total aggregate net PnL recovers to >= 0.0% (Break-Even or Profit):
     - Executes MARKET CLOSE ALL across all open positions.
     - Secures cash to wallet.
     - Resets state back to STATE_NORMAL_REVERSE.
"""

import time
from typing import Dict, Any, Tuple, Optional
from config import (
    DRAWDOWN_RECOVERY_TRIGGER_PCT,
    BREAKEVEN_FLUSH_TARGET_PCT
)

STATE_NORMAL_REVERSE = "NORMAL_REVERSE"
STATE_COUNTER_RECOVERY = "COUNTER_RECOVERY"


class RecoveryStateEngine:
    def __init__(self):
        self.state: str = STATE_NORMAL_REVERSE
        self.trigger_drawdown_pct: float = DRAWDOWN_RECOVERY_TRIGGER_PCT  # -3.0%
        self.flush_target_pct: float = BREAKEVEN_FLUSH_TARGET_PCT         # 0.0%
        self.recovery_activated_time: Optional[float] = None
        self.last_pnl_usd: float = 0.0
        self.last_pnl_pct: float = 0.0

    def get_state(self) -> str:
        return self.state

    def is_counter_recovery_active(self) -> bool:
        return self.state == STATE_COUNTER_RECOVERY

    def should_invert_signals(self) -> bool:
        """
        Reverse Mode permanently removed. Pure forward execution only.
        Predict LONG -> Take LONG. Predict SHORT -> Take SHORT.
        """
        return False

    def evaluate_pnl_and_update_state(
        self,
        account_balance: float,
        total_unrealized_pnl_usd: float
    ) -> Tuple[str, float, float]:
        """
        Evaluates live aggregate portfolio PnL and manages state transitions.
        Returns (action, pnl_usd, pnl_pct) where action is:
        - 'TRIGGER_COUNTER_RECOVERY' : PnL dropped <= -3.0%, activated original direction recovery
        - 'TRIGGER_BREAKEVEN_FLUSH'  : PnL recovered >= 0.0%, execute market close all and reset
        - 'NONE'                     : No state transition
        """
        if account_balance <= 0:
            return "NONE", 0.0, 0.0

        self.last_pnl_usd = total_unrealized_pnl_usd
        pnl_pct = (total_unrealized_pnl_usd / account_balance) * 100.0
        self.last_pnl_pct = pnl_pct

        # 1. Check if Normal Mode hits -3.0% Drawdown Trigger
        if self.state == STATE_NORMAL_REVERSE:
            if pnl_pct <= self.trigger_drawdown_pct:
                self.state = STATE_COUNTER_RECOVERY
                self.recovery_activated_time = time.time()
                print("=" * 80)
                print(f"🚨 [COUNTER-RECOVERY TRIGGERED] Portfolio Drawdown reached {pnl_pct:.2f}% (<= {self.trigger_drawdown_pct}%)!")
                print(f"   • Total Unrealized PnL: ${total_unrealized_pnl_usd:+.4f} USD on ${account_balance:,.2f} balance.")
                print(f"   • Action: Flipping engine to ORIGINAL BOT DIRECTION to ride prevailing trend!")
                print("=" * 80)
                return "TRIGGER_COUNTER_RECOVERY", total_unrealized_pnl_usd, pnl_pct

        # 2. Check if Counter-Recovery Mode hits 0.0% Break-Even Flush Target
        elif self.state == STATE_COUNTER_RECOVERY:
            if pnl_pct >= self.flush_target_pct:
                self.state = STATE_NORMAL_REVERSE
                self.recovery_activated_time = None
                print("=" * 80)
                print(f"🎉 [0.0% BREAK-EVEN FLUSH TRIGGERED] Portfolio PnL recovered to {pnl_pct:.2f}% (>= {self.flush_target_pct}%)!")
                print(f"   • Total Unrealized PnL: ${total_unrealized_pnl_usd:+.4f} USD.")
                print(f"   • Action: Executing MARKET CLOSE ALL across all positions and resetting to Normal Reverse Mode!")
                print("=" * 80)
                return "TRIGGER_BREAKEVEN_FLUSH", total_unrealized_pnl_usd, pnl_pct

        return "NONE", total_unrealized_pnl_usd, pnl_pct

    def reset_to_normal(self):
        """Forces reset back to Normal Reverse state."""
        self.state = STATE_NORMAL_REVERSE
        self.recovery_activated_time = None


# Singleton instance
recovery_engine = RecoveryStateEngine()
