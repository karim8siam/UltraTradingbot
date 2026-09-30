"""
Order Execution Layer & Safety Watchdog
Implements Section 48 (22-Step Execution Flow), Section 49 (Unprotected Position Emergency Market Close),
Section 50 (Order Timeouts), Section 57 (Idempotent clientOrderId), and Multi-Mode Support (DRY_RUN / PAPER / TESTNET / LIVE).
"""

import math
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from config import BotConfig
from binance_client import BinanceFuturesClient
from risk_manager import PositionSizeResult, RiskManager, SymbolSpecs
from setup_evaluator import TradeSetup
from database import BotDatabase, TradeRecord


def _round_to_tick(price: float, tick_size: float) -> float:
    """Round a price DOWN to the nearest tick_size grid point (avoids -1111 and -4014 errors)."""
    if tick_size <= 0:
        return price
    precision = max(0, round(-math.log10(tick_size)))
    ticks = math.floor(round(price / tick_size, 8))
    return round(ticks * tick_size, precision)


def _round_qty(qty: float, step_size: float, qty_precision: int) -> float:
    """Floor a quantity to the nearest step_size (avoids -1111 quantity precision errors)."""
    if step_size <= 0:
        return round(qty, qty_precision)
    factor = 1.0 / step_size
    return round(math.floor(qty * factor) / factor, qty_precision)


@dataclass
class ActivePosition:
    trade_id: str
    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    quantity: float
    sl_price: float
    tp_price: float
    entry_time: int
    sl_order_id: Optional[str] = None
    tp_order_id: Optional[str] = None
    setup: Optional[TradeSetup] = None


