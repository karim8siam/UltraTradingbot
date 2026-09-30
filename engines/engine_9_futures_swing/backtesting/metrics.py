"""
Backtest Metrics & Holding Period Analytics Engine.
Implements all metrics specified in Section 65 & Section 66.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import numpy as np
import pandas as pd


@dataclass
class PerformanceMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    break_even_trades: int
    win_rate: float
    profit_factor: float
    total_net_pnl: float
    gross_profit: float
    gross_loss: float
    total_fees: float
    total_funding: float
    total_slippage: float
    average_win: float
    average_loss: float
    average_r: float
    expectancy: float
    max_drawdown_amount: float
    max_drawdown_percent: float
    max_consecutive_losses: int
    average_holding_hours: float
    median_holding_hours: float
    max_holding_hours: float
    long_trades_count: int
    long_win_rate: float
    long_net_pnl: float
    short_trades_count: int
    short_win_rate: float
    short_net_pnl: float
    symbol_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    monthly_breakdown: Dict[str, float] = field(default_factory=dict)
    score_vs_winrate: Dict[int, Dict[str, Any]] = field(default_factory=dict)


class MetricsEngine:
    @staticmethod
    def calculate_metrics(trades: List[Dict[str, Any]], initial_equity: float = 10000.0) -> PerformanceMetrics:
        if not trades:
            return PerformanceMetrics(
                total_trades=0, winning_trades=0, losing_trades=0, break_even_trades=0,
                win_rate=0.0, profit_factor=0.0, total_net_pnl=0.0, gross_profit=0.0,
                gross_loss=0.0, total_fees=0.0, total_funding=0.0, total_slippage=0.0,
                average_win=0.0, average_loss=0.0, average_r=0.0, expectancy=0.0,
                max_drawdown_amount=0.0, max_drawdown_percent=0.0, max_consecutive_losses=0,
                average_holding_hours=0.0, median_holding_hours=0.0, max_holding_hours=0.0,
                long_trades_count=0, long_win_rate=0.0, long_net_pnl=0.0,
                short_trades_count=0, short_win_rate=0.0, short_net_pnl=0.0
            )

        df = pd.DataFrame(trades)
        total_trades = len(df)
        
        winners = df[df["net_pnl"] > 0]
        losers = df[df["net_pnl"] < 0]
        breakevens = df[df["net_pnl"] == 0]

        winning_count = len(winners)
        losing_count = len(losers)
        be_count = len(breakevens)

        win_rate = (winning_count / total_trades) * 100.0 if total_trades > 0 else 0.0

        gross_profit = float(winners["gross_pnl"].sum()) if not winners.empty else 0.0
        gross_loss = abs(float(losers["gross_pnl"].sum())) if not losers.empty else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        total_net_pnl = float(df["net_pnl"].sum())
        total_fees = float(df["fees"].sum()) if "fees" in df.columns else 0.0
        total_funding = float(df["funding_cost"].sum()) if "funding_cost" in df.columns else 0.0
        total_slippage = float(df["slippage"].sum()) if "slippage" in df.columns else 0.0

        avg_win = float(winners["net_pnl"].mean()) if not winners.empty else 0.0
        avg_loss = abs(float(losers["net_pnl"].mean())) if not losers.empty else 0.0
        avg_r = float(df["R_multiple"].mean()) if "R_multiple" in df.columns else 0.0

        # Expectancy = (WinRate * AvgWin) - (LossRate * AvgLoss)
        win_prob = winning_count / total_trades if total_trades > 0 else 0.0
        loss_prob = losing_count / total_trades if total_trades > 0 else 0.0
        expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)

        # Drawdown calculation
        cumulative_pnl = np.cumsum(df["net_pnl"].values)
        equity_curve = initial_equity + cumulative_pnl
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = running_max - equity_curve
        max_dd_amount = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
        dd_percents = (drawdowns / running_max) * 100.0
        max_dd_pct = float(np.max(dd_percents)) if len(dd_percents) > 0 else 0.0

        # Consecutive losses
        max_consec_losses = 0
        current_streak = 0
        for pnl in df["net_pnl"].values:
            if pnl < 0:
                current_streak += 1
                if current_streak > max_consec_losses:
                    max_consec_losses = current_streak
            else:
                current_streak = 0

        # Holding duration
        holding_hours = []
        for _, row in df.iterrows():
            if "holding_hours" in row and not pd.isna(row["holding_hours"]):
                holding_hours.append(float(row["holding_hours"]))
            elif "entry_time" in row and "exit_time" in row:
                try:
                    t0 = pd.to_datetime(row["entry_time"]).timestamp()
                    t1 = pd.to_datetime(row["exit_time"]).timestamp()
                    holding_hours.append((t1 - t0) / 3600.0)
                except Exception:
                    pass

        avg_hold = float(np.mean(holding_hours)) if holding_hours else 0.0
        med_hold = float(np.median(holding_hours)) if holding_hours else 0.0
        max_hold = float(np.max(holding_hours)) if holding_hours else 0.0

        # Long vs Short
        longs = df[df["direction"].str.upper() == "LONG"]
        shorts = df[df["direction"].str.upper() == "SHORT"]

        long_trades = len(longs)
        long_win_rate = (len(longs[longs["net_pnl"] > 0]) / long_trades * 100.0) if long_trades > 0 else 0.0
        long_pnl = float(longs["net_pnl"].sum()) if not longs.empty else 0.0

        short_trades = len(shorts)
        short_win_rate = (len(shorts[shorts["net_pnl"] > 0]) / short_trades * 100.0) if short_trades > 0 else 0.0
        short_pnl = float(shorts["net_pnl"].sum()) if not shorts.empty else 0.0

        # Symbol breakdown
        sym_breakdown = {}
        for sym, grp in df.groupby("symbol"):
            s_trades = len(grp)
            s_win = len(grp[grp["net_pnl"] > 0])
            sym_breakdown[sym] = {
                "trades": s_trades,
                "win_rate": (s_win / s_trades * 100.0) if s_trades > 0 else 0.0,
                "net_pnl": float(grp["net_pnl"].sum()),
                "profit_factor": (float(grp[grp["net_pnl"] > 0]["gross_pnl"].sum()) / abs(float(grp[grp["net_pnl"] < 0]["gross_pnl"].sum()))) if abs(float(grp[grp["net_pnl"] < 0]["gross_pnl"].sum())) > 0 else 0.0
            }

        # Monthly breakdown
        monthly_breakdown = {}
        if "exit_time" in df.columns:
            try:
                df["month"] = pd.to_datetime(df["exit_time"]).dt.strftime("%Y-%m")
                for month, grp in df.groupby("month"):
                    monthly_breakdown[month] = float(grp["net_pnl"].sum())
            except Exception:
                pass

        # Score vs Win rate
        score_breakdown = {}
        if "setup_score" in df.columns:
            for score, grp in df.groupby("setup_score"):
                sc_trades = len(grp)
                sc_wins = len(grp[grp["net_pnl"] > 0])
                score_breakdown[int(score)] = {
                    "trades": sc_trades,
                    "win_rate": (sc_wins / sc_trades * 100.0) if sc_trades > 0 else 0.0,
                    "net_pnl": float(grp["net_pnl"].sum())
                }

        return PerformanceMetrics(
            total_trades=total_trades,
            winning_trades=winning_count,
            losing_trades=losing_count,
            break_even_trades=be_count,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_net_pnl=total_net_pnl,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            total_fees=total_fees,
            total_funding=total_funding,
            total_slippage=total_slippage,
            average_win=avg_win,
            average_loss=avg_loss,
            average_r=avg_r,
            expectancy=expectancy,
            max_drawdown_amount=max_dd_amount,
            max_drawdown_percent=max_dd_pct,
            max_consecutive_losses=max_consec_losses,
            average_holding_hours=avg_hold,
            median_holding_hours=med_hold,
            max_holding_hours=max_hold,
            long_trades_count=long_trades,
            long_win_rate=long_win_rate,
            long_net_pnl=long_pnl,
            short_trades_count=short_trades,
            short_win_rate=short_win_rate,
            short_net_pnl=short_pnl,
            symbol_breakdown=sym_breakdown,
            monthly_breakdown=monthly_breakdown,
            score_vs_winrate=score_breakdown
        )
