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

# Binance API Credentials
API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# Network & Base URLs
BASE_URL = os.getenv("BINANCE_FUTURES_URL", "https://fapi.binance.com")
PUBLIC_DATA_URLS = [
    "https://data-api.binance.vision/api/v3",
    "https://api3.binance.com/api/v3",
    "https://api1.binance.com/api/v3",
    "https://api.binance.com/api/v3"
]

# Engine Execution Parameters
TIMEFRAME = os.getenv("TIMEFRAME", "30m")  # Recommended: 30m or 15m
MAX_HOLD_CANDLES = int(os.getenv("MAX_HOLD_CANDLES", "8"))  # Auto market close after 8 candles
MIN_SCORE = float(os.getenv("MIN_SCORE", "8.0"))  # >= 8.0 out of 10 points (80% confluence)

# Risk & Leverage Management
LEVERAGE = int(os.getenv("LEVERAGE", "5"))  # 5x Isolated Leverage
MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", "0.01"))  # 1.0% of account equity
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "4"))
FEE_RATE = float(os.getenv("FEE_RATE", "0.0005"))  # 0.05% taker fee per side

# ATR Stop-Loss and Take-Profit Settings (1:2 Risk to Reward)
ATR_PERIOD = 14
ATR_SL_MULT = float(os.getenv("ATR_SL_MULT", "1.55"))  # SL = Entry - (1.55 * ATR)
ATR_TP_MULT = float(os.getenv("ATR_TP_MULT", "3.10"))  # TP = Entry + (3.10 * ATR) -> 1:2 R:R

# Top 30 High-Liquidity Crypto USDT Pairs (Stablecoins & Pegged Tokens Excluded)
SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "SUIUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "NEARUSDT",
    "APTUSDT",
    "LTCUSDT",
    "PEPEUSDT",
    "UNIUSDT",
    "FETUSDT",
    "TAOUSDT",
    "ARBUSDT",
    "INJUSDT",
    "ZECUSDT",
    "ONDOUSDT",
    "ENAUSDT",
    "0GUSDT",
    "QNTUSDT",
    "WLDUSDT",
    "AAVEUSDT",
    "XLMUSDT",
    "ICPUSDT",
    "HBARUSDT",
    "PUMPUSDT",
]
