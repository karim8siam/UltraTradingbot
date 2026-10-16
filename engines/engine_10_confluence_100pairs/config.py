import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Import fixed 30-coin whitelist
try:
    from shared.whitelist import FIXED_30_COINS, filter_allowed_symbols, is_symbol_allowed
except ImportError:
    _shared_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _shared_dir not in sys.path:
        sys.path.insert(0, _shared_dir)
    from shared.whitelist import FIXED_30_COINS, filter_allowed_symbols, is_symbol_allowed

API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Fixed 30 Binance USDT-M Futures Cryptocurrencies & Specifications (1st: BTCUSDT)
SYMBOL_SPECS = {
    'BTCUSDT': {'price_prec': 2, 'qty_prec': 3, 'min_qty': 0.001},
    'ETHUSDT': {'price_prec': 2, 'qty_prec': 3, 'min_qty': 0.001},
    'SOLUSDT': {'price_prec': 4, 'qty_prec': 2, 'min_qty': 0.01},
    'BNBUSDT': {'price_prec': 3, 'qty_prec': 2, 'min_qty': 0.01},
    'XRPUSDT': {'price_prec': 4, 'qty_prec': 1, 'min_qty': 0.1},
    'DOGEUSDT': {'price_prec': 6, 'qty_prec': 0, 'min_qty': 1.0},
    'ADAUSDT': {'price_prec': 5, 'qty_prec': 0, 'min_qty': 1.0},
    'SUIUSDT': {'price_prec': 6, 'qty_prec': 1, 'min_qty': 0.1},
    'AVAXUSDT': {'price_prec': 4, 'qty_prec': 0, 'min_qty': 1.0},
    'LINKUSDT': {'price_prec': 3, 'qty_prec': 2, 'min_qty': 0.01},
    'NEARUSDT': {'price_prec': 4, 'qty_prec': 0, 'min_qty': 1.0},
    'APTUSDT': {'price_prec': 5, 'qty_prec': 1, 'min_qty': 0.1},
    'LTCUSDT': {'price_prec': 2, 'qty_prec': 3, 'min_qty': 0.001},
    'BCHUSDT': {'price_prec': 2, 'qty_prec': 3, 'min_qty': 0.001},
    'DOTUSDT': {'price_prec': 6, 'qty_prec': 1, 'min_qty': 0.1},
    'UNIUSDT': {'price_prec': 4, 'qty_prec': 0, 'min_qty': 1.0},
    'FETUSDT': {'price_prec': 7, 'qty_prec': 0, 'min_qty': 1.0},
    'TAOUSDT': {'price_prec': 2, 'qty_prec': 3, 'min_qty': 0.001},
    'ARBUSDT': {'price_prec': 6, 'qty_prec': 1, 'min_qty': 0.1},
    'INJUSDT': {'price_prec': 6, 'qty_prec': 1, 'min_qty': 0.1},
    'ONDOUSDT': {'price_prec': 7, 'qty_prec': 1, 'min_qty': 0.1},
    'ENAUSDT': {'price_prec': 7, 'qty_prec': 0, 'min_qty': 1.0},
    'WLDUSDT': {'price_prec': 7, 'qty_prec': 0, 'min_qty': 1.0},
    'AAVEUSDT': {'price_prec': 3, 'qty_prec': 1, 'min_qty': 0.1},
    'XLMUSDT': {'price_prec': 5, 'qty_prec': 0, 'min_qty': 1.0},
    'ICPUSDT': {'price_prec': 6, 'qty_prec': 0, 'min_qty': 1.0},
    'HBARUSDT': {'price_prec': 5, 'qty_prec': 0, 'min_qty': 1.0},
    'TIAUSDT': {'price_prec': 7, 'qty_prec': 0, 'min_qty': 1.0},
    'FILUSDT': {'price_prec': 6, 'qty_prec': 1, 'min_qty': 0.1},
    'OPUSDT': {'price_prec': 7, 'qty_prec': 1, 'min_qty': 0.1}
}

def load_dynamic_symbols(engine_key: str, default_symbols):
    import json
    shared_active = os.getenv("ACTIVE_PAIRS_FILE", "/app/shared/active_pairs.json")
    if not os.path.exists(shared_active):
        shared_active = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "shared", "active_pairs.json"))
    if os.path.exists(shared_active):
        try:
            with open(shared_active, "r") as f:
                pair_data = json.load(f)
                alloc = pair_data.get("engine_allocations", {}).get(engine_key)
                if alloc:
                    return filter_allowed_symbols(alloc)
        except Exception:
            pass
    return filter_allowed_symbols(default_symbols)

SYMBOLS = load_dynamic_symbols("engine_10_confluence_100pairs", list(FIXED_30_COINS))

# Timeframes
TIMEFRAME_PRIMARY = "5m"
TIMEFRAME_SECONDARY = "15m"
TIMEFRAME_MACRO = "1h"

# Leverage & Risk Settings
LEVERAGE = 5
MARGIN_TYPE = "ISOLATED"
RISK_PERCENT = 0.01      # 1% of total wallet balance
MIN_NOTIONAL_USDT = 5.5  # Binance minimum order size guard

# Engine Thresholds (Strict 10/10 Confluence, No Trade Count Limit)
SCORE_TRIGGER = 10       # Must score 10.0 out of 10 Points (100% Confluence)
MAX_OPEN_POSITIONS = 30  # Maximum open positions across the 30 pairs
SCAN_INTERVAL = 15       # Scan cycle every 15 seconds

# ATR Bracket Multipliers (1:2 Risk to Reward)
SL_ATR_MULT = 0.60       # Stop Loss = 0.60 * ATR
TP_ATR_MULT = 1.20       # Take Profit = 1.20 * ATR (1:2 R:R)
