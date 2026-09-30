import math
from typing import List, Dict, Any, Optional

class PerformanceMetrics:
    @staticmethod
    def calculate_metrics(trades: List[Dict[str, Any]], initial_capital: float = 10000.0) -> Dict[str, Any]:
        default_metrics = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "win_rate": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "fees": 0.0,
            "funding_cost": 0.0,
            "net_pnl": 0.0,
            "net_profit": 0.0,
            "return_pct": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "expectancy_gross": 0.0,
            "expectancy_net": 0.0,
            "max_drawdown_dollars": 0.0,
            "max_drawdown_pct": 0.0,
            "max_consecutive_losses": 0,
            "long_trades": 0,
            "long_win_rate": 0.0,
            "short_trades": 0,
            "short_win_rate": 0.0,
            "largest_winner": 0.0,
            "largest_loser": 0.0
        }

        if not trades:
            return default_metrics

        total_trades = len(trades)
        wins = [t for t in trades if t.get("net_pnl", 0.0) > 0]
        losses = [t for t in trades if t.get("net_pnl", 0.0) < 0]
        breakevens = [t for t in trades if t.get("net_pnl", 0.0) == 0]

        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate = (winning_trades / total_trades) * 100.0 if total_trades > 0 else 0.0

        gross_profit = sum(t.get("gross_pnl", 0.0) for t in wins)
        gross_loss = abs(sum(t.get("gross_pnl", 0.0) for t in losses))
        total_fees = sum(t.get("fees", 0.0) for t in trades)
        total_funding = sum(t.get("funding_cost", 0.0) for t in trades)
        net_profit = sum(t.get("net_pnl", 0.0) for t in trades)

        avg_win = (gross_profit / winning_trades) if winning_trades > 0 else 0.0
        avg_loss = (gross_loss / losing_trades) if losing_trades > 0 else 0.0

        win_rate_dec = winning_trades / total_trades if total_trades > 0 else 0.0
        loss_rate_dec = losing_trades / total_trades if total_trades > 0 else 0.0
        expectancy_gross = (win_rate_dec * avg_win) - (loss_rate_dec * avg_loss)
        expectancy_net = net_profit / total_trades if total_trades > 0 else 0.0

        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        running_equity = initial_capital
        peak_equity = initial_capital
        max_drawdown_dollars = 0.0
        max_drawdown_pct = 0.0

        for t in trades:
            running_equity += t.get("net_pnl", 0.0)
            if running_equity > peak_equity:
                peak_equity = running_equity
            dd_dollars = peak_equity - running_equity
            dd_pct = (dd_dollars / peak_equity) * 100.0 if peak_equity > 0 else 0.0
            if dd_dollars > max_drawdown_dollars:
                max_drawdown_dollars = dd_dollars
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct

        max_consec_losses = 0
        curr_consec_losses = 0
        for t in trades:
            if t.get("net_pnl", 0.0) < 0:
                curr_consec_losses += 1
                if curr_consec_losses > max_consec_losses:
                    max_consec_losses = curr_consec_losses
            else:
                curr_consec_losses = 0

        long_trades = [t for t in trades if t.get("side") == "LONG"]
        short_trades = [t for t in trades if t.get("side") == "SHORT"]
        long_wins = [t for t in long_trades if t.get("net_pnl", 0.0) > 0]
        short_wins = [t for t in short_trades if t.get("net_pnl", 0.0) > 0]
        
        long_win_rate = (len(long_wins) / len(long_trades) * 100.0) if long_trades else 0.0
        short_win_rate = (len(short_wins) / len(short_trades) * 100.0) if short_trades else 0.0

        largest_winner = max([t.get("net_pnl", 0.0) for t in trades] + [0.0])
        largest_loser = min([t.get("net_pnl", 0.0) for t in trades] + [0.0])

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "breakeven_trades": len(breakevens),
            "win_rate": win_rate,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "fees": total_fees,
            "funding_cost": total_funding,
            "net_profit": net_profit,
            "return_pct": (net_profit / initial_capital) * 100.0,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "expectancy_gross": expectancy_gross,
            "expectancy_net": expectancy_net,
            "max_drawdown_dollars": max_drawdown_dollars,
            "max_drawdown_pct": max_drawdown_pct,
            "max_consecutive_losses": max_consec_losses,
            "long_trades": len(long_trades),
            "long_win_rate": long_win_rate,
            "short_trades": len(short_trades),
            "short_win_rate": short_win_rate,
            "largest_winner": largest_winner,
            "largest_loser": largest_loser
        }
