import time
import json
import hmac
import hashlib
import urllib.request
import urllib.parse
from config import API_KEY, API_SECRET, BASE_URL, PUBLIC_DATA_URLS, DRY_RUN, LEVERAGE

class BinanceClient:
    def __init__(self, api_key=API_KEY, api_secret=API_SECRET, dry_run=DRY_RUN):
        self.api_key = api_key
        self.api_secret = api_secret
        self.dry_run = dry_run
        self.base_url = BASE_URL
        self.mock_balance = 10000.0  # Default paper trading capital

    def fetch_klines(self, symbol, interval="30m", limit=1000):
        """
        Fetches candlestick data with automatic mirror fallback.
        """
        path = f"/klines?symbol={symbol}&interval={interval}&limit={limit}"
        for base in PUBLIC_DATA_URLS:
            try:
                url = f"{base}{path}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw = json.loads(resp.read().decode('utf-8'))
                    candles = []
                    for k in raw:
                        candles.append({
                            'time': int(k[0]),
                            'open': float(k[1]),
                            'high': float(k[2]),
                            'low': float(k[3]),
                            'close': float(k[4]),
                            'volume': float(k[5]),
                            'quote_vol': float(k[7])
                        })
                    return candles
            except Exception:
                continue
        return None

    def _sign(self, params):
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"{query_string}&signature={signature}"

    def _request(self, method, endpoint, params=None):
        if params is None:
            params = {}
        params['timestamp'] = int(time.time() * 1000)
        signed_query = self._sign(params)

        if method == "GET":
            url = f"{self.base_url}{endpoint}?{signed_query}"
            data = None
        else:
            url = f"{self.base_url}{endpoint}"
            data = signed_query.encode('utf-8')

        headers = {
            'X-MBX-APIKEY': self.api_key,
            'User-Agent': 'Mozilla/5.0'
        }

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def get_account_balance(self):
        if self.dry_run or not self.api_key or not self.api_secret:
            return self.mock_balance
        try:
            res = self._request("GET", "/fapi/v2/account")
            for asset in res.get("assets", []):
                if asset.get("asset") == "USDT":
                    return float(asset.get("availableBalance", 0.0))
            return 0.0
        except Exception as e:
            print(f"[BinanceClient] Error fetching balance: {e}")
            return self.mock_balance

    def set_leverage(self, symbol, leverage=LEVERAGE):
        if self.dry_run or not self.api_key:
            return True
        try:
            self._request("POST", "/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})
            return True
        except Exception as e:
            print(f"[BinanceClient] Warning setting leverage on {symbol}: {e}")
            return False

    def place_market_order(self, symbol, side, quantity):
        if self.dry_run:
            print(f"[PAPER TRADING] Executing MARKET {side} on {symbol} | Qty: {quantity}")
            return {"orderId": int(time.time() * 1000), "status": "FILLED", "symbol": symbol, "side": side}

        try:
            params = {
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                "quantity": quantity
            }
            return self._request("POST", "/fapi/v1/order", params)
        except Exception as e:
            print(f"[BinanceClient] Error executing {side} order on {symbol}: {e}")
            return None

    def place_sl_tp_orders(self, symbol, pos_side, quantity, sl_price, tp_price):
        if self.dry_run:
            print(f"[PAPER TRADING] Placed SL @ {sl_price:.4f} and TP @ {tp_price:.4f} for {symbol}")
            return True

        close_side = "SELL" if pos_side == "LONG" else "BUY"
        try:
            # Server-Side Stop Loss
            self._request("POST", "/fapi/v1/order", {
                "symbol": symbol,
                "side": close_side,
                "type": "STOP_MARKET",
                "stopPrice": round(sl_price, 4),
                "closePosition": "true"
            })

            # Server-Side Take Profit
            self._request("POST", "/fapi/v1/order", {
                "symbol": symbol,
                "side": close_side,
                "type": "TAKE_PROFIT_MARKET",
                "stopPrice": round(tp_price, 4),
                "closePosition": "true"
            })
            return True
        except Exception as e:
            print(f"[BinanceClient] Error placing SL/TP on {symbol}: {e}")
            return False
