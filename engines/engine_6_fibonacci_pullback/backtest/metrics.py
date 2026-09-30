"""
Backtest Metrics & Expectancy Calculation Engine
Sections 59 & 60 Specification
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List
from core.types import TradeRecord


@dataclass
class PerformanceMetrics:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    win_rate: float = 0.0
    loss_rate: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pnl: float = 0.0
    total_fees: float = 0.0
    total_funding: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    average_r: float = 0.0
    gross_expectancy: float = 0.0
    net_expectancy: float = 0.0
    max_drawdown_amount: float = 0.0
    max_drawdown_pct: float = 0.0
    max_consecutive_losses: int = 0
    largest_winner: float = 0.0
    largest_loser: float = 0.0
    avg_duration_minutes: float = 0.0
    long_trades_count: int = 0
    long_win_rate: float = 0.0
    short_trades_count: int = 0
    short_win_rate: float = 0.0
    trades_by_symbol: Dict[str, Dict] = field(default_factory=dict)
    trades_by_zone: Dict[str, Dict] = field(default_factory=dict)
    trades_by_score: Dict[int, Dict] = field(default_factory=dict)


class MetricsCalculator:
    @staticmethod
    def calculate(trades: List[TradeRecord], initial_capital: float = 10000.0) -> PerformanceMetrics:
        if not trades:
            return PerformanceMetrics()

        m = PerformanceMetrics()
        m.total_trades = len(trades)

        wins = [t for t in trades if t.net_pnl > 0]
        losses = [t for t in trades if t.net_pnl < 0]
        m.winning_trades = len(wins)
        m.losing_trades = len(losses)
        m.breakeven_trades = m.total_trades - m.winning_trades - m.losing_trades

        m.win_rate = m.winning_trades / m.total_trades if m.total_trades > 0 else 0.0
        m.loss_rate = m.losing_trades / m.total_trades if m.total_trades > 0 else 0.0

        m.gross_profit = sum(t.gross_pnl for t in wins)
        m.gross_loss = abs(sum(t.gross_pnl for t in losses))
        m.total_fees = sum(t.fees for t in trades)
        m.total_funding = sum(t.funding_cost for t in trades)
        m.net_pnl = sum(t.net_pnl for t in trades)

        m.profit_factor = (
            (m.gross_profit / m.gross_loss)
            if m.gross_loss > 0
            else (m.gross_profit if m.gross_profit > 0 else 0.0)
        )

        m.average_win = (m.gross_profit / len(wins)) if wins else 0.0
        m.average_loss = (m.gross_loss / len(losses)) if losses else 0.0

        # R-Multiples
        r_multiples = [
            (t.net_pnl / t.risk_amount) if t.risk_amount > 0 else 0.0 for t in trades
        ]
        m.average_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0.0

        # Section 60: Expectancy = (WinRate * AvgWin) - (LossRate * AvgLoss)
        m.gross_expectancy = (m.win_rate * m.average_win) - (m.loss_rate * m.average_loss)
        net_avg_win = sum(t.net_pnl for t in wins) / len(wins) if wins else 0.0
        net_avg_loss = abs(sum(t.net_pnl for t in losses)) / len(losses) if losses else 0.0
        m.net_expectancy = (m.win_rate * net_avg_win) - (m.loss_rate * net_avg_loss)

        # Max Drawdown & Consecutive Losses
        equity = initial_capital
        peak = equity
        max_dd_amt = 0.0
        max_dd_pct = 0.0
        consec_losses = 0
        max_consec = 0

        for t in trades:
            equity += t.net_pnl
            if equity > peak:
                peak = equity
            dd = peak - equity
            dd_pct = (dd / peak) * 100 if peak > 0 else 0.0
            if dd > max_dd_amt:
                max_dd_amt = dd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

            if t.net_pnl < 0:
                consec_losses += 1
                if consec_losses > max_consec:
                    max_consec = consec_losses
            else:
                consec_losses = 0

        m.max_drawdown_amount = max_dd_amt
        m.max_drawdown_pct = max_dd_pct
        m.max_consecutive_losses = max_consec

        m.largest_winner = max([t.net_pnl for t in trades], default=0.0)
        m.largest_loser = min([t.net_pnl for t in trades], default=0.0)

        # Durations
        durations = [
            (t.exit_time - t.entry_time) / (60 * 1000.0)
            for t in trades
            if t.exit_time > t.entry_time
        ]
        m.avg_duration_minutes = sum(durations) / len(durations) if durations else 0.0

        # Long vs Short
        longs = [t for t in trades if t.side == 'LONG']
        shorts = [t for t in trades if t.side == 'SHORT']
        m.long_trades_count = len(longs)
        m.long_win_rate = (len([t for t in longs if t.net_pnl > 0]) / len(longs)) if longs else 0.0
        m.short_trades_count = len(shorts)
        m.short_win_rate = (len([t for t in shorts if t.net_pnl > 0]) / len(shorts)) if shorts else 0.0

        # Breakdowns by Symbol
        symbols = set(t.symbol for t in trades)
        for s in symbols:
            s_trades = [t for t in trades if t.symbol == s]
            s_wins = [t for t in s_trades if t.net_pnl > 0]
            m.trades_by_symbol[s] = {
                'trades': len(s_trades),
                'win_rate': len(s_wins) / len(s_trades) if s_trades else 0.0,
                'net_pnl': sum(t.net_pnl for t in s_trades),
            }

        # Breakdowns by Fib Zone
        zones = set(t.fib_zone for t in trades if t.fib_zone)
        for z in zones:
            z_trades = [t for t in trades if t.fib_zone == z]
            z_wins = [t for t in z_trades if t.net_pnl > 0]
            m.trades_by_zone[z] = {
                'trades': len(z_trades),
                'win_rate': len(z_wins) / len(z_trades) if z_trades else 0.0,
                'net_pnl': sum(t.net_pnl for t in z_trades),
            }

        return m
