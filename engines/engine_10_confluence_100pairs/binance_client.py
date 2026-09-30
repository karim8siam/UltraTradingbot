import time
import hmac
import hashlib
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import config

class BinanceFuturesClient:
    def __init__(self):
        self.api_key = config.API_KEY
        self.secret_key = config.API_SECRET
        self.base_url = "https://fapi.binance.com"
        self.headers = {"X-MBX-APIKEY": self.api_key}
        
        self.session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.2, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=retries)
        self.session.mount("https://", adapter)

    def _sign(self, params: dict) -> str:
        params["timestamp"] = int(time.time() * 1000)
        query = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        sig = hmac.new(self.secret_key.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{query}&signature={sig}"

    def get_usdt_balance(self) -> float:
        """Fetches live USDT balance in Futures Wallet"""
        try:
            params = {}
            signed_query = self._sign(params)
            url = f"{self.base_url}/fapi/v2/balance?{signed_query}"
            r = self.session.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                for asset in data:
                    if asset.get("asset") == "USDT":
                        return float(asset.get("balance", 0.0))
            return 0.0
        except Exception:
            return 0.0

    def get_open_positions(self) -> dict:
        """Returns active open positions dict: {symbol: position_info}"""
        try:
            params = {}
            signed_query = self._sign(params)
            url = f"{self.base_url}/fapi/v2/positionRisk?{signed_query}"
            r = self.session.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                positions = r.json()
                open_pos = {}
                for pos in positions:
                    amt = float(pos.get("positionAmt", 0.0))
                    if amt != 0.0:
                        symbol = pos.get("symbol")
                        side = "LONG" if amt > 0 else "SHORT"
                        entry_price = float(pos.get("entryPrice", 0.0))
                        unrealized_pnl = float(pos.get("unRealizedProfit", 0.0))
                        notional = abs(float(pos.get("notional", 0.0)))
                        percentage = (unrealized_pnl / (notional / config.LEVERAGE + 1e-10)) * 100
                        open_pos[symbol] = {
                            "symbol": symbol,
                            "side": side,
                            "contracts": abs(amt),
                            "notional": notional,
                            "entry_price": entry_price,
                            "unrealized_pnl": unrealized_pnl,
                            "percentage": percentage,
                        }
                return open_pos
            return {}
        except Exception:
            return {}

    def fetch_klines(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> pd.DataFrame:
        try:
            url = f"{self.base_url}/fapi/v1/klines?symbol={symbol}&interval={timeframe}&limit={limit}"
            r = self.session.get(url, timeout=10)
            if r.status_code == 200:
                raw = r.json()
                data = [[row[0], float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])] for row in raw]
                df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                return df
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def fetch_book_ticker(self, symbol: str) -> dict:
        try:
            url = f"{self.base_url}/fapi/v1/ticker/bookTicker?symbol={symbol}"
            r = self.session.get(url, timeout=5)
            if r.status_code == 200:
                return r.json()
            return {}
        except Exception:
            return {}

    def set_symbol_leverage(self, symbol: str, leverage: int = 5):
        try:
            params = {"symbol": symbol, "leverage": leverage}
            signed_query = self._sign(params)
            url = f"{self.base_url}/fapi/v1/leverage?{signed_query}"
            self.session.post(url, headers=self.headers, timeout=10)
        except Exception:
            pass

    def calculate_order_amount(self, symbol: str, current_price: float, balance: float) -> float:
        spec = config.SYMBOL_SPECS.get(symbol, {"price_prec": 2, "qty_prec": 1, "min_qty": 0.1})
        
        margin_budget = max(balance * config.RISK_PERCENT, 1.0)
        notional_value = margin_budget * config.LEVERAGE
        notional_value = max(notional_value, config.MIN_NOTIONAL_USDT)
        
        raw_amount = notional_value / current_price
        qty_prec = spec["qty_prec"]
        
        if qty_prec == 0:
            amount = float(int(raw_amount))
        else:
            amount = round(raw_amount, qty_prec)
            
        min_qty = spec["min_qty"]
        return max(amount, min_qty)

    def close_position_market(self, symbol: str, side: str, amount: float):
        """Closes an active position via market order (for Max Hold Timeout)"""
        close_side = "SELL" if side == "LONG" else "BUY"
        try:
            params = {
                "symbol": symbol,
                "side": close_side,
                "type": "MARKET",
                "quantity": amount,
                "reduceOnly": "true"
            }
            query = self._sign(params)
            r = self.session.post(f"{self.base_url}/fapi/v1/order?{query}", headers=self.headers, timeout=10)
            return r.json()
        except Exception:
            return None

    def place_market_entry_with_sl_tp(self, symbol: str, side: str, amount: float, entry_price: float, sl_price: float, tp_price: float):
        spec = config.SYMBOL_SPECS.get(symbol, {"price_prec": 2, "qty_prec": 1, "min_qty": 0.1})
        price_prec = spec["price_prec"]
        
        self.set_symbol_leverage(symbol, config.LEVERAGE)
        
        entry_side = "BUY" if side == "LONG" else "SELL"
        close_side = "SELL" if side == "LONG" else "BUY"
        
        try:
            # 1. Market Entry Order
            print(f"[*] Submitting {side} Market Order for {amount} {symbol}...")
            entry_params = {
                "symbol": symbol,
                "side": entry_side,
                "type": "MARKET",
                "quantity": amount
            }
            query = self._sign(entry_params)
            r = self.session.post(f"{self.base_url}/fapi/v1/order?{query}", headers=self.headers, timeout=10)
            entry_res = r.json()
            
            if r.status_code != 200:
                print(f"[!] Market Entry Rejected: {entry_res}")
                return None
                
            print(f"[+] ✅ Market Entry Filled: ID {entry_res.get(orderId)}")
            time.sleep(0.3)
            
            # 2. Native Binance Stop-Loss Order (Server-Side @ 0.55x ATR)
            sl_rounded = round(sl_price, price_prec)
            sl_params = {
                "symbol": symbol,
                "side": close_side,
                "type": "STOP_MARKET",
                "stopPrice": sl_rounded,
                "closePosition": "true"
            }
            sl_query = self._sign(sl_params)
            r_sl = self.session.post(f"{self.base_url}/fapi/v1/order?{sl_query}", headers=self.headers, timeout=10)
            if r_sl.status_code == 200:
                print(f"[+] 🛡️ Server-Side Stop Loss set at {sl_rounded} (0.55x ATR)")
            else:
                print(f"[!] Warning setting Stop Loss: {r_sl.json()}")

            # 3. Native Binance Take-Profit Order (Server-Side @ 0.55x ATR)
            tp_rounded = round(tp_price, price_prec)
            tp_params = {
                "symbol": symbol,
                "side": close_side,
                "type": "TAKE_PROFIT_MARKET",
                "stopPrice": tp_rounded,
                "closePosition": "true"
            }
            tp_query = self._sign(tp_params)
            r_tp = self.session.post(f"{self.base_url}/fapi/v1/order?{tp_query}", headers=self.headers, timeout=10)
            if r_tp.status_code == 200:
                print(f"[+] 🎯 Server-Side Take Profit set at {tp_rounded} (0.55x ATR)")
            else:
                print(f"[!] Warning setting Take Profit: {r_tp.json()}")
                
            return entry_res
        except Exception as e:
            print(f"[!] Execution exception on {symbol}: {e}")
            return None
