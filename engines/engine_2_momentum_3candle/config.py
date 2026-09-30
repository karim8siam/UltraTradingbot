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
HOLD_MINUTES = 30  # Hold for 30 minutes (2 candles)
LEVERAGE = 5
MARGIN_FRACTION = 0.001  # 0.1% of total balance per trade
MAX_CONCURRENT_TRADES = 4

# Top 25 High-Liquidity USDT-M Futures Pairs
SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "TRXUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "SUIUSDT",
    "NEARUSDT",
    "APTUSDT",
    "DOTUSDT",
    "LTCUSDT",
    "BCHUSDT",
    "PEPEUSDT",
    "SHIBUSDT",
    "UNIUSDT",
    "FETUSDT",
    "TAOUSDT",
    "OPUSDT",
    "ARBUSDT",
    "INJUSDT",
    "TIAUSDT",
]

# Candle Health & Quality Filters
# Body must be at least 50% of the entire candle (High - Low)
MIN_BODY_RATIO = 0.50

# Maximum wick against the direction (e.g. upper wick for green candle, lower wick for red candle)
MAX_OPPOSITE_WICK_RATIO = 0.35

# Minimum range to avoid zero-volatility flat candles
MIN_CANDLE_RANGE_PCT = 0.0003
