"""
Binance USDT-M Futures REST API Client
Implements secure, sanitized public & authenticated requests using pure Python.
"""

import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from core.types import Candle

logger = logging.getLogger("BinanceClient")


class BinanceClient:
    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = True,
        timeout: int = 15,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.timeout = timeout
        self.base_url = (
            "https://testnet.binancefuture.com"
            if testnet
            else "https://fapi.binance.com"
        )

    def _sign(self, query_string: str) -> str:
        """Generates HMAC-SHA256 signature for private endpoints."""
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Any:
        """Executes HTTP request with error handling and key sanitization."""
        params = params or {}
        headers = {"User-Agent": "BinanceFibBot/1.0"}

        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError("API Key and Secret required for authenticated requests")
            headers["X-MBX-APIKEY"] = self.api_key
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 5000
            query_string = urllib.parse.urlencode(params)
            signature = self._sign(query_string)
            query_string += f"&signature={signature}"
        else:
            query_string = urllib.parse.urlencode(params) if params else ""

        url = f"{self.base_url}{path}"
        if method in ("GET", "DELETE") and query_string:
            url = f"{url}?{query_string}"
            data = None
        elif method in ("POST", "PUT"):
            data = query_string.encode("utf-8") if query_string else None
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = None

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_text = resp.read().decode("utf-8")
                return json.loads(resp_text)
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            logger.error(f"HTTP {e.code} Error on {path}: {err_msg}")
            raise RuntimeError(f"Binance API Error {e.code}: {err_msg}")
        except Exception as e:
            logger.error(f"Connection error on {path}: {str(e)}")
            raise

    # ------------------ Public Endpoints ------------------ #

    def ping(self) -> bool:
        try:
            self._request("GET", "/fapi/v1/ping")
            return True
        except Exception:
            return False

    def get_server_time(self) -> int:
        res = self._request("GET", "/fapi/v1/time")
        return int(res.get("serverTime", 0))

    def get_exchange_info(self) -> Dict[str, Any]:
        return self._request("GET", "/fapi/v1/exchangeInfo")

    def get_ticker_price(self, symbol: str) -> float:
        res = self._request("GET", "/fapi/v1/ticker/price", {"symbol": symbol})
        return float(res.get("price", 0.0))

    def get_funding_rate(self, symbol: str) -> float:
        res = self._request("GET", "/fapi/v1/premiumIndex", {"symbol": symbol})
        return float(res.get("lastFundingRate", 0.0))

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Candle]:
        """Fetches historical candlestick (kline) data."""
        params: Dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": min(limit, 1000)}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        raw = self._request("GET", "/fapi/v1/klines", params)
        candles: List[Candle] = []
        for item in raw:
            candles.append(
                Candle(
                    timestamp=int(item[0]),
                    open=float(item[1]),
                    high=float(item[2]),
                    low=float(item[3]),
                    close=float(item[4]),
                    volume=float(item[5]),
                    close_time=int(item[6]),
                    is_closed=True,
                )
            )
        return candles

    # ------------------ Authenticated Endpoints ------------------ #

    def get_account_equity(self) -> float:
        res = self._request("GET", "/fapi/v2/balance", signed=True)
        for b in res:
            if b.get("asset") == "USDT":
                return float(b.get("balance", 0.0))
        return 0.0

    def get_positions(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/fapi/v2/positionRisk", signed=True)

    def set_leverage(self, symbol: str, leverage: int = 5) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/fapi/v1/leverage",
            {"symbol": symbol, "leverage": leverage},
            signed=True,
        )

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if price is not None:
            params["price"] = price
        if stop_price is not None:
            params["stopPrice"] = stop_price
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        if order_type in ("LIMIT", "STOP", "TAKE_PROFIT"):
            params["timeInForce"] = time_in_force
        if reduce_only:
            params["reduceOnly"] = "true"

        return self._request("POST", "/fapi/v1/order", params, signed=True)

    def cancel_order(self, symbol: str, order_id: Optional[int] = None, client_order_id: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        return self._request("DELETE", "/fapi/v1/order", params, signed=True)

    def cancel_all_open_orders(self, symbol: str) -> Dict[str, Any]:
        return self._request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": symbol}, signed=True)
