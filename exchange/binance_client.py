"""
Binance USDT-M Futures Client.
Handles dynamic exchange information, signature generation, market data feeds,
order execution, position tracking, and safety stop enforcement.
"""

import time
import hmac
import hashlib
import math
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlencode
import requests

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class SymbolInfo:
    symbol: str
    status: str
    base_asset: str
    quote_asset: str
    price_precision: int
    quantity_precision: int
    tick_size: float
    step_size: float
    min_qty: float
    min_notional: float
    max_leverage: int


class BinanceFuturesClient:
    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.BINANCE_API_KEY
        self.api_secret = config.BINANCE_API_SECRET
        
        if config.BINANCE_TESTNET:
            self.base_url = "https://testnet.binancefuture.com"
        else:
            self.base_url = "https://fapi.binance.com"
            
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key or "",
            "User-Agent": "AgySwingTradingBot/1.0"
        })
        self.symbol_specs: Dict[str, SymbolInfo] = {}
        self._time_offset = 0

    def sync_server_time(self) -> None:
        """Synchronize local time with Binance server time."""
        try:
            res = self.session.get(f"{self.base_url}/fapi/v1/time", timeout=5)
            if res.status_code == 200:
                server_time = res.json().get("serverTime", 0)
                local_time = int(time.time() * 1000)
                self._time_offset = server_time - local_time
        except Exception as e:
            logger.warning(f"Failed to sync server time: {e}")

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000) + self._time_offset

    def _sign(self, params: Dict[str, Any]) -> str:
        """Generate HMAC-SHA256 signature for authenticated requests."""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                 signed: bool = False) -> Dict[str, Any]:
        """Execute HTTP request with optional signing and error handling."""
        params = params.copy() if params else {}
        url = f"{self.base_url}{endpoint}"

        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError("API Key and Secret required for signed endpoints.")
            params["timestamp"] = self._get_timestamp()
            params["recvWindow"] = 5000
            params["signature"] = self._sign(params)

        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, timeout=10)
            elif method.upper() == "POST":
                response = self.session.post(url, data=params, timeout=10)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, params=params, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Binance API Error on {method} {endpoint}: {e}")
            if hasattr(e, "response") and e.response is not None:
                try:
                    err_json = e.response.json()
                    logger.error(f"API Error payload: {err_json}")
                    return err_json
                except Exception:
                    pass
            raise

    # ---------------- Exchange Info & Precision (Section 2) ----------------

    def fetch_exchange_info(self) -> Dict[str, SymbolInfo]:
        """Dynamically retrieve tick size, step size, precision, min notional, and limits."""
        res = self._request("GET", "/fapi/v1/exchangeInfo")
        symbols_list = res.get("symbols", [])
        
        for s in symbols_list:
            symbol_name = s["symbol"]
            status = s["status"]
            base_asset = s["baseAsset"]
            quote_asset = s["quoteAsset"]
            price_precision = s.get("pricePrecision", 2)
            quantity_precision = s.get("quantityPrecision", 3)

            tick_size = 0.01
            step_size = 0.001
            min_qty = 0.001
            min_notional = 5.0
            max_leverage = 50

            for f in s.get("filters", []):
                if f["filterType"] == "PRICE_FILTER":
                    tick_size = float(f.get("tickSize", "0.01"))
                elif f["filterType"] == "LOT_SIZE":
                    step_size = float(f.get("stepSize", "0.001"))
                    min_qty = float(f.get("minQty", "0.001"))
                elif f["filterType"] == "MIN_NOTIONAL":
                    min_notional = float(f.get("notional", "5.0"))

            self.symbol_specs[symbol_name] = SymbolInfo(
                symbol=symbol_name,
                status=status,
                base_asset=base_asset,
                quote_asset=quote_asset,
                price_precision=price_precision,
                quantity_precision=quantity_precision,
                tick_size=tick_size,
                step_size=step_size,
                min_qty=min_qty,
                min_notional=min_notional,
                max_leverage=max_leverage
            )
        return self.symbol_specs

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        if symbol not in self.symbol_specs:
            self.fetch_exchange_info()
        if symbol not in self.symbol_specs:
            raise ValueError(f"Symbol {symbol} not found on Binance USDT-M Futures.")
        return self.symbol_specs[symbol]

    def format_price(self, symbol: str, price: float) -> float:
        """Round price to valid tick size."""
        spec = self.get_symbol_info(symbol)
        precision = spec.price_precision
        tick = spec.tick_size
        rounded = round(round(price / tick) * tick, precision)
        return rounded

    def format_quantity(self, symbol: str, qty: float) -> float:
        """Round quantity down to valid step size."""
        spec = self.get_symbol_info(symbol)
        precision = spec.quantity_precision
        step = spec.step_size
        if step == 0:
            return round(qty, precision)
        steps = math.floor(qty / step)
        formatted = round(steps * step, precision)
        return formatted

    # ---------------- Market Data Endpoints ----------------

    def fetch_klines(self, symbol: str, interval: str, limit: int = 500,
                     start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[List[Any]]:
        """Fetch OHLCV candlestick data from Binance Futures."""
        params: Dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return self._request("GET", "/fapi/v1/klines", params=params)

    def fetch_funding_info(self, symbol: str) -> Dict[str, Any]:
        """Retrieve latest funding rate and next funding time (Section 44)."""
        res = self._request("GET", "/fapi/v1/premiumIndex", params={"symbol": symbol})
        return {
            "symbol": symbol,
            "last_funding_rate": float(res.get("lastFundingRate", 0.0)),
            "next_funding_time": int(res.get("nextFundingTime", 0)),
            "mark_price": float(res.get("markPrice", 0.0)),
            "index_price": float(res.get("indexPrice", 0.0))
        }

    # ---------------- Account & Orders (Signed) ----------------

    def set_leverage(self, symbol: str, leverage: int = 3) -> Dict[str, Any]:
        """Configure symbol leverage (Section 34 default 3x)."""
        return self._request("POST", "/fapi/v1/leverage", {
            "symbol": symbol,
            "leverage": leverage
        }, signed=True)

    def fetch_account_balance(self) -> Dict[str, float]:
        """Fetch total USDT wallet balance, unrealized PnL, and available equity."""
        res = self._request("GET", "/fapi/v2/account", signed=True)
        total_wallet_balance = float(res.get("totalWalletBalance", 0.0))
        total_unrealized_profit = float(res.get("totalUnrealizedProfit", 0.0))
        total_margin_balance = float(res.get("totalMarginBalance", 0.0))
        available_balance = float(res.get("availableBalance", 0.0))
        
        return {
            "wallet_balance": total_wallet_balance,
            "unrealized_pnl": total_unrealized_profit,
            "equity": total_margin_balance if total_margin_balance > 0 else total_wallet_balance,
            "available_margin": available_balance
        }

    def fetch_positions(self) -> List[Dict[str, Any]]:
        """Fetch active positions."""
        res = self._request("GET", "/fapi/v2/positionRisk", signed=True)
        active_positions = []
        for p in res:
            amt = float(p.get("positionAmt", 0.0))
            if abs(amt) > 1e-6:
                active_positions.append({
                    "symbol": p["symbol"],
                    "position_amt": amt,
                    "entry_price": float(p["entryPrice"]),
                    "mark_price": float(p["markPrice"]),
                    "unrealized_pnl": float(p["unRealizedProfit"]),
                    "leverage": int(p["leverage"]),
                    "margin_type": p["marginType"],
                    "liquidation_price": float(p["liquidationPrice"])
                })
        return active_positions

    def place_order(self, symbol: str, side: str, order_type: str, quantity: float,
                    price: Optional[float] = None, stop_price: Optional[float] = None,
                    reduce_only: bool = False, client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """Place an order with unique client ID and parameter verification."""
        formatted_qty = self.format_quantity(symbol, quantity)
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": formatted_qty,
        }

        if price is not None:
            params["price"] = self.format_price(symbol, price)
            params["timeInForce"] = "GTC"

        if stop_price is not None:
            params["stopPrice"] = self.format_price(symbol, stop_price)

        if reduce_only:
            params["reduceOnly"] = "true"

        if client_order_id:
            params["newClientOrderId"] = client_order_id
        else:
            params["newClientOrderId"] = f"AGY_{symbol}_{int(time.time() * 1000)}"

        return self._request("POST", "/fapi/v1/order", params=params, signed=True)

    def cancel_order(self, symbol: str, order_id: Optional[int] = None, client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """Cancel a specific order."""
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        return self._request("DELETE", "/fapi/v1/order", params=params, signed=True)

    def cancel_all_open_orders(self, symbol: str) -> Dict[str, Any]:
        """Cancel all open orders for a given symbol."""
        return self._request("DELETE", "/fapi/v1/allOpenOrders", params={"symbol": symbol}, signed=True)

    def emergency_market_close(self, symbol: str, current_position_amt: float) -> Dict[str, Any]:
        """Safety failsafe (Section 55): Immediate market close if SL fails to be placed."""
        side = "SELL" if current_position_amt > 0 else "BUY"
        qty = abs(current_position_amt)
        logger.warning(f"EMERGENCY CLOSE for {symbol}: {side} {qty}")
        return self.place_order(
            symbol=symbol,
            side=side,
            order_type="MARKET",
            quantity=qty,
            reduce_only=True,
            client_order_id=f"EMERGENCY_CLOSE_{symbol}_{int(time.time())}"
        )
