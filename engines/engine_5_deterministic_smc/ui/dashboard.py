import os
import sys
from typing import Dict, Any, List
from datetime import datetime, timezone
from config import Config

class Dashboard:
    def __init__(self, config: Config):
        self.config = config

    def render_console(self, account_data: Dict[str, Any], symbol_states: Dict[str, Any],
                       open_positions: List[Dict[str, Any]], recent_trades: List[Dict[str, Any]]):
        mode = self.config.get_mode_name()
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = []
        lines.append("=" * 80)
        lines.append("  BINANCE USDT-M FUTURES — DETERMINISTIC SMC TRADING BOT")
        lines.append("  System Time: " + now_str + "   |   Current Mode: [" + mode + "]")
        
        if mode == "LIVE":
            lines.append("  [!] CAUTION: BOT IS CURRENTLY IN LIVE TRADING MODE — REAL CAPITAL AT RISK [!]")
        elif mode == "TESTNET":
            lines.append("  [*] Operating on Binance Futures Testnet (Virtual Balance)")
        elif mode == "PAPER":
            lines.append("  [*] Paper Trading Active (Real-Time Market Data, Zero Real Orders)")
        else:
            lines.append("  [*] Dry-Run Simulation Active (Zero Real Orders)")
        lines.append("=" * 80)

        # Account & Risk Summary
        bal = account_data.get("equity", self.config.INITIAL_EQUITY)
        daily_pnl = account_data.get("daily_pnl", 0.0)
        daily_loss_pct = account_data.get("daily_loss_pct", 0.0)
        daily_trades = account_data.get("daily_trades", 0)
        consec_losses = account_data.get("consecutive_losses", 0)

        lines.append(f"  Equity: ${bal:,.2f}  |  Today PnL: ${daily_pnl:+,.2f} ({daily_loss_pct:+.2f}%)")
        lines.append(f"  Daily Trades: {daily_trades}/{self.config.MAX_DAILY_TRADES}  |  Consecutive Losses: {consec_losses}/{self.config.MAX_CONSECUTIVE_LOSSES}  |  Leverage: {self.config.DEFAULT_LEVERAGE}x")
        lines.append("-" * 80)

        # Multi-Symbol SMC States Table
        sym_hdr = "SYMBOL"
        b4h_hdr = "4H BIAS"
        b1h_hdr = "1H BIAS"
        st_hdr = "STATE"
        tr_hdr = "LAST TRANSITION"
        lines.append(f"  {sym_hdr:<10} | {b4h_hdr:<8} | {b1h_hdr:<8} | {st_hdr:<24} | {tr_hdr}")
        lines.append("-" * 80)
        for sym in self.config.SYMBOLS:
            st = symbol_states.get(sym, {})
            b4h = st.get("bias_4h", "NEUTRAL")
            b1h = st.get("bias_1h", "NEUTRAL")
            state_val = st.get("state", "WAITING")
            reason = str(st.get("reason", "INITIALIZED"))[:24]
            lines.append(f"  {sym:<10} | {b4h:<8} | {b1h:<8} | {state_val:<24} | {reason}")

        lines.append("-" * 80)

        # Open Positions Table
        lines.append(f"  ACTIVE POSITIONS ({len(open_positions)}/{self.config.MAX_OPEN_POSITIONS}):")
        if not open_positions:
            lines.append("  (No active positions)")
        else:
            for p in open_positions:
                sym_p = p["symbol"]
                side_p = p["side"]
                entry_p = p["entry"]
                sl_p = p["stop_loss"]
                tp_p = p["take_profit"]
                qty_p = p["position_size"]
                rr_p = p.get("rr", 0.0)
                lines.append(f"  -> [{sym_p}] {side_p} Entry: {entry_p} | SL: {sl_p} | TP: {tp_p} | Qty: {qty_p} | RR: {rr_p:.2f}")

        lines.append("=" * 80)
        print("\n".join(lines))
