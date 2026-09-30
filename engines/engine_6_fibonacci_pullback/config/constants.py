"""
Trading Bot Constants & Default Configuration Parameters
Based on Version 1 Specification
"""

# Supported Top 30 Trading Pairs
DEFAULT_SYMBOLS = [
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
    "TRXUSDT",
    "NEARUSDT",
    "PEPEUSDT",
    "ENAUSDT",
    "SHIBUSDT",
    "LTCUSDT",
    "BCHUSDT",
    "DOTUSDT",
    "UNIUSDT",
    "APTUSDT",
    "WLDUSDT",
    "TAOUSDT",
    "FETUSDT",
    "RENDERUSDT",
    "OPUSDT",
    "ARBUSDT",
    "FILUSDT",
    "INJUSDT",
    "AAVEUSDT",
    "CRVUSDT",
]

# Timeframes
TIMEFRAME_MAJOR_TREND = "4h"
TIMEFRAME_TRADING_TREND = "1h"
TIMEFRAME_IMPULSE = "15m"
TIMEFRAME_CONFIRMATION = "5m"

TIMEFRAMES = [
    TIMEFRAME_MAJOR_TREND,
    TIMEFRAME_TRADING_TREND,
    TIMEFRAME_IMPULSE,
    TIMEFRAME_CONFIRMATION,
]

# Minimum Candle Counts for Backtesting / Strategy Initialization
MIN_CANDLES = {
    "4h": 500,
    "1h": 1000,
    "15m": 2000,
    "5m": 3000,
}

# Market Structure & Swing Detection
SWING_LENGTH = 2

# Impulse Detection
IMPULSE_MIN_ATR = 2.0
ATR_PERIOD = 14
ATR_AVG_PERIOD = 50
MAX_ATR_RATIO = 2.5

# Fibonacci Retracement Levels
FIB_0 = 0.0
FIB_236 = 0.236
FIB_382 = 0.382
FIB_500 = 0.500
FIB_618 = 0.618
FIB_786 = 0.786
FIB_1000 = 1.0

FIB_LEVELS = [FIB_0, FIB_236, FIB_382, FIB_500, FIB_618, FIB_786, FIB_1000]

# Retracement Zones
FIB_PRIMARY_LOW = 0.382
FIB_PRIMARY_HIGH = 0.618
FIB_PREFERRED_LOW = 0.500
FIB_PREFERRED_HIGH = 0.618
FIB_INVALIDATION = 0.786

# Pullback Confirmation & Displacement
AVG_BODY_PERIOD = 10
DISPLACEMENT_BODY_MULTIPLIER = 1.5
MIN_BODY_PERCENTAGE = 0.60
MAX_ENTRY_DEVIATION_ATR = 0.25

# Stop Loss Buffer
SL_ATR_BUFFER = 0.10

# Risk / Reward & Scoring
MIN_RR = 2.0
MIN_SETUP_SCORE = 11

# Risk Management
RISK_PER_TRADE = 0.01  # 1% Account Equity per trade
DEFAULT_LEVERAGE = 5   # 5X Isolated Leverage
MAX_DAILY_LOSS = None  # No maximum daily loss limit
MAX_CONSECUTIVE_LOSSES = 3
COOLDOWN_HOURS = 4.0
MAX_DAILY_TRADES = 10
MAX_OPEN_POSITIONS = 5
MAX_POSITIONS_PER_SYMBOL = 1

# Timeouts & Setup Expiration
ENTRY_ORDER_TIMEOUT_MINUTES = 30
MAX_SETUP_AGE_CANDLES = 20  # 5M candles

# Trading Sessions (UTC)
# List of (start_hour, start_min, end_hour, end_min)
DEFAULT_TRADING_SESSIONS = [
    (7, 0, 11, 0),   # 07:00 - 11:00 UTC
    (13, 0, 17, 0),  # 13:00 - 17:00 UTC
]

# Backtesting Data Split
TRAIN_SPLIT_RATIO = 0.60
VAL_SPLIT_RATIO = 0.20
OOS_SPLIT_RATIO = 0.20

# Fees & Slippage Estimates (USDT-M Futures)
DEFAULT_TAKER_FEE = 0.0004  # 0.04%
DEFAULT_MAKER_FEE = 0.0002  # 0.02%
DEFAULT_SLIPPAGE = 0.0001   # 0.01%
