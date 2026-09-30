import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

# API Configuration
API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# Futures API Base URL
BASE_URL = "https://fapi.binance.com"

# Strategy Settings
TIMEFRAME = "15m"
HOLD_MINUTES = 45  # Exact 3 candles (45 minutes time-based exit)
LEVERAGE = 5       # 5x ISOLATED Leverage (20% Safe Buffer)
MARGIN_FRACTION = 0.001  # Exact 0.1% risk of total capital per trade
MAX_CONCURRENT_TRADES = 3

# Top 25 Verified High Win-Rate Pairs (>= 55% Historical Win Rate)
SYMBOLS = [
    "LTCUSDT",
    "ZKPUSDT",
    "ETHUSDT",
    "WIFUSDT",
    "UNIUSDT",
    "ZENUSDT",
    "NVDAUSDT",
    "ZKUSDT",
    "ADAUSDT",
    "CRCLUSDT",
    "BICOUSDT",
    "SOLUSDT",
    "XAGUSDT",
    "1000PEPEUSDT",
    "FETUSDT",
    "XAUUSDT",
    "ARBUSDT",
    "BZUSDT",
    "APTUSDT",
    "WLFIUSDT",
    "TRXUSDT",
    "DOGEUSDT",
    "1000SHIBUSDT",
    "CAKEUSDT",
    "HYPEUSDT",
]

# Indicator & Exhaustion Filters
RSI_PERIOD = 14
RSI_OVERBOUGHT = 65.0
RSI_OVERSOLD = 35.0

# Candle Health & Quality Filters
# Body must be at least 30% of total range (Dojis and messy long-wick pins are skipped)
MIN_BODY_RATIO = 0.30
MIN_CANDLE_RANGE_PCT = 0.0005