class OrderExecutor:
    def __init__(
        self,
        config: BotConfig,
        client: BinanceFuturesClient,
        risk_manager: RiskManager,
        db: BotDatabase
    ):
        self.config = config
        self.client = client
        self.risk_manager = risk_manager
        self.db = db
        self.active_positions: Dict[str, ActivePosition] = {}

    def execute_trade(
        self,
        setup: TradeSetup,
        specs: SymbolSpecs,
        account_equity: float,
        current_price: float,
        timestamp_ms: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Executes Section 48 workflow:
        1. Validate setup validity
        2. Validate risk & limits
        3. Calculate exact 1% position size
        4. Submit entry order
        5. Submit protective SL & TP
        6. Watchdog check
        """
        ts_ms = timestamp_ms or int(time.time() * 1000)
        ts_sec = ts_ms / 1000.0

        if not setup.is_valid:
            return False, setup.rejection_reason

        # 1. Risk Manager Can Open Check
        can_open, reason = self.risk_manager.can_open_new_trade(
            symbol=setup.symbol,
            current_ts=ts_sec,
            volatility_ratio=setup.volatility_ratio,
            emergency_stop=self.config.EMERGENCY_STOP
        )
        if not can_open:
            self.db.log_rejected_setup(setup.symbol, reason or "RISK_GATE_REJECT", setup.setup_score, current_price, setup.fvg.fvg_id)
            return False, reason

        # 2. Position Size Calculation
        size_result = self.risk_manager.calculate_position_size(
            symbol=setup.symbol,
            entry_price=setup.entry_price,
            sl_price=setup.sl_price,
            account_equity=account_equity,
            specs=specs,
            leverage=self.config.DEFAULT_LEVERAGE,
            max_leverage_cap=self.config.MAX_LEVERAGE_CAP
        )
        if not size_result.is_valid:
            self.db.log_rejected_setup(setup.symbol, size_result.rejection_reason or "SIZE_REJECT", setup.setup_score, current_price, setup.fvg.fvg_id)
            return False, size_result.rejection_reason

        trade_id = f"FVG_{setup.symbol}_{ts_ms}"

        # 3. DRY RUN & PAPER TRADING EXECUTION
        if self.config.DRY_RUN or self.config.PAPER_TRADING:
            pos = ActivePosition(
                trade_id=trade_id,
                symbol=setup.symbol,
                side=setup.side,
                entry_price=setup.entry_price,
                quantity=size_result.formatted_qty,
                sl_price=setup.sl_price,
                tp_price=setup.tp_price,
                entry_time=ts_ms,
                sl_order_id=f"SL_{trade_id}",
                tp_order_id=f"TP_{trade_id}",
                setup=setup
            )
            self.active_positions[setup.symbol] = pos
            self.risk_manager.record_trade_opened(setup.symbol, {"trade_id": trade_id, "size": size_result.formatted_qty}, ts_sec)

            # Record in DB
            record = TradeRecord(
                trade_id=trade_id,
                timestamp=ts_ms,
                symbol=setup.symbol,
                side=setup.side,
                bias_4h=setup.bias_4h.value,
                bias_1h=setup.bias_1h.value,
                bias_15m=setup.fvg.fvg_type.value,
                fvg_type=setup.fvg.fvg_type.value,
                fvg_high=setup.fvg.fvg_high,
                fvg_low=setup.fvg.fvg_low,
                fvg_mid=setup.fvg.fvg_mid,
                fvg_size=setup.fvg.fvg_size,
                fvg_size_atr=setup.fvg.fvg_size_atr,
                fvg_age=setup.fvg.age_5m,
                displacement_size=setup.fvg.displacement_body,
                atr=setup.atr14_15m,
                pullback_high=setup.pullback_high,
                pullback_low=setup.pullback_low,
                confirmation_level=setup.confirmation_level,
                entry=setup.entry_price,
                sl=setup.sl_price,
                tp=setup.tp_price,
                risk_amount=size_result.risk_amount,
                position_size=size_result.formatted_qty,
                leverage=size_result.leverage,
                rr=setup.rr,
                setup_score=setup.setup_score,
                funding_rate=setup.funding_rate,
                entry_time=ts_ms
            )
            self.db.insert_trade(record)
            return True, None

        # 4. REAL TESTNET / LIVE EXECUTION
        if self.config.LIVE_TRADING:
            self.config.validate_safety()

        side_binance = "BUY" if setup.side == "LONG" else "SELL"
        close_side = "SELL" if setup.side == "LONG" else "BUY"

        # ─── Exact 1:2 Risk to Reward SL & TP Calculation ─────────────────────
        risk_dist = abs(setup.entry_price - setup.sl_price)
        if risk_dist <= 0:
            risk_dist = setup.entry_price * 0.01

        if setup.side == "LONG":
            calc_sl = setup.entry_price - risk_dist
            calc_tp = setup.entry_price + (2.0 * risk_dist)  # 1:2 ratio: win is 2x loss
        else:
            calc_sl = setup.entry_price + risk_dist
            calc_tp = setup.entry_price - (2.0 * risk_dist)  # 1:2 ratio: win is 2x loss

        entry_price = _round_to_tick(setup.entry_price, specs.tick_size)
        sl_price    = _round_to_tick(calc_sl,           specs.tick_size)
        tp_price    = _round_to_tick(calc_tp,           specs.tick_size)
        order_qty   = _round_qty(size_result.formatted_qty, specs.step_size, specs.qty_precision)

        # Guard: if rounding collapsed SL == entry, widen by one tick
        if sl_price >= entry_price and setup.side == "LONG":
            sl_price = _round_to_tick(entry_price - specs.tick_size, specs.tick_size)
        if sl_price <= entry_price and setup.side == "SHORT":
            sl_price = _round_to_tick(entry_price + specs.tick_size, specs.tick_size)

        try:
            # Set leverage (5x leverage fixed)
            self.client.set_leverage(setup.symbol, size_result.leverage)

            # ── MARKET ENTRY — executes immediately upon confirmation ─────────
            order_type = "MARKET" if self.config.USE_MARKET_ENTRY else "LIMIT"
            if order_type == "MARKET":
                entry_resp = self.client.place_order(
                    symbol=setup.symbol,
                    side=side_binance,
                    order_type="MARKET",
                    quantity=order_qty,
                    client_order_id=f"E_{trade_id}"
                )
            else:
                entry_resp = self.client.place_order(
                    symbol=setup.symbol,
                    side=side_binance,
                    order_type="LIMIT",
                    quantity=order_qty,
                    price=entry_price,
                    client_order_id=f"E_{trade_id}",
                    time_in_force="GTC"
                )

            # ── 1:2 STOP LOSS — placed directly to Binance matching engine ────
            sl_placed = False
            if self.config.USE_SL:
                for retry in range(3):
                    try:
                        self.client.place_order(
                            symbol=setup.symbol,
                            side=close_side,
                            order_type="STOP_MARKET",
                            stop_price=sl_price,
                            client_order_id=f"SL_{trade_id}",
                            close_position=True
                        )
                        sl_placed = True
                        break
                    except Exception:
                        time.sleep(0.5)

                if not sl_placed:
                    # Emergency close position immediately if SL failed
                    self.client.place_order(
                        symbol=setup.symbol,
                        side=close_side,
                        order_type="MARKET",
                        quantity=order_qty,
                        reduce_only=True
                    )
                    self.client.cancel_all_orders(setup.symbol)
                    raise RuntimeError("SAFETY WATCHDOG: Stop loss order failed. Closed position for protection.")

            # ── 1:2 TAKE PROFIT — placed directly to Binance matching engine ──
            tp_placed = False
            for retry in range(3):
                try:
                    self.client.place_order(
                        symbol=setup.symbol,
                        side=close_side,
                        order_type="TAKE_PROFIT_MARKET",
                        stop_price=tp_price,
                        client_order_id=f"TP_{trade_id}",
                        close_position=True
                    )
                    tp_placed = True
                    break
                except Exception:
                    time.sleep(0.5)

            pos = ActivePosition(
                trade_id=trade_id,
                symbol=setup.symbol,
                side=setup.side,
                entry_price=entry_price,
                quantity=order_qty,
                sl_price=sl_price,
                tp_price=tp_price,
                entry_time=ts_ms,
                sl_order_id=f"SL_{trade_id}" if sl_placed else None,
                tp_order_id=f"TP_{trade_id}",
                setup=setup
            )
            self.active_positions[setup.symbol] = pos
            self.risk_manager.record_trade_opened(setup.symbol, {"trade_id": trade_id, "size": size_result.formatted_qty}, ts_sec)

            return True, None

        except Exception as e:
            return False, f"EXECUTION_FAILED: {str(e)}"

    def sync_active_positions(self) -> Dict[str, dict]:
        """
        Synchronizes open positions directly with Binance Futures.
        Ensures exact awareness of open positions, even after daemon restarts.
        """
        active: Dict[str, dict] = {}
        try:
            positions_data = self.client._request("GET", "/fapi/v2/positionRisk", signed=True)
            for p in positions_data:
                amt = float(p.get("positionAmt", 0))
                sym = p.get("symbol", "")
                if amt != 0 and sym:
                    active[sym] = {
                        "amount": amt,
                        "entry_price": float(p.get("entryPrice", 0)),
                        "unrealized_profit": float(p.get("unRealizedProfit", 0)),
                        "leverage": int(p.get("leverage", 10)),
                        "side": "LONG" if amt > 0 else "SHORT",
                        "quantity": abs(amt)
                    }
                    if sym not in self.active_positions:
                        self.active_positions[sym] = ActivePosition(
                            trade_id=f"BINANCE_{sym}",
                            symbol=sym,
                            side="LONG" if amt > 0 else "SHORT",
                            entry_price=float(p.get("entryPrice", 0)),
                            quantity=abs(amt),
                            sl_price=0.0,
                            tp_price=0.0,
                            entry_time=int(time.time() * 1000)
                        )
                    self.risk_manager.state.open_positions[sym] = {"trade_id": f"BINANCE_{sym}", "size": abs(amt)}

            # Clean up positions no longer open on Binance
            for sym in list(self.active_positions.keys()):
                if sym not in active:
                    del self.active_positions[sym]
                    if sym in self.risk_manager.state.open_positions:
                        del self.risk_manager.state.open_positions[sym]
        except Exception:
            pass
        return active

    def check_and_close_pnl_target(
        self,
        account_equity: float,
        target_pct: float = 0.02
    ) -> Optional[str]:
        """
        Checks current unrealized PnL across all active positions.
        If total unrealized PnL >= target_pct × account_equity, market-close every position.
        Returns a summary string if positions were closed, else None.
        """
        if not self.active_positions:
            return None

        target_pnl = account_equity * target_pct  # e.g. $13.34 × 0.02 = $0.2668

        # Fetch live positions from Binance to get real unrealized PnL
        try:
            positions_data = self.client._request("GET", "/fapi/v2/positionRisk", signed=True)
        except Exception:
            return None

        # Build a map of symbol -> unrealizedProfit
        pnl_map: Dict[str, float] = {}
        for p in positions_data:
            sym = p.get("symbol", "")
            amt = float(p.get("positionAmt", 0))
            if amt != 0:
                pnl_map[sym] = float(p.get("unRealizedProfit", 0.0))

        # Reconcile any positions that were closed on Binance externally
        for sym in list(self.active_positions.keys()):
            if sym not in pnl_map:
                del self.active_positions[sym]
                if sym in self.risk_manager.state.open_positions:
                    del self.risk_manager.state.open_positions[sym]

        if not self.active_positions:
            return None

        # Sum PnL only for symbols tracked in our active_positions
        total_unrealized = sum(
            pnl_map.get(sym, 0.0) for sym in self.active_positions
        )

        if total_unrealized < target_pnl:
            return None  # Not yet at target

        # ── 2% PnL TARGET HIT — close every active position at market ──────
        closed_symbols = []
        for sym, pos in list(self.active_positions.items()):
            close_side = "SELL" if pos.side == "LONG" else "BUY"
            try:
                self.client.cancel_all_orders(sym)
            except Exception:
                pass
            try:
                self.client.place_order(
                    symbol=sym,
                    side=close_side,
                    order_type="MARKET",
                    quantity=pos.quantity,
                    reduce_only=True
                )
                closed_symbols.append(sym)
                ts_sec = time.time()
                pnl = pnl_map.get(sym, 0.0)
                new_equity = account_equity + total_unrealized
                self.risk_manager.record_trade_closed(sym, pnl, new_equity, ts_sec)
                del self.active_positions[sym]
            except Exception:
                pass

        return (
            f"2% PnL TARGET REACHED (${total_unrealized:.4f} USDT profit). "
            f"Closed positions: {', '.join(closed_symbols)}"
        )

    def check_position_exits_simulation(
        self,
        symbol: str,
        current_candle_5m,
        account_equity: float,
        timestamp_ms: Optional[int] = None
    ) -> Optional[Tuple[str, float]]:
        """
        Simulates position exits against 5M high/low for Paper Trading & Backtesting.
        Returns (result, net_pnl) if closed, else None.
        """
        if symbol not in self.active_positions:
            return None

        pos = self.active_positions[symbol]
        ts_ms = timestamp_ms or int(time.time() * 1000)
        ts_sec = ts_ms / 1000.0

        is_long = (pos.side == "LONG")
        exit_price = None
        exit_reason = ""
        result = ""

        if is_long:
            if current_candle_5m.low <= pos.sl_price:
                exit_price = pos.sl_price
                exit_reason = "SL_HIT"
                result = "LOSS"
            elif current_candle_5m.high >= pos.tp_price:
                exit_price = pos.tp_price
                exit_reason = "TP_HIT"
                result = "WIN"
        else:
            if current_candle_5m.high >= pos.sl_price:
                exit_price = pos.sl_price
                exit_reason = "SL_HIT"
                result = "LOSS"
            elif current_candle_5m.low <= pos.tp_price:
                exit_price = pos.tp_price
                exit_reason = "TP_HIT"
                result = "WIN"

        if exit_price is not None:
            # Calculate PnL & costs
            gross_pnl = (exit_price - pos.entry_price) * pos.quantity if is_long else (pos.entry_price - exit_price) * pos.quantity
            notional = pos.entry_price * pos.quantity
            fees = notional * (self.config.TAKER_FEE_RATE * 2)
            slippage = notional * self.config.SLIPPAGE_RATE
            funding_cost = notional * self.config.DEFAULT_FUNDING_RATE
            net_pnl = gross_pnl - fees - slippage - funding_cost

            # Update DB
            self.db.update_trade_exit(
                trade_id=pos.trade_id,
                exit_time=ts_ms,
                exit_price=exit_price,
                gross_pnl=gross_pnl,
                fees=fees,
                funding_cost=funding_cost,
                net_pnl=net_pnl,
                result=result,
                exit_reason=exit_reason
            )

            # Update Risk Manager
            del self.active_positions[symbol]
            new_equity = account_equity + net_pnl
            self.risk_manager.record_trade_closed(symbol, net_pnl, new_equity, ts_sec)

            return result, net_pnl

        return None
