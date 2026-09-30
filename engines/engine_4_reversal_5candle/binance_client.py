import time
import hmac
import hashlib
import json
import urllib.parse
import urllib.request
import ssl
from typing import Dict, Any, List, Optional
import config

class BinanceFuturesClient:
    def __init__(self, api_key: str = config.API_KEY, api_secret: str = config.API_SECRET, base_url: str = config.BASE_URL):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.exchange_info_cache = {}
        self.ssl_context = ssl.create_default_context()
        self.time_offset = 0
        self.sync_time_offset()

    def sync_time_offset(self):
        """Synchronize local clock offset with Binance server time."""
        try:
            req = urllib.request.Request(f"{self.base_url}/fapi/v1/time", headers={"User-Agent": "BinanceFuturesBot/1.0"})
            with urllib.request.urlopen(req, context=self.ssl_context, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                server_time = data.get("serverTime")
                if server_time:
                    local_time = int(time.time() * 1000)
                    self.time_offset = server_time - local_time
                    print(f"[TIME SYNC] Synced with Binance server. Offset: {self.time_offset}ms")
        except Exception as e:
            print(f"[WARN] Failed to sync time offset: {e}")

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000) + self.time_offset

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params["timestamp"] = self._get_timestamp()
        params["recvWindow"] = 30000
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, retries: int = 3) -> Any:
        if params is None:
            params = {}
        
        headers = {
            "X-MBX-APIKEY": self.api_key,
            "User-Agent": "BinanceFuturesBot/1.0",
        }

        query_str = urllib.parse.urlencode(params)
        url = f"{self.base_url}{path}"
        data = None

        if method == "GET":
            if query_str:
                url = f"{url}?{query_str}"
        elif method == "POST":
            data = query_str.encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        last_error = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(req, context=self.ssl_context, timeout=15) as response:
                    body = response.read().decode("utf-8")
                    return json.loads(body)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8")
                try:
                    data_err = json.loads(err_body)
                    if data_err.get("code") == -1021:
                        self.sync_time_offset()
                        if params and "signature" in params:
                            params = self._sign({k: v for k, v in params.items() if k not in ["timestamp", "signature", "recvWindow"]})
                            query_str = urllib.parse.urlencode(params)
                            if method == "GET":
                                url = f"{self.base_url}{path}?{query_str}"
                            elif method == "POST":
                                data = query_str.encode("utf-8")
                    return data_err
                except Exception:
                    return {"error": err_body, "status": e.code}
            except Exception as e:
                last_error = str(e)
                time.sleep(0.5 * (attempt + 1))
        
        return {"error": last_error}

    def get_server_time(self) -> Optional[int]:
        res = self._request("GET", "/fapi/v1/time")
        if isinstance(res, dict) and "serverTime" in res:
            return res["serverTime"]
        print(f"[ERROR] Failed to get server time: {res}")
        return None

    def get_usdt_balance(self) -> float:
        """Fetch total available USDT balance in Futures account."""
        params = self._sign({})
        res = self._request("GET", "/fapi/v2/account", params)
        if isinstance(res, dict) and "assets" in res:
            for asset in res["assets"]:
                if asset["asset"] == "USDT":
                    return float(asset.get("walletBalance", 0.0))
        else:
            print(f"[ERROR] Balance fetch failed: {res}")
        return 0.0

    def get_symbol_rules(self, symbol: str) -> Dict[str, Any]:
        """Fetch symbol precision, stepSize, minQty, minNotional."""
        if symbol in self.exchange_info_cache:
            return self.exchange_info_cache[symbol]

        res = self._request("GET", "/fapi/v1/exchangeInfo")
        if isinstance(res, dict) and "symbols" in res:
            for s in res["symbols"]:
                sym = s["symbol"]
                step_size = 0.001
                min_qty = 0.001
                min_notional = 5.0
                price_precision = s.get("pricePrecision", 2)
                quantity_precision = s.get("quantityPrecision", 3)

                for f in s.get("filters", []):
                    if f["filterType"] == "LOT_SIZE":
                        step_size = float(f["stepSize"])
                        min_qty = float(f["minQty"])
                    elif f["filterType"] == "MIN_NOTIONAL":
                        min_notional = float(f.get("notional", 5.0))

                self.exchange_info_cache[sym] = {
                    "step_size": step_size,
                    "min_qty": min_qty,
                    "min_notional": min_notional,
                    "price_precision": price_precision,
                    "quantity_precision": quantity_precision,
                }
            return self.exchange_info_cache.get(symbol, {
                "step_size": 0.001,
                "min_qty": 0.001,
                "min_notional": 5.0,
                "quantity_precision": 3,
            })

        return {
            "step_size": 0.001,
            "min_qty": 0.001,
            "min_notional": 5.0,
            "quantity_precision": 3,
        }

    def set_leverage(self, symbol: str, leverage: int = 5) -> bool:
        """Set leverage for symbol."""
        params = self._sign({
            "symbol": symbol,
            "leverage": leverage
        })
        res = self._request("POST", "/fapi/v1/leverage", params)
        if isinstance(res, dict) and res.get("leverage") == leverage:
            return True
        print(f"[WARN] Setting leverage on {symbol}: {res}")
        return False

    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED") -> bool:
        """Set margin type (ISOLATED or CROSSED)."""
        params = self._sign({
            "symbol": symbol,
            "marginType": margin_type
        })
        res = self._request("POST", "/fapi/v1/marginType", params)
        if isinstance(res, dict) and (res.get("code") == 200 or "code" not in res or res.get("code") == -4046):
            # -4046 means "No need to change margin type" (already isolated)
            return True
        return False

    def get_klines(self, symbol: str, interval: str = "15m", limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch historical klines.
        Returns list of candle dicts: open_time, open, high, low, close, volume, is_closed.
        """
        res = self._request("GET", "/fapi/v1/klines", {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        })
        if isinstance(res, list):
            klines = []
            for k in res:
                klines.append({
                    "open_time": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "close_time": int(k[6]),
                })
            return klines
        print(f"[ERROR] Exception fetching klines for {symbol}: {res}")
        return []

    def get_current_price(self, symbol: str) -> float:
        res = self._request("GET", "/fapi/v1/ticker/price", {"symbol": symbol})
        if isinstance(res, dict) and "price" in res:
            return float(res["price"])
        print(f"[ERROR] Failed to get price for {symbol}: {res}")
        return 0.0

    def get_active_positions(self) -> List[Dict[str, Any]]:
        """Returns list of open positions with non-zero positionAmt."""
        params = self._sign({})
        res = self._request("GET", "/fapi/v2/positionRisk", params)
        active = []
        if isinstance(res, list):
            for pos in res:
                amt = float(pos.get("positionAmt", 0.0))
                if abs(amt) > 0.0:
                    active.append({
                        "symbol": pos["symbol"],
                        "positionAmt": amt,
                        "entryPrice": float(pos.get("entryPrice", 0.0)),
                        "unrealizedProfit": float(pos.get("unRealizedProfit", 0.0)),
                        "side": "LONG" if amt > 0 else "SHORT",
                    })
        elif isinstance(res, dict):
            print(f"[ERROR] Failed positionRisk: {res}")
        return active

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Optional[Dict[str, Any]]:
        """Place Market Order (side: BUY or SELL)."""
        params = self._sign({
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity
        })
        res = self._request("POST", "/fapi/v1/order", params)
        if isinstance(res, dict) and "orderId" in res:
            return res
        print(f"[ERROR] Place order failed for {symbol}: {res}")
        return None

    def close_market_position(self, symbol: str, side: str, quantity: float) -> Optional[Dict[str, Any]]:
        """
        Close an existing position using a reduceOnly market order.
        If current position is LONG, side must be SELL. If SHORT, side must be BUY.
        """
        params = self._sign({
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": abs(quantity),
            "reduceOnly": "true"
        })
        res = self._request("POST", "/fapi/v1/order", params)
        if isinstance(res, dict) and "orderId" in res:
            return res
        print(f"[ERROR] Close position failed for {symbol}: {res}")
        return None
