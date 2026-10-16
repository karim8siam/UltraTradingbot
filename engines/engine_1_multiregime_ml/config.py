"""
Configuration Module for Binance Futures ML Trading Bot.
Enforces strict security checks, whitelisted pairs, and risk rules.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ==========================================
# 1. EXCHANGE & CREDENTIALS
# ==========================================
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
# Default to Testnet / Sandbox mode for safety
USE_TESTNET = os.getenv("USE_TESTNET", "true").lower() in ("true", "1", "yes")

# ==========================================
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from shared.whitelist import FIXED_30_COINS, is_symbol_allowed, validate_symbol_or_reject

# STRICT FIXED 30-COIN WHITELIST (1st coin: BTC/USDT)
# Without these 30, no coin is accepted under any circumstances.
ALLOWED_SYMBOLS = [s[:-4] + "/USDT" for s in FIXED_30_COINS]

# Master Bitcoin Sentinel Layer (1-Hour Macro Trend Authority)
ENABLE_BITCOIN_SENTINEL_LAYER = os.getenv("ENABLE_BITCOIN_SENTINEL_LAYER", "true").lower() == "true"
BTC_SENTINEL_TIMEFRAME = os.getenv("BTC_SENTINEL_TIMEFRAME", "1h")

# Upgraded Timeframes: 5M Execution with 15M Structural Anchors & 1H BTC Trend
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "5m")
HIGHER_TIMEFRAME = os.getenv("HIGHER_TIMEFRAME", "15m")

# ==========================================
# 3. RISK MANAGEMENT RULES (STRICT 0.1% AMOUNT & 1:2 R:R ENGINE)
# ==========================================
MARGIN_FRACTION = float(os.getenv("MARGIN_FRACTION", "0.001"))  # 0.1% maximum amount (margin) of total balance per trade
RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", "0.1"))  # 0.1% maximum amount per trade
BASKET_WIN_TARGET_PERCENT = float(os.getenv("BASKET_WIN_TARGET_PERCENT", "1.0"))  # +1.0% Basket Cash Harvest (Closes all in profit)
# Stop-Loss: Managed per-pair independently via native Binance STOP_MARKET orders
DEFAULT_LEVERAGE = int(os.getenv("DEFAULT_LEVERAGE", "5"))  # 5x isolated
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", "30"))  # 30 pairs maximum
DRAWDOWN_RECOVERY_TRIGGER_PCT = float(os.getenv("DRAWDOWN_RECOVERY_TRIGGER_PCT", "-3.0"))  # -3.0% triggers Counter-Recovery
BREAKEVEN_FLUSH_TARGET_PCT = float(os.getenv("BREAKEVEN_FLUSH_TARGET_PCT", "0.0"))  # 0.0% triggers Market Close All
MAX_DAILY_LOSS_PERCENT = float(os.getenv("MAX_DAILY_LOSS_PERCENT", "3.0"))  # Kill switch at 3% daily drawdown
PAUSE_NEW_TRADES = False  # Trading LIVE & ACTIVE per user directive

# Take-Profit & Stop-Loss Multipliers (1:2 Risk/Reward Ratio — 2x Profit Target)
SL_ATR_MULTIPLIER = float(os.getenv("SL_ATR_MULTIPLIER", "1.5"))  # 1.5x ATR for Stop Loss (1R)
TP_ATR_MULTIPLIER = float(os.getenv("TP_ATR_MULTIPLIER", "3.0"))  # 3.0x ATR for Take Profit (2R -> 1:2 R:R)

# ==========================================
# 4. MACHINE LEARNING & GEMINI PARAMETERS (ENHANCED +2% QUALITY GATES)
# ==========================================
# Tier 1: Core Majors: BTC, ETH, BNB, SOL, XRP, ADA, NEAR, TRX -> 58.0%+
STANDARD_ML_THRESHOLD = float(os.getenv("STANDARD_ML_THRESHOLD", "0.58"))
STANDARD_GEMINI_THRESHOLD = float(os.getenv("STANDARD_GEMINI_THRESHOLD", "58.0"))

# Tier 2: High-Risk Alts: AVAX, DOGE, LINK, DOT -> 60.0%+
HIGH_RISK_ML_THRESHOLD = float(os.getenv("HIGH_RISK_ML_THRESHOLD", "0.60"))
HIGH_RISK_GEMINI_THRESHOLD = float(os.getenv("HIGH_RISK_GEMINI_THRESHOLD", "60.0"))

# Tier 3: Sniper Tokens: SUI, APT, RENDER, TIA, INJ, ARB, OP, FET, SEI -> 62.0%+
SNIPER_ML_THRESHOLD = float(os.getenv("SNIPER_ML_THRESHOLD", "0.62"))
SNIPER_GEMINI_THRESHOLD = float(os.getenv("SNIPER_GEMINI_THRESHOLD", "62.0"))

ML_CONFIDENCE_THRESHOLD = STANDARD_ML_THRESHOLD
GEMINI_CONFIDENCE_THRESHOLD = STANDARD_GEMINI_THRESHOLD
RETRAIN_TRADE_INTERVAL = int(os.getenv("RETRAIN_TRADE_INTERVAL", "5"))   # Continuous learning: Auto-retrains every 5 completed trades
MIN_SAMPLES_FOR_TRAIN = int(os.getenv("MIN_SAMPLES_FOR_TRAIN", "10"))    # Active immediately

# ==========================================
# 5. DATABASE & MODEL PATHS
# ==========================================
if os.getenv("VERCEL"):
    DATA_DIR = Path("/tmp")
    DB_PATH = Path("/tmp/trading_journal.db")
else:
    DATA_DIR = BASE_DIR / "data"
    try:
        DATA_DIR.mkdir(exist_ok=True)
    except Exception:
        pass
    DB_PATH = DATA_DIR / "trading_journal.db"
MODEL_PATH = DATA_DIR / "meta_classifier.joblib"
SCALER_PATH = DATA_DIR / "feature_scaler.joblib"


# ==========================================
# 6. WEB PLATFORM & BEP20 DEPOSIT SETTINGS
# ==========================================
# Master Platform BEP20 Address (where users send >= 1.0 USDT deposits)
PLATFORM_DEPOSIT_ADDRESS = os.getenv(
    "PLATFORM_DEPOSIT_ADDRESS", 
    "0x66A06fA03BE98383fe4F73a5f1783332CAC0F5A0"
)

# Binance Hot Wallet Address (where accumulated daily funds sweep for bot trading)
BINANCE_BOT_WALLET_ADDRESS = os.getenv(
    "BINANCE_BOT_WALLET_ADDRESS",
    "0xf13c3ce17b921ddff8d7057e2363fc79cac1fb2b"
)

# Daily Sweep Schedule (Default: 00:00 UTC / 12:00 AM UTC)
DAILY_SWEEP_HOUR_UTC = int(os.getenv("DAILY_SWEEP_HOUR_UTC", "0"))
DAILY_SWEEP_MINUTE_UTC = int(os.getenv("DAILY_SWEEP_MINUTE_UTC", "0"))
AUTO_SWEEP_ENABLED = os.getenv("AUTO_SWEEP_ENABLED", "true").lower() in ("true", "1", "yes")

# Binance Smart Chain (BSC) Settings
BSC_RPC_URLS = [
    os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/"),
    "https://bsc-dataseed1.defibit.io/",
    "https://bsc-dataseed2.ninicoin.io/",
    "https://rpc.ankr.com/bsc"
]

# Official BSC BEP20 USDT Contract
# Mainnet USDT: 0x55d398326f99059fF775485246999027B3197955 (18 decimals)
# Testnet USDT: 0x337610d27c682E347C9cD60BD4b3b107C9d34dDd
BSC_USDT_CONTRACT = os.getenv(
    "BSC_USDT_CONTRACT", 
    "0x55d398326f99059fF775485246999027B3197955"
).lower()

# Minimum Deposit Rule (Equal or more than 1 USDT)
MIN_DEPOSIT_USDT = float(os.getenv("MIN_DEPOSIT_USDT", "1.0"))

# Security & Web Server
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "apextrade_ai_super_secret_jwt_key_bsc_prod_2026")
SERVER_PORT = int(os.getenv("PORT", "8000"))
SERVER_HOST = os.getenv("HOST", "0.0.0.0")



ALL_SUPPORTED_SYMBOLS = list(ALLOWED_SYMBOLS)
ALLOWED_RAW_SYMBOLS = set(FIXED_30_COINS) | set(ALLOWED_SYMBOLS)


def validate_symbol(symbol: str) -> str:
    """
    Guarantees that ONLY the approved 30 Binance USD(S)-M Futures symbols are processed.
    Any other symbol is strictly rejected.
    """
    raw = symbol.upper().replace(":", "").replace("-", "")
    if "/" in raw:
        slash_sym = raw
        raw_sym = raw.replace("/", "")
    else:
        raw_sym = raw
        slash_sym = raw[:-4] + "/USDT" if raw.endswith("USDT") else raw + "/USDT"

    if raw_sym not in FIXED_30_COINS and slash_sym not in ALLOWED_SYMBOLS:
        raise ValueError(
            f"STRICT GATE REJECTION: Symbol '{symbol}' is not in the approved 30-coin whitelist! "
            f"Without these 30, no coin is accepted."
        )
    return slash_sym

