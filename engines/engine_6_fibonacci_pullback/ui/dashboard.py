"""
Terminal Dashboard for Strategy Monitoring
Section 66 Specification
"""

import datetime
from typing import Dict, List, Optional
from core.types import StrategyState, TrendType
from core.state_machine import SymbolStateMachine


class TerminalDashboard:
    @staticmethod
    def render(
        mode: str,
        equity: float,
        daily_pnl: float,
        daily_loss_pct: float,
        daily_trades: int,
        consecutive_losses: int,
        state_machines: Dict[str, SymbolStateMachine],
        open_positions: List[Dict],
    ):
        utc_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        pnl_color = "\033[92m" if daily_pnl >= 0 else "\033[91m"
        reset_color = "\033[0m"

        mode_badge = f"\033[93m[{mode}]\033[0m" if mode != "LIVE" else "\033[91m[LIVE TRADING]\033[0m"

        print("\n" + "=" * 85)
        print(f"  BINANCE FUTURES — FIBONACCI PULLBACK TRADING BOT  |  {mode_badge}  |  {utc_now}")
        print("=" * 85)

        # Portfolio Summary
        eq_str = f"{equity:,.2f}"
        pnl_str = f"{daily_pnl:+,.2f}"
        print(
            f"  Account Equity: \033[1m$" + eq_str + f"\033[0m  |  "
            f"Today PnL: " + pnl_color + "$" + pnl_str + f" ({daily_loss_pct:.2f}%)" + reset_color + f"  |  "
            f"Trades Today: {daily_trades}/5  |  Consecutive Losses: {consecutive_losses}/3"
        )
        print("-" * 85)

        # Active Positions
        print("  ACTIVE POSITIONS:")
        if not open_positions:
            print("    (No open positions)")
        else:
            for p in open_positions:
                sym_val = p.get('symbol', '')
                side_val = p.get('side', '')
                side_color = "\033[92m" if side_val == "LONG" else "\033[91m"
                ep = p.get('entry_price', 0)
                sl = p.get('sl_price', 0)
                tp = p.get('tp_price', 0)
                ra = p.get('risk_amount', 0)
                qty_val = p.get('quantity', 0)
                print(
                    f"    • {sym_val:<9} {side_color}{side_val:<5}{reset_color} | "
                    f"Entry: ${ep:,.2f} | "
                    f"SL: ${sl:,.2f} | "
                    f"TP: ${tp:,.2f} | "
                    f"Qty: {qty_val} | "
                    f"Risk: ${ra:,.2f}"
                )
        print("-" * 85)

        # Symbol States Table
        print(f"  SYMBOL     4H BIAS    1H BIAS    CURRENT STATE                SCORE ")
        print("  " + "-" * 70)
        for sym, sm in state_machines.items():
            b4 = sm.bias_4h.value if hasattr(sm.bias_4h, "value") else str(sm.bias_4h)
            b1 = sm.bias_1h.value if hasattr(sm.bias_1h, "value") else str(sm.bias_1h)
            st = sm.state.value if hasattr(sm.state, "value") else str(sm.state)
            sc = str(sm.current_setup.score) if sm.current_setup else "-"

            c4 = "\033[92m" if b4 == "BULLISH" else ("\033[91m" if b4 == "BEARISH" else "\033[90m")
            c1 = "\033[92m" if b1 == "BULLISH" else ("\033[91m" if b1 == "BEARISH" else "\033[90m")

            print(f"  {sym:<10} {c4}{b4:<10}{reset_color} {c1}{b1:<10}{reset_color} {st:<28} {sc:<6}")

        print("=" * 85 + "\n")
