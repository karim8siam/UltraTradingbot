"""
Real-Time Terminal Dashboard & Monitoring UI
Implements Section 73 Dashboard Requirements in formatted ANSI text.
Zero external dependencies.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from config import BotConfig
from fvg_state_machine import SymbolStateMachine
from order_executor import ActivePosition
from risk_manager import RiskManager


class TerminalDashboard:
    def __init__(self, config: BotConfig):
        self.config = config

    def render(
        self,
        risk_mgr: RiskManager,
        state_machines: Dict[str, SymbolStateMachine],
        active_positions: Dict[str, ActivePosition],
        account_equity: float,
        api_status: str = "CONNECTED",
        ws_status: str = "ACTIVE"
    ) -> str:
        """Constructs an ANSI-formatted status overview dashboard."""
        mode_str = self.config.get_mode_name()
        state = risk_mgr.state

        daily_loss_pct = 0.0
        if state.daily_starting_equity > 0:
            daily_loss_pct = ((state.daily_starting_equity - account_equity) / state.daily_starting_equity) * 100.0

        lines = []
        lines.append("=" * 95)
        lines.append(f"  BINANCE USDT-M FUTURES — AUTOMATED FVG BOT (v1.0)  |  MODE: {mode_str}")
        lines.append("=" * 95)

        # Account & Risk Summary
        lines.append(
            f" Equity: ${account_equity:,.2f}  |  Today's PnL: ${state.daily_realized_pnl:+,.2f} ({daily_loss_pct:.2f}%) "
            f" |  Trades: {state.daily_trades_count}/{risk_mgr.max_daily_trades}  |  Consecutive Losses: {state.consecutive_losses}/{risk_mgr.max_consecutive_losses}"
        )
        lines.append(
            f" Open Positions: {len(active_positions)}/{risk_mgr.max_open_positions}  |  API: {api_status}  |  WebSocket: {ws_status}  |  Emergency Stop: {self.config.EMERGENCY_STOP}"
        )
        lines.append("-" * 95)

        # Active Positions Table
        lines.append(" ACTIVE OPEN POSITIONS:")
        if not active_positions:
            lines.append("   (No active positions)")
        else:
            lines.append(f"   {'Symbol':<10} {'Side':<6} {'Size':<10} {'Entry':<12} {'SL':<12} {'TP':<12} {'RR':<6} {'Trade ID'}")
            for sym, pos in active_positions.items():
                rr_val = pos.setup.rr if pos.setup else 0.0
                lines.append(f"   {sym:<10} {pos.side:<6} {pos.quantity:<10.3f} ${pos.entry_price:<11.4f} ${pos.sl_price:<11.4f} ${pos.tp_price:<11.4f} {rr_val:<6.2f} {pos.trade_id}")

        lines.append("-" * 95)

        # 10 Symbol Scanner & FVG Pipeline Table
        lines.append(" SYMBOL SCANNER & FVG PIPELINE:")
        lines.append(f"   {'Symbol':<10} {'4H':<8} {'1H':<8} {'State':<24} {'FVG Zone / Mid':<22} {'Score':<6} {'Latest Message'}")
        for sym in self.config.SYMBOLS:
            sm = state_machines.get(sym)
            if not sm:
                lines.append(f"   {sym:<10} {'-':<8} {'-':<8} {'OFFLINE':<24} {'-':<22} {'-':<6} Waiting...")
                continue

            b4 = sm.bias_4h.value[:4] if sm.bias_4h else "NEUT"
            b1 = sm.bias_1h.value[:4] if sm.bias_1h else "NEUT"
            st_name = sm.state.value[:24]

            fvg_str = "-"
            if sm.active_fvg:
                f = sm.active_fvg
                fvg_str = f"[{f.fvg_low:.2f}-{f.fvg_high:.2f}]"

            score_str = str(sm.active_setup.setup_score) if sm.active_setup else "-"
            msg = sm.status_message[:35]

            lines.append(f"   {sym:<10} {b4:<8} {b1:<8} {st_name:<24} {fvg_str:<22} {score_str:<6} {msg}")

        lines.append("=" * 95)
        return "\n".join(lines)
