"""
Risk & Portfolio Management Engine.
Implements 1% equity risk per trade, portfolio risk limits, daily loss limits,
consecutive loss cooldown, and correlation filtering.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from config import Config
from exchange.binance_client import SymbolInfo


@dataclass
class PositionSizeResult:
    is_valid: bool
    risk_amount: float
    stop_distance: float
    raw_quantity: float
    formatted_quantity: float
    notional_value: float
    leverage: int
    rejection_reason: Optional[str] = None


class RiskManager:
    def __init__(self, config: Config):
        self.config = config
        self.starting_daily_equity: Optional[float] = None
        self.current_daily_date: Optional[str] = None
        self.daily_realized_pnl: float = 0.0
        self.daily_trade_count: int = 0
        self.consecutive_losses: int = 0
        self.cooldown_until: Optional[float] = None

    def _update_daily_cycle(self, current_equity: float, now_dt: Optional[datetime] = None) -> None:
        """Reset daily tracking metrics at 00:00 UTC."""
        dt = now_dt or datetime.now(timezone.utc)
        today_str = dt.strftime("%Y-%m-%d")

        if self.current_daily_date != today_str:
            self.current_daily_date = today_str
            self.starting_daily_equity = current_equity
            self.daily_realized_pnl = 0.0
            self.daily_trade_count = 0

    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        symbol_info: Optional[SymbolInfo] = None
    ) -> PositionSizeResult:
        """
        Section 33 & 34:
        Risk exactly 1% account equity.
        RiskAmount = AccountEquity * 0.01
        PositionSize = RiskAmount / StopDistance
        """
        stop_distance = abs(entry_price - stop_loss)
        if stop_distance <= 0 or account_equity <= 0:
            return PositionSizeResult(
                is_valid=False, risk_amount=0, stop_distance=stop_distance,
                raw_quantity=0, formatted_quantity=0, notional_value=0,
                leverage=self.config.DEFAULT_LEVERAGE,
                rejection_reason="REJECTED_STRUCTURE_INVALIDATED"
            )

        risk_amount = account_equity * self.config.RISK_PER_TRADE
        raw_quantity = risk_amount / stop_distance
        notional_value = raw_quantity * entry_price

        # Format to step size if symbol info available
        formatted_qty = raw_quantity
        if symbol_info:
            step = symbol_info.step_size
            prec = symbol_info.quantity_precision
            if step > 0:
                steps = int(raw_quantity / step)
                formatted_qty = round(steps * step, prec)

            # Check min quantity & min notional
            if formatted_qty < symbol_info.min_qty:
                return PositionSizeResult(
                    is_valid=False, risk_amount=risk_amount, stop_distance=stop_distance,
                    raw_quantity=raw_quantity, formatted_quantity=formatted_qty, notional_value=notional_value,
                    leverage=self.config.DEFAULT_LEVERAGE, rejection_reason="REJECTED_MIN_QUANTITY"
                )
            if (formatted_qty * entry_price) < symbol_info.min_notional:
                return PositionSizeResult(
                    is_valid=False, risk_amount=risk_amount, stop_distance=stop_distance,
                    raw_quantity=raw_quantity, formatted_quantity=formatted_qty, notional_value=notional_value,
                    leverage=self.config.DEFAULT_LEVERAGE, rejection_reason="REJECTED_MIN_NOTIONAL"
                )

        return PositionSizeResult(
            is_valid=True,
            risk_amount=risk_amount,
            stop_distance=stop_distance,
            raw_quantity=raw_quantity,
            formatted_quantity=formatted_qty,
            notional_value=formatted_qty * entry_price,
            leverage=self.config.DEFAULT_LEVERAGE,
            rejection_reason=None
        )

    def can_open_new_trade(
        self,
        candidate_symbol: str,
        current_equity: float,
        open_positions: List[Dict[str, Any]],
        symbol_returns_df: Optional[pd.DataFrame] = None,
        now_timestamp: Optional[float] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Sections 35-40:
        Enforces Daily Loss Limit (2%), Consecutive Losses (3 -> 12h cooldown),
        Max Daily Trades (3), Max Open Positions (3), Portfolio Open Risk (3%),
        and Correlation Filter.
        """
        now_ts = now_timestamp or datetime.now(timezone.utc).timestamp()
        self._update_daily_cycle(current_equity, datetime.fromtimestamp(now_ts, timezone.utc))

        # Check Cooldown
        if self.cooldown_until and now_ts < self.cooldown_until:
            return False, "COOLDOWN_ACTIVE"

        # Section 35: Daily Loss Limit (2%)
        if self.starting_daily_equity and self.starting_daily_equity > 0:
            daily_loss_pct = -self.daily_realized_pnl / self.starting_daily_equity
            if daily_loss_pct >= self.config.MAX_DAILY_LOSS:
                return False, "REJECTED_DAILY_LIMIT"

        # Section 37: Daily Trade Limit (3 trades per day)
        if self.daily_trade_count >= self.config.MAX_DAILY_TRADES:
            return False, "REJECTED_DAILY_LIMIT"

        # Section 38: Maximum Open Positions (3)
        if len(open_positions) >= self.config.MAX_OPEN_POSITIONS:
            return False, "REJECTED_MAX_POSITIONS"

        # Check existing position on symbol
        for pos in open_positions:
            if pos.get("symbol") == candidate_symbol:
                return False, "REJECTED_EXISTING_POSITION"

        # Section 40: Portfolio Open Risk Limit (Max 3% total open risk)
        current_open_risk = sum(pos.get("risk_amount", 0.0) for pos in open_positions)
        new_trade_risk = current_equity * self.config.RISK_PER_TRADE
        if (current_open_risk + new_trade_risk) > (current_equity * self.config.MAX_OPEN_RISK * 1.001):
            return False, "REJECTED_PORTFOLIO_RISK"

        # Section 39: Correlation Filter
        if symbol_returns_df is not None and len(open_positions) >= self.config.MAX_HIGH_CORRELATION_POSITIONS:
            correlated_count = 0
            if candidate_symbol in symbol_returns_df.columns:
                cand_returns = symbol_returns_df[candidate_symbol]
                for pos in open_positions:
                    open_sym = pos.get("symbol")
                    if open_sym in symbol_returns_df.columns:
                        corr = cand_returns.corr(symbol_returns_df[open_sym])
                        if corr >= self.config.CORRELATION_THRESHOLD:
                            correlated_count += 1
                if correlated_count >= self.config.MAX_HIGH_CORRELATION_POSITIONS:
                    return False, "REJECTED_CORRELATION_LIMIT"

        return True, None

    def on_trade_closed(self, net_pnl: float, risk_amount: float, now_timestamp: Optional[float] = None) -> None:
        """Update circuit breaker state on trade closure."""
        now_ts = now_timestamp or datetime.now(timezone.utc).timestamp()
        self.daily_realized_pnl += net_pnl
        self.daily_trade_count += 1

        if net_pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.config.MAX_CONSECUTIVE_LOSSES:
                self.cooldown_until = now_ts + (self.config.COOLDOWN_HOURS * 3600)
        else:
            self.consecutive_losses = 0
