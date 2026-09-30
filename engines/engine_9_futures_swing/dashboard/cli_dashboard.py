"""
Rich Terminal Dashboard.
Implements the multi-dimensional operational view specified in Section 72.
"""

from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box

from backtesting.metrics import PerformanceMetrics


class CLIDashboard:
    def __init__(self):
        self.console = Console()

    def print_header(self, mode: str, account_equity: float, open_positions_count: int,
                     open_risk_pct: float, daily_loss_pct: float) -> None:
        title = Text("🚀 BINANCE FUTURES — SYSTEMATIC SWING TRADING BOT (v1)", style="bold cyan")
        subtitle = Text(f"MODE: [{mode}]  |  EQUITY: ${account_equity:,.2f}  |  OPEN POSITIONS: {open_positions_count}/3  |  OPEN RISK: {open_risk_pct:.1f}% / 3.0%  |  DAILY LOSS: {daily_loss_pct:.2f}% / 2.0%", style="bold white")
        self.console.print(Panel(subtitle, title=title, border_style="bright_blue"))

    def render_scan_table(self, scan_results: List[Dict[str, Any]]) -> None:
        table = Table(title="📊 Real-Time Market Scan & Swing Setup Pipeline", box=box.ROUNDED, header_style="bold magenta")
        table.add_column("Symbol", style="bold white")
        table.add_column("Direction", style="bold")
        table.add_column("Status", style="cyan")
        table.add_column("Score", justify="center")
        table.add_column("1D Trend", justify="center")
        table.add_column("4H Trend", justify="center")
        table.add_column("ADX", justify="center")
        table.add_column("Pullback %", justify="center")
        table.add_column("Entry", justify="right")
        table.add_column("Stop Loss", justify="right")
        table.add_column("Target (TP1)", justify="right")
        table.add_column("RR", justify="center")

        for r in scan_results:
            direction_style = "green" if r.get("direction") == "LONG" else ("red" if r.get("direction") == "SHORT" else "dim white")
            dir_text = Text(r.get("direction") or "NEUTRAL", style=direction_style)

            score_val = r.get("score", 0)
            score_style = "bold green" if score_val >= 14 else ("yellow" if score_val >= 10 else "dim white")
            score_text = Text(str(score_val), style=score_style)

            entry_str = f"${r['entry_price']:,.2f}" if r.get("entry_price") else "-"
            sl_str = f"${r['stop_loss']:,.2f}" if r.get("stop_loss") else "-"
            tp_str = f"${r['tp1']:,.2f}" if r.get("tp1") else "-"
            rr_str = f"{r.get('rr_ratio', 0):.2f}" if r.get("rr_ratio") else "-"

            pb_depth = r.get("pullback_depth")
            pb_str = f"{pb_depth * 100:.1f}%" if pb_depth is not None else "-"

            adx_val = r.get("adx")
            adx_str = f"{adx_val:.1f}" if adx_val is not None else "-"

            table.add_row(
                r.get("symbol", ""),
                dir_text,
                r.get("status", ""),
                score_text,
                r.get("daily_trend", "-"),
                r.get("four_h_trend", "-"),
                adx_str,
                pb_str,
                entry_str,
                sl_str,
                tp_str,
                rr_str
            )
        self.console.print(table)

    def render_backtest_summary(self, metrics: PerformanceMetrics) -> None:
        table = Table(title="📈 Backtest Performance Report (Section 65)", box=box.HEAVY_EDGE, header_style="bold green")
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="bold white")

        table.add_row("Total Completed Trades", f"{metrics.total_trades}")
        table.add_row("Win Rate", f"{metrics.win_rate:.2f}% ({metrics.winning_trades}W / {metrics.losing_trades}L / {metrics.break_even_trades}BE)")
        table.add_row("Profit Factor", f"{metrics.profit_factor:.2f}")
        table.add_row("Net PnL", f"${metrics.total_net_pnl:+,.2f}")
        table.add_row("Gross Profit / Gross Loss", f"${metrics.gross_profit:,.2f} / ${metrics.gross_loss:,.2f}")
        table.add_row("Fees / Funding / Slippage", f"${metrics.total_fees:,.2f} / ${metrics.total_funding:,.2f} / ${metrics.total_slippage:,.2f}")
        table.add_row("Average Win / Average Loss", f"${metrics.average_win:,.2f} / ${metrics.average_loss:,.2f}")
        table.add_row("Average R-Multiple", f"{metrics.average_r:+.2f} R")
        table.add_row("Trade Expectancy", f"${metrics.expectancy:+,.2f} per trade")
        table.add_row("Max Drawdown", f"${metrics.max_drawdown_amount:,.2f} ({metrics.max_drawdown_percent:.2f}%)")
        table.add_row("Max Consecutive Losses", f"{metrics.max_consecutive_losses}")
        table.add_row("Avg / Median / Max Holding Hours", f"{metrics.average_holding_hours:.1f}h / {metrics.median_holding_hours:.1f}h / {metrics.max_holding_hours:.1f}h")
        table.add_row("Long Win Rate / PnL", f"{metrics.long_win_rate:.2f}% ({metrics.long_trades_count} trades) / ${metrics.long_net_pnl:+,.2f}")
        table.add_row("Short Win Rate / PnL", f"{metrics.short_win_rate:.2f}% ({metrics.short_trades_count} trades) / ${metrics.short_net_pnl:+,.2f}")

        self.console.print(table)

        # Render Per-Symbol Table
        if metrics.symbol_breakdown:
            sym_table = Table(title="🏷️ Symbol Performance Breakdown", box=box.SIMPLE_HEAD, header_style="bold yellow")
            sym_table.add_column("Symbol", style="bold white")
            sym_table.add_column("Trades", justify="center")
            sym_table.add_column("Win Rate", justify="center")
            sym_table.add_column("Profit Factor", justify="center")
            sym_table.add_column("Net PnL", justify="right")

            for sym, s_data in metrics.symbol_breakdown.items():
                pnl_style = "green" if s_data["net_pnl"] >= 0 else "red"
                sym_table.add_row(
                    sym,
                    str(s_data["trades"]),
                    f"{s_data['win_rate']:.1f}%",
                    f"{s_data['profit_factor']:.2f}",
                    Text(f"${s_data['net_pnl']:+,.2f}", style=pnl_style)
                )
            self.console.print(sym_table)
