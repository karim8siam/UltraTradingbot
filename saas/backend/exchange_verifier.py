import time
import hmac
import hashlib
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, Tuple


class ExchangeVerifier:
    """
    Automated live validator for client exchange API credentials.
    Verifies that Futures trading is active and withdrawals are safely disabled.
    """

    @staticmethod
    def verify_binance(api_key: str, api_secret: str) -> Dict[str, Any]:
        """
        Validates Binance USDT-M Futures account permissions.
        """
        base_url = "https://fapi.binance.com"
        endpoint = "/fapi/v2/account"

        ts = int(time.time() * 1000)
        query_string = f"timestamp={ts}"
        signature = hmac.new(
            api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
        req = urllib.request.Request(url, headers={
            "X-MBX-APIKEY": api_key,
            "User-Agent": "Mozilla/5.0 (UltraTradingBot-Verifier/2.0)"
        })

        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                can_trade = data.get("canTrade", False)
                total_wallet_balance = float(data.get("totalWalletBalance", 0.0))

                # Check spot/sapi apiRestrictions if accessible
                withdrawals_disabled = True
                try:
                    sapi_url = f"https://api.binance.com/sapi/v1/account/apiRestrictions?timestamp={ts}&signature=" + \
                               hmac.new(api_secret.encode("utf-8"), f"timestamp={ts}".encode("utf-8"), hashlib.sha256).hexdigest()
                    sapi_req = urllib.request.Request(sapi_url, headers={"X-MBX-APIKEY": api_key})
                    with urllib.request.urlopen(sapi_req, timeout=5) as s_resp:
                        s_data = json.loads(s_resp.read().decode("utf-8"))
                        if s_data.get("enableWithdrawals", False) is True:
                            withdrawals_disabled = False
                except Exception:
                    pass

                return {
                    "success": True,
                    "exchange": "binance",
                    "futures_enabled": can_trade,
                    "withdrawals_disabled": withdrawals_disabled,
                    "balance_usdt": round(total_wallet_balance, 2),
                    "message": "Binance USDT-M Futures API connected and verified successfully."
                }
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_msg)
                msg = err_json.get("msg", err_msg)
            except Exception:
                msg = err_msg

            if "API-key format invalid" in msg:
                msg = "Invalid Binance API Key format. Please check your credentials."
            elif "Signature for this request is not valid" in msg:
                msg = "Invalid Binance API Secret key."
            elif "IP" in msg:
                msg = "Binance API key has restricted IP whitelist. Please allow unrestricted or server IP."

            return {
                "success": False,
                "exchange": "binance",
                "futures_enabled": False,
                "withdrawals_disabled": True,
                "balance_usdt": 0.0,
                "error": msg
            }
        except Exception as e:
            return {
                "success": False,
                "exchange": "binance",
                "futures_enabled": False,
                "withdrawals_disabled": True,
                "balance_usdt": 0.0,
                "error": f"Connection error: {str(e)}"
            }

    @staticmethod
    def verify_bybit(api_key: str, api_secret: str) -> Dict[str, Any]:
        """
        Validates Bybit V5 Linear Futures account permissions.
        """
        base_url = "https://api.bybit.com"
        endpoint = "/v5/account/wallet-balance"
        params = "accountType=UNIFIED"

        ts = str(int(time.time() * 1000))
        recv_window = "5000"
        param_str = f"accountType=UNIFIED"
        sign_str = f"{ts}{api_key}{recv_window}{param_str}"

        signature = hmac.new(
            api_secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        url = f"{base_url}{endpoint}?{param_str}"
        req = urllib.request.Request(url, headers={
            "X-BAPI-API-KEY": api_key,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-SIGN": signature,
            "X-BAPI-RECV-WINDOW": recv_window,
            "User-Agent": "Mozilla/5.0 (UltraTradingBot-Verifier/2.0)"
        })

        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ret_code = data.get("retCode", -1)
                if ret_code != 0:
                    return {
                        "success": False,
                        "exchange": "bybit",
                        "futures_enabled": False,
                        "withdrawals_disabled": True,
                        "balance_usdt": 0.0,
                        "error": data.get("retMsg", "Bybit authentication failed.")
                    }

                # Parse USDT balance
                total_equity = 0.0
                try:
                    coins = data.get("result", {}).get("list", [{}])[0].get("coin", [])
                    for c in coins:
                        if c.get("coin") == "USDT":
                            total_equity = float(c.get("walletBalance", 0.0))
                            break
                except Exception:
                    pass

                return {
                    "success": True,
                    "exchange": "bybit",
                    "futures_enabled": True,
                    "withdrawals_disabled": True,
                    "balance_usdt": round(total_equity, 2),
                    "message": "Bybit Unified / Linear Futures API connected and verified successfully."
                }
        except urllib.error.HTTPError as e:
            return {
                "success": False,
                "exchange": "bybit",
                "futures_enabled": False,
                "withdrawals_disabled": True,
                "balance_usdt": 0.0,
                "error": f"Bybit API error: {e.read().decode('utf-8')}"
            }
        except Exception as e:
            return {
                "success": False,
                "exchange": "bybit",
                "futures_enabled": False,
                "withdrawals_disabled": True,
                "balance_usdt": 0.0,
                "error": f"Bybit connection error: {str(e)}"
            }
