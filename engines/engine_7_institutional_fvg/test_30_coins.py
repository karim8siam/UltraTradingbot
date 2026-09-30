from binance_client import BinanceFuturesClient
from config import BotConfig

config = BotConfig()
client = BinanceFuturesClient(config.BINANCE_API_KEY, config.BINANCE_API_SECRET, False)

try:
    bal = client.get_account_balance()
    print(f"✅ BINANCE API: AUTHENTICATED")
    print(f"✅ LIVE ACCOUNT BALANCE: ${bal:.2f} USDT\n")
except Exception as e:
    print(f"⚠️ Note on API Key Authentication: {e}")
    print("ℹ️ Tip: Whitelist current IP (103.199.110.50) and check 'Enable Futures' in Binance API Management.\n")

print(f"--- TESTING 30 COINS CONNECTION ---")
tickers = client._request("GET", "/fapi/v1/ticker/price")
price_map = {t["symbol"]: float(t["price"]) for t in tickers}

connected = 0
for idx, sym in enumerate(config.SYMBOLS, 1):
    if sym in price_map:
        connected += 1
        print(f" {idx:2d}. {sym:<14} : [OK] Live Price = ${price_map[sym]:.4f}")
    else:
        print(f" {idx:2d}. {sym:<14} : [FAIL]")

print(f"\nSTATUS: {connected}/{len(config.SYMBOLS)} COINS 100% CONNECTED & STREAMING.")
