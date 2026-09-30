import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from config import Config
from database import Database
from market_data.binance_client import BinanceFuturesClient
from execution.risk_manager import RiskManager
from execution.order_manager import OrderManager
from execution.position_guard import PositionGuard
from strategy.models import SMCSetup, TradeSide

logger = logging.getLogger("SMC_Executor")

class ExecutionCoordinator:
    def __init__(self, config: Config, db: Database, client: BinanceFuturesClient,
                 risk_manager: RiskManager):
        self.config = config
        self.db = db
        self.client = client
        self.risk_manager = risk_manager
        self.order_manager = OrderManager(timeout_minutes=config.ENTRY_ORDER_TIMEOUT_MINUTES)
        self.position_guard = PositionGuard(client, self.order_manager)

        # Virtual state for dry-run/paper trading
        self.virtual_equity = config.INITIAL_EQUITY
        self.virtual_open_positions: Dict[str, Dict[str, Any]] = {}
        self.virtual_pending_orders: Dict[str, Dict[str, Any]] = {}

    def execute_setup(self, setup: SMCSetup, current_account_equity: float,
                      starting_daily_equity: float, today_realized_pnl: float,
                      today_trade_count: int, open_positions_count: int,
                      has_position_on_symbol: bool) -> Dict[str, Any]:
        """
        Coordinates complete setup execution across DRY_RUN, PAPER, TESTNET, or LIVE modes.
        """
        symbol = setup.symbol
        side = setup.side
        mode = self.config.get_mode_name()

        # 1. Risk Pre-Checks
        allowed, risk_reason = self.risk_manager.check_trade_allowed(
            current_equity=current_account_equity,
            starting_daily_equity=starting_daily_equity,
            today_realized_pnl=today_realized_pnl,
            today_trade_count=today_trade_count,
            open_positions_count=open_positions_count,
            symbol_has_open_position=has_position_on_symbol
        )

        if not allowed:
            self.db.log_rejected_signal(
                symbol=symbol,
                reason=risk_reason,
                bias_4h=setup.bias_4h.value,
                bias_1h=setup.bias_1h.value,
                score=setup.setup_score,
                rr=setup.rr,
                details=f"Risk check failed: {risk_reason}"
            )
            return {"status": "REJECTED", "reason": risk_reason}

        # 2. Precision & Sizing
        rules = self.client.get_symbol_rules(symbol) if not self.config.DRY_RUN else {
            "tickSize": 0.1, "stepSize": 0.001, "minQty": 0.001, "minNotional": 5.0,
            "pricePrecision": 2, "quantityPrecision": 3
        }

        pos_qty, notional, risk_amount, size_status = self.risk_manager.calculate_position_size(
            account_equity=current_account_equity,
            entry_price=setup.entry_price,
            stop_loss=setup.stop_loss,
            symbol_rules=rules
        )

        if size_status != "VALID":
            self.db.log_rejected_signal(
                symbol=symbol,
                reason=f"REJECTED_POSITION_SIZE_{size_status}",
                bias_4h=setup.bias_4h.value,
                bias_1h=setup.bias_1h.value,
                score=setup.setup_score,
                rr=setup.rr,
                details=f"Sizing validation: {size_status}"
            )
            return {"status": "REJECTED", "reason": size_status}

        setup.risk_amount = risk_amount
        setup.position_size = pos_qty

        # 3. Format Entry Price
        formatted_entry = self.order_manager.format_price(
            setup.entry_price, rules.get("tickSize", 0.01), rules.get("pricePrecision", 2)
        )
        formatted_sl = self.order_manager.format_price(
            setup.stop_loss, rules.get("tickSize", 0.01), rules.get("pricePrecision", 2)
        )
        formatted_tp = self.order_manager.format_price(
            setup.take_profit, rules.get("tickSize", 0.01), rules.get("pricePrecision", 2)
        )

        client_order_id = self.order_manager.generate_client_order_id(symbol, side, "ENTRY")

        # 4. Handle Execution Mode
        if mode in ("DRY_RUN", "PAPER"):
            # Record Virtual / Paper Order
            trade_record = {
                "trade_id": client_order_id,
                "symbol": symbol,
                "side": side.value,
                "bias_4h": setup.bias_4h.value,
                "bias_1h": setup.bias_1h.value,
                "bias_15m": setup.bias_15m.value,
                "liquidity_type": setup.sweep_event.liquidity_level.level_type.value,
                "liquidity_level": setup.sweep_event.liquidity_level.price,
                "sweep_high": setup.sweep_event.sweep_high,
                "sweep_low": setup.sweep_event.sweep_low,
                "mss_level": setup.mss_event.broken_swing_level,
                "displacement_size": setup.fvg_event.midpoint,
                "fvg_high": setup.fvg_event.fvg_high,
                "fvg_low": setup.fvg_event.fvg_low,
                "fvg_midpoint": setup.fvg_event.midpoint,
                "entry": formatted_entry,
                "stop_loss": formatted_sl,
                "take_profit": formatted_tp,
                "risk_amount": risk_amount,
                "position_size": pos_qty,
                "leverage": self.config.DEFAULT_LEVERAGE,
                "rr": setup.rr,
                "setup_score": setup.setup_score,
                "atr": setup.atr,
                "funding_rate": setup.funding_rate,
                "entry_time": datetime.now(timezone.utc).isoformat(),
                "result": "OPEN",
                "client_order_id": client_order_id,
                "sl_order_id": f"SIM_SL_{client_order_id}",
                "tp_order_id": f"SIM_TP_{client_order_id}",
                "mode": mode
            }
            self.db.record_trade_opened(trade_record)
            self.virtual_open_positions[symbol] = trade_record
            logger.info(f"[{mode}] Placed simulated trade {client_order_id} on {symbol} {side.value} at {formatted_entry} (SL: {formatted_sl}, TP: {formatted_tp}, Qty: {pos_qty})")
            return {"status": "SUCCESS", "mode": mode, "trade_id": client_order_id, "data": trade_record}

        # 5. Live / Testnet Execution
        if not self.config.is_live_allowed() and not self.config.BINANCE_TESTNET:
            return {"status": "BLOCKED", "reason": "LIVE_TRADING_GATE_LOCKED"}

        try:
            # Set Leverage
            self.client.set_leverage(symbol, self.config.DEFAULT_LEVERAGE)
            
            # Place Limit FVG Entry
            order_side = "BUY" if side == TradeSide.LONG else "SELL"
            entry_res = self.client.place_order(
                symbol=symbol,
                side=order_side,
                order_type="LIMIT",
                quantity=pos_qty,
                price=formatted_entry,
                client_order_id=client_order_id,
                time_in_force="GTC"
            )
            logger.info(f"[{mode}] Entry order placed for {symbol}: {entry_res}")
            return {"status": "ORDER_PLACED", "order_id": entry_res.get("orderId"), "client_order_id": client_order_id}
        except Exception as e:
            logger.error(f"[{mode}] Order execution error on {symbol}: {e}")
            return {"status": "ERROR", "reason": str(e)}
