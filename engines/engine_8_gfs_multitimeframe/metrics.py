"""
Quantitative Performance Metrics Engine
Computes Win Rate, Profit Factor, Gross/Net Expectancy, Drawdown, Sharpe/Sortino, and Breakdown Reports.
"""

import math
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class TradeMetric:
    trade_id: str
    symbol: str
    direction: str
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    position_size: float
    risk_amount: float
    gross_pnl: float
    fees: float
    funding_cost: float
    net_pnl: float
    r_multiple: float
    exit_reason: str
    setup_score: int


@dataclass
class PerformanceSummary:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    break_even_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    total_fees: float = 0.0
    total_funding: float = 0.0
    total_slippage: float = 0.0
    net_pnl: float = 0.0
    return_percentage: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    average_r_multiple: float = 0.0
    gross_expectancy: float = 0.0
    net_expectancy: float = 0.0
    max_drawdown_amount: float = 0.0
    max_drawdown_pct: float = 0.0
    max_consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    long_trades: int = 0
    long_win_rate: float = 0.0
    long_net_pnl: float = 0.0
    short_trades: int = 0
    short_win_rate: float = 0.0
    short_net_pnl: float = 0.0
    symbol_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    session_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def calculate_performance_metrics(
    trades: List[TradeMetric],
    initial_equity: float = 10000.0
) -> PerformanceSummary:
    summary = PerformanceSummary()
    if not trades:
        return summary

    summary.total_trades = len(trades)
    wins: List[TradeMetric] = []
    losses: List[TradeMetric] = []
    be: List[TradeMetric] = []

    equity_curve = [initial_equity]
    current_equity = initial_equity
    peak_equity = initial_equity
    max_dd_amt = 0.0
    max_dd_pct = 0.0

    curr_consec_wins = 0
    curr_consec_losses = 0
    max_consec_wins = 0
    max_consec_losses = 0

    pnl_returns = []

    long_trades = []
    short_trades = []
    sym_dict: Dict[str, List[TradeMetric]] = {}

    for t in trades:
        net = t.net_pnl
        gross = t.gross_pnl
        fees = t.fees
        funding = t.funding_cost

        summary.total_fees += fees
        summary.total_funding += funding
        summary.net_pnl += net

        if gross > 0:
            summary.gross_profit += gross
        else:
            summary.gross_loss += abs(gross)

        if net > 0:
            wins.append(t)
            curr_consec_wins += 1
            curr_consec_losses = 0
        elif net < 0:
            losses.append(t)
            curr_consec_losses += 1
            curr_consec_wins = 0
        else:
            be.append(t)
            curr_consec_wins = 0
            curr_consec_losses = 0

        max_consec_wins = max(max_consec_wins, curr_consec_wins)
        max_consec_losses = max(max_consec_losses, curr_consec_losses)

        # Equity & Drawdown Tracking
        current_equity += net
        equity_curve.append(current_equity)
        if current_equity > peak_equity:
            peak_equity = current_equity

        dd_amt = peak_equity - current_equity
        dd_pct = (dd_amt / peak_equity * 100.0) if peak_equity > 0 else 0.0
        if dd_amt > max_dd_amt:
            max_dd_amt = dd_amt
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

        ret = (net / (current_equity - net)) if (current_equity - net) > 0 else 0.0
        pnl_returns.append(ret)

        if t.direction.upper() == "BULLISH" or t.direction.upper() == "BUY":
            long_trades.append(t)
        else:
            short_trades.append(t)

        if t.symbol not in sym_dict:
            sym_dict[t.symbol] = []
        sym_dict[t.symbol].append(t)

    # Core Stats
    summary.winning_trades = len(wins)
    summary.losing_trades = len(losses)
    summary.break_even_trades = len(be)
    summary.win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0
    summary.return_percentage = (summary.net_pnl / initial_equity * 100.0)
    summary.profit_factor = (summary.gross_profit / summary.gross_loss) if summary.gross_loss > 0 else (999.0 if summary.gross_profit > 0 else 0.0)

    summary.average_win = (sum(w.net_pnl for w in wins) / len(wins)) if wins else 0.0
    summary.average_loss = (sum(abs(l.net_pnl) for l in losses) / len(losses)) if losses else 0.0
    summary.average_r_multiple = (sum(t.r_multiple for t in trades) / len(trades)) if trades else 0.0

    # Expectancy Calculations
    win_prob = len(wins) / len(trades)
    loss_prob = len(losses) / len(trades)
    gross_avg_w = (sum(w.gross_pnl for w in wins) / len(wins)) if wins else 0.0
    gross_avg_l = (sum(abs(l.gross_pnl) for l in losses) / len(losses)) if losses else 0.0

    summary.gross_expectancy = (win_prob * gross_avg_w) - (loss_prob * gross_avg_l)
    summary.net_expectancy = (win_prob * summary.average_win) - (loss_prob * summary.average_loss)

    summary.max_drawdown_amount = max_dd_amt
    summary.max_drawdown_pct = max_dd_pct
    summary.max_consecutive_wins = max_consec_wins
    summary.max_consecutive_losses = max_consec_losses

    # Sharpe and Sortino (assumes 0% risk free rate for active trading steps)
    if len(pnl_returns) > 1:
        mean_ret = sum(pnl_returns) / len(pnl_returns)
        var_ret = sum((r - mean_ret) ** 2 for r in pnl_returns) / (len(pnl_returns) - 1)
        std_ret = math.sqrt(var_ret) if var_ret > 0 else 0.0

        downside_returns = [r for r in pnl_returns if r < 0]
        if downside_returns:
            downside_var = sum(r ** 2 for r in downside_returns) / len(downside_returns)
            downside_std = math.sqrt(downside_var) if downside_var > 0 else 0.0
        else:
            downside_std = 0.0

        summary.sharpe_ratio = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0.0
        summary.sortino_ratio = (mean_ret / downside_std * math.sqrt(252)) if downside_std > 0 else 0.0

    # Long vs Short
    summary.long_trades = len(long_trades)
    long_wins = [t for t in long_trades if t.net_pnl > 0]
    summary.long_win_rate = (len(long_wins) / len(long_trades) * 100.0) if long_trades else 0.0
    summary.long_net_pnl = sum(t.net_pnl for t in long_trades)

    summary.short_trades = len(short_trades)
    short_wins = [t for t in short_trades if t.net_pnl > 0]
    summary.short_win_rate = (len(short_wins) / len(short_trades) * 100.0) if short_trades else 0.0
    summary.short_net_pnl = sum(t.net_pnl for t in short_trades)

    # Per Symbol Breakdown
    for sym, sym_trades in sym_dict.items():
        s_wins = [t for t in sym_trades if t.net_pnl > 0]
        s_net = sum(t.net_pnl for t in sym_trades)
        summary.symbol_breakdown[sym] = {
            "total_trades": len(sym_trades),
            "win_rate": round(len(s_wins) / len(sym_trades) * 100.0, 1),
            "net_pnl": round(s_net, 2),
            "avg_r": round(sum(t.r_multiple for t in sym_trades) / len(sym_trades), 2)
        }

    return summary
