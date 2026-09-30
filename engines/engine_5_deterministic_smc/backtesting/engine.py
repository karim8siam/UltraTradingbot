import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from config import Config
from strategy.models import Candle, TradeSide, BiasType
from strategy.setup_evaluator import SetupEvaluator
from strategy.state_machine import SymbolStateMachine
from execution.risk_manager import RiskManager
from backtesting.metrics import PerformanceMetrics

logger = logging.getLogger("SMC_Backtester")

class BacktestEngine:
    def __init__(self, config: Config):
        self.config = config
        self.setup_evaluator = SetupEvaluator(
            min_rr=config.MIN_RR,
            min_score=config.MIN_SETUP_SCORE,
            sl_atr_multiplier=config.SL_ATR_BUFFER_MULTIPLIER,
            max_atr_ratio=config.MAX_ATR_RATIO,
            allowed_sessions=config.ALLOWED_SESSIONS,
            min_stop_distance_pct=getattr(config, "MIN_STOP_DISTANCE_PCT", 0.002)
        )
        self.risk_manager = RiskManager(
            risk_per_trade=config.RISK_PER_TRADE,
            max_daily_loss=config.MAX_DAILY_LOSS,
            max_consecutive_losses=config.MAX_CONSECUTIVE_LOSSES,
            cooldown_hours=config.CONSECUTIVE_LOSS_COOLDOWN_HOURS,
            max_daily_trades=config.MAX_DAILY_TRADES,
            max_open_positions=config.MAX_OPEN_POSITIONS,
            default_leverage=config.DEFAULT_LEVERAGE
        )

    def run_backtest(self, symbol: str, candles_4h: List[Candle], candles_1h: List[Candle],
                     candles_15m: List[Candle], candles_5m: List[Candle],
                     initial_capital: float = 10000.0) -> Dict[str, Any]:
        """
        Runs deterministic event-driven backtest iterating through closed 5M candles.
        """
        state_machine = SymbolStateMachine(symbol, self.setup_evaluator, swing_length=self.config.SWING_LENGTH)
        
        equity = initial_capital
        starting_daily_equity = initial_capital
        current_day: Optional[str] = None
        daily_trades_count = 0
        daily_realized_pnl = 0.0

        open_position: Optional[Dict[str, Any]] = None
        pending_order: Optional[Dict[str, Any]] = None
        completed_trades: List[Dict[str, Any]] = []

        # Minimum required starting candles
        min_start_idx = max(50, self.config.WARMUP_CANDLES_5M // 10)
        
        for i in range(min_start_idx, len(candles_5m)):
            current_5m_slice = candles_5m[: i + 1]
            current_bar = current_5m_slice[-1]
            curr_ts = current_bar.timestamp
            curr_dt = datetime.fromtimestamp(curr_ts / 1000.0, tz=timezone.utc)
            date_str = curr_dt.strftime("%Y-%m-%d")

            # Daily rollover check
            if date_str != current_day:
                current_day = date_str
                starting_daily_equity = equity
                daily_trades_count = 0
                daily_realized_pnl = 0.0

            # Match corresponding 4H, 1H, 15M candles closed up to curr_ts
            slice_4h = [c for c in candles_4h if c.timestamp <= curr_ts]
            slice_1h = [c for c in candles_1h if c.timestamp <= curr_ts]
            slice_15m = [c for c in candles_15m if c.timestamp <= curr_ts]

            # 1. Manage Existing Open Position
            if open_position is not None:
                side = open_position["side"]
                entry_p = open_position["entry"]
                sl_p = open_position["stop_loss"]
                tp_p = open_position["take_profit"]
                qty = open_position["position_size"]
                init_sl = open_position.get("initial_stop_loss", sl_p)
                risk_dist = abs(entry_p - init_sl)

                # A. Dynamic Breakeven Trigger (+1.5R)
                be_mult = getattr(self.config, "BREAKEVEN_R_TRIGGER", 1.5)
                if not open_position.get("is_breakeven") and risk_dist > 0:
                    if side == "LONG" and current_bar.high >= entry_p + (be_mult * risk_dist):
                        open_position["stop_loss"] = entry_p
                        open_position["is_breakeven"] = True
                        sl_p = entry_p
                    elif side == "SHORT" and current_bar.low <= entry_p - (be_mult * risk_dist):
                        open_position["stop_loss"] = entry_p
                        open_position["is_breakeven"] = True
                        sl_p = entry_p

                # B. Dynamic Partial Take Profit (+2.0R, 50% scale-out)
                ptp_mult = getattr(self.config, "PARTIAL_TP_R", 2.0)
                ptp_ratio = getattr(self.config, "PARTIAL_TP_RATIO", 0.50)
                if not open_position.get("partial_taken") and risk_dist > 0 and qty > 0:
                    ptp_hit = False
                    partial_exit_p = 0.0
                    if side == "LONG" and current_bar.high >= entry_p + (ptp_mult * risk_dist):
                        ptp_hit = True
                        partial_exit_p = entry_p + (ptp_mult * risk_dist)
                    elif side == "SHORT" and current_bar.low <= entry_p - (ptp_mult * risk_dist):
                        ptp_hit = True
                        partial_exit_p = entry_p - (ptp_mult * risk_dist)

                    if ptp_hit:
                        partial_qty = qty * ptp_ratio
                        if side == "LONG":
                            p_gross = (partial_exit_p - entry_p) * partial_qty
                        else:
                            p_gross = (entry_p - partial_exit_p) * partial_qty
                        p_fees = (entry_p * partial_qty * self.config.MAKER_FEE_RATE) + (partial_exit_p * partial_qty * self.config.TAKER_FEE_RATE)
                        p_slip = (partial_exit_p * partial_qty * self.config.ESTIMATED_SLIPPAGE)
                        p_net = p_gross - p_fees - p_slip

                        open_position["accumulated_gross_pnl"] = open_position.get("accumulated_gross_pnl", 0.0) + p_gross
                        open_position["accumulated_fees"] = open_position.get("accumulated_fees", 0.0) + p_fees + p_slip
                        open_position["accumulated_net_pnl"] = open_position.get("accumulated_net_pnl", 0.0) + p_net
                        open_position["position_size"] -= partial_qty
                        qty = open_position["position_size"]
                        open_position["partial_taken"] = True
                        # Lock in breakeven on remaining position
                        open_position["stop_loss"] = entry_p
                        open_position["is_breakeven"] = True
                        sl_p = entry_p

                # C. Check if SL or TP hit on remaining position in current bar
                sl_hit = False
                tp_hit = False

                if side == "LONG":
                    if current_bar.low <= sl_p:
                        sl_hit = True
                    elif current_bar.high >= tp_p:
                        tp_hit = True
                else:  # SHORT
                    if current_bar.high >= sl_p:
                        sl_hit = True
                    elif current_bar.low <= tp_p:
                        tp_hit = True

                if sl_hit or tp_hit:
                    exit_price = sl_p if sl_hit else tp_p
                    exit_reason = "SL_HIT" if sl_hit else "TP_HIT"
                    
                    # Calculate remaining PnL with fees & slippage
                    if side == "LONG":
                        rem_gross = (exit_price - entry_p) * qty
                    else:
                        rem_gross = (entry_p - exit_price) * qty

                    entry_notional = entry_p * qty
                    exit_notional = exit_price * qty
                    rem_fees = (entry_notional * self.config.MAKER_FEE_RATE) + (exit_notional * self.config.TAKER_FEE_RATE)
                    rem_slip = exit_notional * self.config.ESTIMATED_SLIPPAGE
                    rem_net = rem_gross - rem_fees - rem_slip

                    # Combine with any accumulated partial TP
                    tot_gross_pnl = rem_gross + open_position.get("accumulated_gross_pnl", 0.0)
                    tot_fees = rem_fees + rem_slip + open_position.get("accumulated_fees", 0.0)
                    tot_net_pnl = rem_net + open_position.get("accumulated_net_pnl", 0.0)

                    equity += tot_net_pnl
                    daily_realized_pnl += tot_net_pnl
                    is_win = (tot_net_pnl > 0)
                    self.risk_manager.record_trade_outcome(is_win, curr_dt)

                    completed_trades.append({
                        "trade_id": open_position["trade_id"],
                        "symbol": symbol,
                        "side": side,
                        "entry": entry_p,
                        "exit_price": exit_price,
                        "stop_loss": sl_p,
                        "take_profit": tp_p,
                        "position_size": open_position.get("initial_position_size", qty),
                        "entry_time": open_position["entry_time"],
                        "exit_time": curr_dt.isoformat(),
                        "gross_pnl": tot_gross_pnl,
                        "fees": tot_fees,
                        "funding_cost": 0.0,
                        "net_pnl": tot_net_pnl,
                        "result": "WIN" if is_win else "LOSS",
                        "exit_reason": exit_reason if not open_position.get("partial_taken") else f"{exit_reason}_AFTER_PARTIAL",
                        "setup_score": open_position.get("setup_score", 0),
                        "rr": open_position.get("rr", 0.0),
                        "is_breakeven": open_position.get("is_breakeven", False),
                        "partial_taken": open_position.get("partial_taken", False)
                    })
                    open_position = None
                continue

            # 2. Check Pending Limit Entry Fill
            if pending_order is not None:
                # Check timeout (30 mins = 6 bars of 5M)
                bars_waiting = i - pending_order["placed_bar_idx"]
                if bars_waiting > 6:
                    # Timeout expired
                    pending_order = None
                else:
                    target_entry = pending_order["entry"]
                    side = pending_order["side"]
                    filled = False
                    if side == "LONG" and current_bar.low <= target_entry:
                        filled = True
                    elif side == "SHORT" and current_bar.high >= target_entry:
                        filled = True

                    if filled:
                        open_position = pending_order
                        open_position["entry_time"] = curr_dt.isoformat()
                        pending_order = None
                        daily_trades_count += 1
                        continue

            # 3. Generate New Signals
            if len(slice_4h) < 10 or len(slice_1h) < 20 or len(slice_15m) < 30:
                continue

            setup, status = state_machine.process_candles(
                slice_4h, slice_1h, slice_15m, current_5m_slice
            )

            if setup:
                # Risk check
                allowed, risk_reason = self.risk_manager.check_trade_allowed(
                    current_equity=equity,
                    starting_daily_equity=starting_daily_equity,
                    today_realized_pnl=daily_realized_pnl,
                    today_trade_count=daily_trades_count,
                    open_positions_count=(1 if open_position else 0),
                    symbol_has_open_position=(open_position is not None),
                    current_time=curr_dt
                )

                if allowed:
                    rules = {"stepSize": 0.001, "minQty": 0.001, "minNotional": 5.0, "quantityPrecision": 3}
                    pos_qty, notional, risk_amount, s_status = self.risk_manager.calculate_position_size(
                        account_equity=equity,
                        entry_price=setup.entry_price,
                        stop_loss=setup.stop_loss,
                        symbol_rules=rules
                    )

                    if s_status == "VALID":
                        pending_order = {
                            "trade_id": f"BT_{symbol}_{i}",
                            "side": setup.side.value,
                            "entry": setup.entry_price,
                            "stop_loss": setup.stop_loss,
                            "initial_stop_loss": setup.stop_loss,
                            "take_profit": setup.take_profit,
                            "position_size": pos_qty,
                            "initial_position_size": pos_qty,
                            "risk_amount": risk_amount,
                            "setup_score": setup.setup_score,
                            "rr": setup.rr,
                            "placed_bar_idx": i,
                            "placed_time": curr_dt.isoformat()
                        }

        # Calculate final metrics
        metrics = PerformanceMetrics.calculate_metrics(completed_trades, initial_capital)
        return {
            "symbol": symbol,
            "metrics": metrics,
            "trades": completed_trades
        }
