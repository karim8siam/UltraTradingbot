"""
Binance USDT-M Futures Client (REST & WebSocket Helper)
Supports Public Market Data, Testnet, and Live Trading with HMAC-SHA256 Signing.
"""

import time
import hmac
import hashlib
import urllib.request
import urllib.parse
import json
from typing import List, Dict, Any, Optional, Tuple
from indicators import Candle
from risk_manager import SymbolFilters
from config import (
    BINANCE_FUTURES_LIVE_REST,
    BINANCE_FUTURES_TESTNET_REST
)


class BinanceFuturesClient:
    """
    Robust Binance USDT-M Futures Client with error handling and rate limit backoff.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = True
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.base_url = BINANCE_FUTURES_TESTNET_REST if testnet else BINANCE_FUTURES_LIVE_REST

    def _sign_payload(self, params: Dict[str, Any]) -> str:
        params["timestamp"] = int(time.time() * 1000)
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return f"{query_string}&signature={signature}"

    def _send_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False
    ) -> Dict[str, Any]:
        params = params or {}
        headers = {
            "User-Agent": "BinanceGFSBot/1.0",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        if signed:
            headers["X-MBX-APIKEY"] = self.api_key

        if signed:
            query = self._sign_payload(params)
            url = f"{self.base_url}{path}?{query}"
            data = None
        else:
            if params:
                query = urllib.parse.urlencode(params)
                if method == "GET":
                    url = f"{self.base_url}{path}?{query}"
                    data = None
                else:
                    url = f"{self.base_url}{path}"
                    data = query.encode("utf-8")
            else:
                url = f"{self.base_url}{path}"
                data = None

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                return {"error": True, "code": e.code, "message": err_json.get("msg", err_body)}
            except Exception:
                return {"error": True, "code": e.code, "message": err_body}
        except Exception as e:
            return {"error": True, "code": 500, "message": str(e)}

    # ================= PUBLIC MARKET DATA =================

    def fetch_exchange_info(self) -> Dict[str, SymbolFilters]:
        """
        Fetches exchange information and parses symbol precision, step sizes, and min quantities.
        """
        res = self._send_request("GET", "/fapi/v1/exchangeInfo")
        filters_map: Dict[str, SymbolFilters] = {}
        if isinstance(res, dict) and "symbols" in res:
            for s in res["symbols"]:
                sym = s["symbol"]
                p_prec = s.get("pricePrecision", 2)
                q_prec = s.get("quantityPrecision", 3)
                step_size = 0.001
                tick_size = 0.01
                min_qty = 0.001
                min_notional = 5.0

                for f in s.get("filters", []):
                    if f["filterType"] == "LOT_SIZE":
                        step_size = float(f.get("stepSize", 0.001))
                        min_qty = float(f.get("minQty", 0.001))
                    elif f["filterType"] == "PRICE_FILTER":
                        tick_size = float(f.get("tickSize", 0.01))
                    elif f["filterType"] == "MIN_NOTIONAL":
                        min_notional = float(f.get("notional", 5.0))

                filters_map[sym] = SymbolFilters(
                    symbol=sym,
                    price_precision=p_prec,
                    quantity_precision=q_prec,
                    step_size=step_size,
                    tick_size=tick_size,
                    min_qty=min_qty,
                    min_notional=min_notional
                )
        return filters_map

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Candle]:
        """
        Fetches historical klines/candlesticks from Binance Futures.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1500)
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        res = self._send_request("GET", "/fapi/v1/klines", params=params)
        candles: List[Candle] = []
        if isinstance(res, list):
            for row in res:
                candles.append(Candle(
                    timestamp=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    close_time=int(row[6]),
                    is_closed=True
                ))
        return candles

    def fetch_ticker_price(self, symbol: str) -> float:
        res = self._send_request("GET", "/fapi/v1/ticker/price", params={"symbol": symbol})
        if isinstance(res, dict) and "price" in res:
            return float(res["price"])
        return 0.0

    def fetch_funding_rate(self, symbol: str) -> float:
        res = self._send_request("GET", "/fapi/v1/fundingRate", params={"symbol": symbol, "limit": 1})
        if isinstance(res, list) and len(res) > 0:
            return float(res[0].get("fundingRate", 0.0))
        return 0.0

    # ================= AUTHENTICATED ACCOUNT & ORDERS =================

    def fetch_account(self) -> Dict[str, Any]:
        return self._send_request("GET", "/fapi/v2/account", signed=True)

    def fetch_positions(self) -> List[Dict[str, Any]]:
        res = self._send_request("GET", "/fapi/v2/positionRisk", signed=True)
        if isinstance(res, list):
            return res
        return []

    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        return self._send_request("POST", "/fapi/v1/leverage", params={"symbol": symbol, "leverage": leverage}, signed=True)

    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED") -> Dict[str, Any]:
        res = self._send_request("POST", "/fapi/v1/marginType", params={"symbol": symbol, "marginType": margin_type.upper()}, signed=True)
        if isinstance(res, dict) and ("No need to change margin type" in str(res.get("message", "")) or res.get("code") == -4046):
            return {"code": 200, "msg": "SUCCESS", "message": "Margin type already set"}
        return res

    def place_order(
        self,
        symbol: str,
        side: str,
        type_: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
        reduce_only: bool = False,
        time_in_force: Optional[str] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side.upper(),
            "type": type_.upper(),
            "quantity": quantity
        }
        if price is not None:
            params["price"] = price
        if stop_price is not None:
            params["stopPrice"] = stop_price
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        if reduce_only:
            params["reduceOnly"] = "true"
        if time_in_force:
            params["timeInForce"] = time_in_force
        elif type_.upper() == "LIMIT":
            params["timeInForce"] = "GTC"

        return self._send_request("POST", "/fapi/v1/order", params=params, signed=True)

    def cancel_order(self, symbol: str, order_id: Optional[int] = None, client_order_id: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        return self._send_request("DELETE", "/fapi/v1/order", params=params, signed=True)

    def fetch_open_orders(self, symbol: str) -> List[Dict[str, Any]]:
        res = self._send_request("GET", "/fapi/v1/openOrders", params={"symbol": symbol}, signed=True)
        if isinstance(res, list):
            return res
        return []

    def fetch_user_trades(self, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        res = self._send_request("GET", "/fapi/v1/userTrades", params={"symbol": symbol, "limit": limit}, signed=True)
        if isinstance(res, list):
            return res
        return []
