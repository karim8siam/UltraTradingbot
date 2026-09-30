"""
Fibonacci Retracement Zone Analysis Engine
Section 61 Specification
"""

from typing import Dict, List
from core.types import FibZoneCategory, TradeRecord


class FibZoneAnalyzer:
    @staticmethod
    def analyze_zones(trades: List[TradeRecord]) -> Dict[str, Dict]:
        """
        Compares strategy performance across the three key Fibonacci pullback zones:
        - 38.2%–50.0%
        - 50.0%–61.8% (Preferred)
        - 61.8%–78.6% (Deep)
        """
        target_zones = [
            FibZoneCategory.ZONE_382_500.value,
            FibZoneCategory.ZONE_500_618.value,
            FibZoneCategory.ZONE_618_786.value,
        ]

        results: Dict[str, Dict] = {}

        for zone in target_zones:
            zone_trades = [t for t in trades if t.fib_zone == zone]
            count = len(zone_trades)
            if count == 0:
                results[zone] = {
                    "trades": 0,
                    "win_rate": 0.0,
                    "net_pnl": 0.0,
                    "gross_profit": 0.0,
                    "gross_loss": 0.0,
                    "profit_factor": 0.0,
                    "avg_r": 0.0,
                }
                continue

            wins = [t for t in zone_trades if t.net_pnl > 0]
            losses = [t for t in zone_trades if t.net_pnl < 0]
            gross_profit = sum(t.gross_pnl for t in wins)
            gross_loss = abs(sum(t.gross_pnl for t in losses))
            net_pnl = sum(t.net_pnl for t in zone_trades)
            win_rate = len(wins) / count
            pf = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

            r_vals = [(t.net_pnl / t.risk_amount) if t.risk_amount > 0 else 0.0 for t in zone_trades]
            avg_r = sum(r_vals) / count if count > 0 else 0.0

            results[zone] = {
                "trades": count,
                "win_rate": win_rate,
                "net_pnl": net_pnl,
                "gross_profit": gross_profit,
                "gross_loss": gross_loss,
                "profit_factor": pf,
                "avg_r": avg_r,
            }

        return results
