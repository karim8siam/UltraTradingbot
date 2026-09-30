import hmac
import hashlib
import time
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional, List

logger = logging.getLogger("BinanceClient")

class BinanceFuturesClient:
    def __init__(self, api_key: str = "", api_secret: str = "", is_testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_testnet = is_testnet
        
        if is_testnet:
            self.base_url = "https://testnet.binancefuture.com"
        else:
            self.base_url = "https://fapi.binance.com"
            
        self.public_mirrors = [
            "https://data-api.binance.vision",
            "https://api.binance.com",
            "https://fapi.binance.com"
        ]
            
        self.symbol_info_cache: Dict[str, Dict[str, Any]] = {}
        self.leverage_brackets_cache: Dict[str, Any] = {}

    def _sign_payload(self, params: Dict[str, Any]) -> str:
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return f"{query_string}&signature={signature}"

    def _send_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                      signed: bool = False, max_retries: int = 3) -> Dict[str, Any]:
        params = params or {}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SMC-Bot/1.0"
        }
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            query_string = self._sign_payload(params)
        else:
            query_string = urllib.parse.urlencode(params) if params else ""

        url = f"{self.base_url}{endpoint}"
        if method == "GET" and query_string:
            url = f"{url}?{query_string}"
            req_data = None
        elif method in ("POST", "DELETE") and query_string:
            req_data = query_string.encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            req_data = None

        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)

        for attempt in range(1, max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    res_body = response.read().decode("utf-8")
                    return json.loads(res_body)
            except urllib.error.HTTPError as e:
                error_msg = e.read().decode("utf-8")
                logger.error(f"HTTP Error {e.code} on {endpoint}: {error_msg}")
                if attempt == max_retries or e.code in (400, 401, 403):
                    raise RuntimeError(f"Binance API Error {e.code}: {error_msg}")
                time.sleep(attempt * 0.5)
            except Exception as e:
                logger.error(f"Network error on {endpoint}: {e}")
                if attempt == max_retries:
                    raise
                time.sleep(attempt * 0.5)

        return {}

    def fetch_exchange_info(self) -> Dict[str, Any]:
        """
        Fetches exchange information and populates symbol filters (tick size, min qty, min notional).
        """
        data = self._send_request("GET", "/fapi/v1/exchangeInfo")
        symbols = data.get("symbols", [])
        for s in symbols:
            sym_name = s["symbol"]
            filters = {f["filterType"]: f for f in s.get("filters", [])}
            
            price_filter = filters.get("PRICE_FILTER", {})
            lot_size_filter = filters.get("LOT_SIZE", {})
            min_notional_filter = filters.get("MIN_NOTIONAL", {})
            
            tick_size = float(price_filter.get("tickSize", "0.01"))
            step_size = float(lot_size_filter.get("stepSize", "0.001"))
            min_qty = float(lot_size_filter.get("minQty", "0.001"))
            min_notional = float(min_notional_filter.get("notional", "5.0"))
            
            self.symbol_info_cache[sym_name] = {
                "symbol": sym_name,
                "status": s.get("status"),
                "pricePrecision": s.get("pricePrecision", 2),
                "quantityPrecision": s.get("quantityPrecision", 3),
                "tickSize": tick_size,
                "stepSize": step_size,
                "minQty": min_qty,
                "minNotional": min_notional,
                "contractType": s.get("contractType", "PERPETUAL")
            }
        return self.symbol_info_cache

    def get_symbol_rules(self, symbol: str) -> Dict[str, Any]:
        if not self.symbol_info_cache or symbol not in self.symbol_info_cache:
            self.fetch_exchange_info()
        return self.symbol_info_cache.get(symbol, {
            "tickSize": 0.01,
            "stepSize": 0.001,
            "minQty": 0.001,
            "minNotional": 5.0,
            "pricePrecision": 2,
            "quantityPrecision": 3
        })

    def fetch_klines(self, symbol: str, interval: str, limit: int = 500, start_time: Optional[int] = None) -> List[List[Any]]:
        """
        Fetches historical klines/candlesticks.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1500)
        }
        if start_time:
            params["startTime"] = start_time
        return self._send_request("GET", "/fapi/v1/klines", params=params)

    def fetch_premium_index(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches funding rate and mark price info.
        """
        return self._send_request("GET", "/fapi/v1/premiumIndex", params={"symbol": symbol})

    def fetch_account_balance(self) -> Dict[str, Any]:
        """
        Fetches account equity and margin balances.
        """
        return self._send_request("GET", "/fapi/v2/account", signed=True)

    def set_leverage(self, symbol: str, leverage: int = 5) -> Dict[str, Any]:
        return self._send_request("POST", "/fapi/v1/leverage", params={"symbol": symbol, "leverage": leverage}, signed=True)

    def place_order(self, symbol: str, side: str, order_type: str, quantity: float,
                    price: Optional[float] = None, stop_price: Optional[float] = None,
                    client_order_id: Optional[str] = None, reduce_only: bool = False,
                    time_in_force: str = "GTC") -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity
        }
        if price is not None:
            params["price"] = price
            params["timeInForce"] = time_in_force
        if stop_price is not None:
            params["stopPrice"] = stop_price
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        if reduce_only:
            params["reduceOnly"] = "true"

        return self._send_request("POST", "/fapi/v1/order", params=params, signed=True)

    def cancel_order(self, symbol: str, order_id: Optional[int] = None, client_order_id: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        elif client_order_id:
            params["origClientOrderId"] = client_order_id
        return self._send_request("DELETE", "/fapi/v1/order", params=params, signed=True)

    def cancel_all_orders(self, symbol: str) -> Dict[str, Any]:
        return self._send_request("DELETE", "/fapi/v1/allOpenOrders", params={"symbol": symbol}, signed=True)

    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"symbol": symbol} if symbol else {}
        return self._send_request("GET", "/fapi/v1/openOrders", params=params, signed=True)

    def fetch_positions(self) -> List[Dict[str, Any]]:
        return self._send_request("GET", "/fapi/v2/positionRisk", signed=True)
