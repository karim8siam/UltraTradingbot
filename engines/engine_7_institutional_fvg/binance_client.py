"""
Binance USDT-M Futures REST Client
Pure Python standard library implementation (urllib + hmac + hashlib).
Zero external dependencies.
"""

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import gzip
from typing import Any, Dict, List, Optional, Tuple
from indicators import Candle
from risk_manager import SymbolSpecs


class BinanceFuturesClient:
    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = True,
        timeout: int = 25
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.endpoints = [
            "https://fapi.binance.com",
            "https://fapi2.binance.com",
            "https://fapi3.binance.com"
        ] if not testnet else ["https://testnet.binancefuture.com"]
        self.base_url = self.endpoints[0]
        self.timeout = timeout
        self.specs_cache: Dict[str, SymbolSpecs] = {}
        self.time_offset = 0
        self._sync_time()

    def _sync_time(self) -> None:
        """Synchronizes local clock with Binance server timestamp to prevent -1021 errors."""
        try:
            url = f"{self.endpoints[0]}/fapi/v1/time"
            req = urllib.request.Request(url, headers={"User-Agent": "BinanceFVGBot/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                server_time = res.get("serverTime", int(time.time() * 1000))
                self.time_offset = server_time - int(time.time() * 1000)
        except Exception:
            self.time_offset = 0

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False
    ) -> Any:
        params = params or {}
        if signed:
            params["recvWindow"] = 60000
            params["timestamp"] = int(time.time() * 1000) + self.time_offset
            query_string = urllib.parse.urlencode(params)
            signature = hmac.new(
                self.api_secret.encode("utf-8"),
                query_string.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            params["signature"] = signature

        query_string = urllib.parse.urlencode(params)
        headers = {
            "User-Agent": "BinanceFVGBot/1.0",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, identity"
        }
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key

        last_error = None
        for base in self.endpoints:
            url = f"{base}{path}"
            if method == "GET" and query_string:
                url = f"{url}?{query_string}"
                data = None
            else:
                data = query_string.encode("utf-8") if query_string else None

            for attempt in range(3):
                try:
                    req = urllib.request.Request(url, data=data, headers=headers, method=method)
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        raw_bytes = resp.read()
                        if resp.info().get("Content-Encoding") == "gzip" or (len(raw_bytes) >= 2 and raw_bytes[:2] == b"\x1f\x8b"):
                            raw_bytes = gzip.decompress(raw_bytes)
                        res_data = raw_bytes.decode("utf-8")
                        return json.loads(res_data)
                except urllib.error.HTTPError as e:
                    err_body = e.read()
                    if e.headers.get("Content-Encoding") == "gzip" or (len(err_body) >= 2 and err_body[:2] == b"\x1f\x8b"):
                        err_body = gzip.decompress(err_body)
                    err_str = err_body.decode("utf-8")
                    raise RuntimeError(f"Binance API HTTP {e.code} Error: {err_str}")
                except Exception as e:
                    last_error = e
                    time.sleep(0.3)

        raise RuntimeError(f"Binance API Network Error: {str(last_error)}")

    def get_exchange_info(self, symbols: Optional[List[str]] = None) -> Dict[str, SymbolSpecs]:
        """
        Dynamically retrieves exchange specifications (tick size, step size, minQty, minNotional, etc.)
        Section 2: Never hard-code Binance precision rules.
        """
        data = self._request("GET", "/fapi/v1/exchangeInfo")
        result: Dict[str, SymbolSpecs] = {}

        symbols_filter = set(symbols) if symbols else None

        for s in data.get("symbols", []):
            sym = s.get("symbol", "")
            if symbols_filter and sym not in symbols_filter:
                continue

            tick_size = 0.01
            step_size = 0.001
            min_qty = 0.001
            min_notional = 5.0

            for f in s.get("filters", []):
                ftype = f.get("filterType")
                if ftype == "PRICE_FILTER":
                    tick_size = float(f.get("tickSize", "0.01"))
                elif ftype == "LOT_SIZE":
                    step_size = float(f.get("stepSize", "0.001"))
                    min_qty = float(f.get("minQty", "0.001"))
                elif ftype in ("MIN_NOTIONAL", "NOTIONAL"):
                    min_notional = float(f.get("notional", f.get("minNotional", "5.0")))

            price_prec = int(s.get("pricePrecision", 2))
            qty_prec = int(s.get("quantityPrecision", 3))
            status = s.get("status", "TRADING")

            specs = SymbolSpecs(
                symbol=sym,
                tick_size=tick_size,
                step_size=step_size,
                price_precision=price_prec,
                qty_precision=qty_prec,
                min_qty=min_qty,
                min_notional=min_notional,
                max_leverage=50,
                status=status
            )
            result[sym] = specs
            self.specs_cache[sym] = specs

        return result

    def get_klines(self, symbol: str, interval: str, limit: int = 500, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Candle]:
        """
        Retrieves historical klines and converts to Candle dataclass list.
        """
        params = {"symbol": symbol, "interval": interval, "limit": min(1000, limit)}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        raw_klines = self._request("GET", "/fapi/v1/klines", params=params)
        candles: List[Candle] = []

        for k in raw_klines:
            # k: [0:open_time, 1:open, 2:high, 3:low, 4:close, 5:vol, 6:close_time, ...]
            candles.append(Candle(
                timestamp=int(k[0]),
                open=float(k[1]),
                high=float(k[2]),
                low=float(k[3]),
                close=float(k[4]),
                volume=float(k[5]),
                close_time=int(k[6])
            ))
        return candles

    def get_ticker_price(self, symbol: str) -> float:
        """Retrieves latest mark/last price for a symbol."""
        data = self._request("GET", "/fapi/v1/ticker/price", params={"symbol": symbol})
        return float(data.get("price", 0.0))

    def get_funding_rate(self, symbol: str) -> Tuple[float, int]:
        """Returns (lastFundingRate, nextFundingTime)."""
        data = self._request("GET", "/fapi/v1/premiumIndex", params={"symbol": symbol})
        rate = float(data.get("lastFundingRate", 0.0001))
        next_time = int(data.get("nextFundingTime", 0))
        return rate, next_time

    def set_leverage(self, symbol: str, leverage: int = 5) -> dict:
        """Sets leverage on Binance Futures."""
        return self._request("POST", "/fapi/v1/leverage", params={"symbol": symbol, "leverage": leverage}, signed=True)

    def get_account_balance(self) -> float:
        """Retrieves total wallet balance/equity in USDT."""
        data = self._request("GET", "/fapi/v2/balance", signed=True)
        for item in data:
            if item.get("asset") == "USDT":
                return float(item.get("balance", item.get("walletBalance", 0.0)))
        return 0.0

    def place_order(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        order_type: str,  # "LIMIT", "MARKET", "STOP_MARKET", "TAKE_PROFIT_MARKET"
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
        reduce_only: bool = False,
        close_position: bool = False,
        time_in_force: str = "GTC"
    ) -> dict:
        """Places a futures order with unique clientOrderId."""
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
        }
        if close_position and order_type.upper() in ("STOP_MARKET", "TAKE_PROFIT_MARKET"):
            params["closePosition"] = "true"
        elif quantity is not None:
            params["quantity"] = f"{quantity:f}".rstrip("0").rstrip(".")

        if price is not None and order_type.upper() == "LIMIT":
            params["price"] = f"{price:f}".rstrip("0").rstrip(".")
            params["timeInForce"] = time_in_force
        if stop_price is not None:
            params["stopPrice"] = f"{stop_price:f}".rstrip("0").rstrip(".")
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        if reduce_only and not close_position:
            params["reduceOnly"] = "true"

        return self._request("POST", "/fapi/v1/order", params=params, signed=True)

    def cancel_order(self, symbol: str, client_order_id: Optional[str] = None, order_id: Optional[int] = None) -> dict:
        """Cancels an active order."""
        params = {"symbol": symbol}
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        elif order_id:
            params["orderId"] = order_id
        return self._request("DELETE", "/fapi/v1/order", params=params, signed=True)

    def cancel_all_orders(self, symbol: str) -> dict:
        """Cancels all open orders for a symbol."""
        return self._request("DELETE", "/fapi/v1/allOpenOrders", params={"symbol": symbol}, signed=True)
