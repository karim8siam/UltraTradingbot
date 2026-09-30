from datetime import datetime, timezone
from typing import Dict, Any

class GFSDashboard:
    @staticmethod
    def render_cli_view(
        mode: str,
        equity: float,
        daily_pnl: float,
        daily_trades: int,
        consec_losses: int,
        symbol_states: Dict[str, Dict[str, Any]],
        open_positions: Dict[str, Dict[str, Any]],
        rejections: Dict[str, int]
    ) -> str:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        daily_pnl_pct = (daily_pnl / equity * 100.0) if equity > 0 else 0.0

        pnl_color = "\033[92m" if daily_pnl >= 0 else "\033[91m"
        reset_color = "\033[0m"
        mode_badge = f"\033[93m[{mode}]\033[0m"
        if mode == "LIVE":
            mode_badge = "\033[91;1m[LIVE TRADING]\033[0m"
        elif mode == "PAPER":
            mode_badge = "\033[96m[PAPER TRADING]\033[0m"

        hdr_sym = "SYMBOL"
        hdr_1d = "1D TREND"
        hdr_4h = "4H TREND"
        hdr_pb = "PULLBACK"
        hdr_15m = "15M STATUS"
        hdr_sc = "SCORE"
        hdr_rr = "RR"
        hdr_st = "STATE"

        lines = [
            "=" * 105,
            f"  BINANCE FUTURES — GFS MULTI-TIMEFRAME TRADING BOT (1D -> 4H -> 15M)  {mode_badge}",
            f"  Time: {now_str}  |  Equity: ${equity:,.2f}  |  Daily PnL: {pnl_color}${daily_pnl:+,.2f} ({daily_pnl_pct:+.2f}%){reset_color}",
            f"  Daily Trades: {daily_trades}/5  |  Consecutive Losses: {consec_losses}/3  |  Open Positions: {len(open_positions)}/3",
            "=" * 105,
            f"  {hdr_sym:<14} | {hdr_1d:<10} | {hdr_4h:<10} | {hdr_pb:<10} | {hdr_15m:<16} | {hdr_sc:<6} | {hdr_rr:<5} | {hdr_st:<18}",
            "-" * 110
        ]

        for sym, data in sorted(symbol_states.items()):
            d_trend = data.get("1d_trend", "NEUTRAL")
            h4_trend = data.get("4h_trend", "NEUTRAL")
            pb = data.get("pullback", "NO")
            s15 = data.get("15m_status", "IDLE")
            score = data.get("score", 0)
            rr = data.get("rr", 0.0)
            state = data.get("state", "WAITING")

            d_color = "\033[92m" if d_trend == "BULLISH" else ("\033[91m" if d_trend == "BEARISH" else "\033[90m")
            h4_color = "\033[92m" if h4_trend == "BULLISH" else ("\033[91m" if h4_trend == "BEARISH" else "\033[90m")
            st_color = "\033[94m" if "MONITOR" in state else ("\033[92m" if "POSITION" in state else "\033[0m")

            row = f"  {sym:<14} | {d_color}{d_trend:<10}{reset_color} | {h4_color}{h4_trend:<10}{reset_color} | {pb:<10} | {s15:<16} | {score:<6} | {rr:<5.1f} | {st_color}{state:<18}{reset_color}"
            lines.append(row)

        lines.append("=" * 110)

        if open_positions:
            lines.append(" ACTIVE OPEN POSITIONS:")
            h_sym, h_dir, h_entry, h_sl, h_tp, h_sz, h_rk, h_sc = "SYMBOL", "DIR", "ENTRY", "SL", "TP", "SIZE", "RISK $", "SCORE"
            lines.append(f"  {h_sym:<10} | {h_dir:<6} | {h_entry:<10} | {h_sl:<10} | {h_tp:<10} | {h_sz:<10} | {h_rk:<8} | {h_sc:<5}")
            lines.append("  " + "-" * 85)
            for sym, pos in open_positions.items():
                d = str(pos.get("direction", ""))
                ep = float(pos.get("entry_price", 0.0))
                sl = float(pos.get("stop_loss", 0.0))
                tp = float(pos.get("take_profit", 0.0))
                sz = float(pos.get("position_size", 0.0))
                rk = float(pos.get("risk_amount", 0.0))
                sc = int(pos.get("setup_score", 0))
                lines.append(f"  {sym:<10} | {d:<6} | {ep:<10.4f} | {sl:<10.4f} | {tp:<10.4f} | {sz:<10.3f} | ${rk:<7.2f} | {sc:<5}")
            lines.append("=" * 105)

        if rejections:
            top_rej = sorted(rejections.items(), key=lambda x: x[1], reverse=True)[:5]
            rej_str = " | ".join([f"{k}: {v}" for k, v in top_rej])
            lines.append(f" Setup Filter Logs: {rej_str}")
        return "\n".join(lines)