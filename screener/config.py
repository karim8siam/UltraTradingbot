import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.whitelist import FIXED_30_COINS, filter_allowed_symbols, is_symbol_allowed

# Strict 30 High-Liquidity USDT-M Futures Universe (1st coin: BTCUSDT)
# Excludes stablecoins, pegged assets, and low-cap illiquid tokens. No other coin accepted.
SYMBOLS = list(FIXED_30_COINS)

# Alternate symbol mappings for exchanges that use PEPEUSDT instead of 1000PEPEUSDT
ALT_SYMBOL_MAPPINGS = {
    "1000PEPEUSDT": "PEPEUSDT",
    "1000SHIBUSDT": "SHIBUSDT",
    "1000BONKUSDT": "BONKUSDT",
    "1000FLOKIUSDT": "FLOKIUSDT"
}

# Binance Public Data Mirror URLs (Zero API key needed for screener market data)
PUBLIC_DATA_URLS = [
    "https://fapi.binance.com/fapi/v1",
    "https://data-api.binance.vision/api/v3",
    "https://api3.binance.com/api/v3",
    "https://api1.binance.com/api/v3"
]

# Screener Performance Criteria
MIN_WIN_RATE = 0.50          # At least 50% historical win-rate in the last 24h
MIN_RR = 2.0                 # Target 1:2 Risk to Reward (TP = 2 * SL)
LOOKBACK_HOURS = 24          # Trailing 24-hour evaluation window (midnight to midnight)
MIN_SIGNALS_PER_COIN = 1     # Minimum valid trade setups generated in 24h

# Shared Output File Path
SHARED_DIR = os.getenv("SHARED_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared")))
ACTIVE_PAIRS_FILE = os.path.join(SHARED_DIR, "active_pairs.json")
AUDIT_LOG_FILE = os.path.join(SHARED_DIR, "daily_screener_audit.log")
