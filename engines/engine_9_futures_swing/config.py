"""
Binance USDT-M Futures Systematic Swing Trading Bot - Configuration & Constants
"""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    # ---------------- Environment & Execution Gates ----------------
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
    BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    LIVE_TRADING: bool = os.getenv("LIVE_TRADING", "false").lower() == "true"
    LIVE_TRADING_CONFIRMATION: bool = os.getenv("LIVE_TRADING_CONFIRMATION", "false").lower() == "true"
    PAPER_TRADING: bool = os.getenv("PAPER_TRADING", "false").lower() == "true"
    DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() == "true"

    # ---------------- Default Trading Pairs (Top 25) ----------------
    SYMBOLS: List[str] = field(default_factory=lambda: [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "ADAUSDT",
        "DOGEUSDT",
        "AVAXUSDT",
        "LINKUSDT",
        "DOTUSDT",
        "NEARUSDT",
        "SUIUSDT",
        "APTUSDT",
        "OPUSDT",
        "ARBUSDT",
        "ATOMUSDT",
        "LTCUSDT",
        "BCHUSDT",
        "ETCUSDT",
        "FILUSDT",
        "ICPUSDT",
        "INJUSDT",
        "TIAUSDT",
        "RENDERUSDT",
        "UNIUSDT"
    ])

    # ---------------- Timeframes ----------------
    TF_DAILY: str = "1d"
    TF_4H: str = "4h"
    TF_1H: str = "1h"

    # ---------------- Risk & Portfolio Management (Section 77) ----------------
    RISK_PER_TRADE: float = 0.01          # 1% account risk per trade
    MIN_RR: float = 2.5                   # Minimum Risk/Reward ratio
    MIN_SETUP_SCORE: int = 14             # Minimum setup score to enter (Section 45)
    DEFAULT_LEVERAGE: int = 3             # 3x leverage for swing trades
    MAX_DAILY_LOSS: float = 0.02          # 2% max daily loss of starting daily equity
    MAX_CONSECUTIVE_LOSSES: int = 3       # Max 3 consecutive losses before cooldown
    COOLDOWN_HOURS: int = 12              # 12-hour cooldown after consecutive losses
    MAX_DAILY_TRADES: int = 3             # Max 3 new trades per UTC day
    MAX_OPEN_POSITIONS: int = 3           # Max 3 simultaneous open positions
    MAX_OPEN_RISK: float = 0.03           # Max 3% total open portfolio risk
    MAX_HIGH_CORRELATION_POSITIONS: int = 2 # Max correlated positions (> 0.80)
    CORRELATION_THRESHOLD: float = 0.80

    # ---------------- Indicators & Filters (Section 77) ----------------
    DAILY_EMA_FAST: int = 50
    DAILY_EMA_SLOW: int = 200
    FOUR_HOUR_EMA_FAST: int = 20
    FOUR_HOUR_EMA_SLOW: int = 50

    SWING_LENGTH: int = 2                 # Swing pivot confirmation window: High[i] > High[i-2..i+2]
    MIN_ADX: float = 20.0                 # Minimum 4H ADX trend strength
    STRONG_ADX: float = 25.0              # Strong ADX bonus threshold
    MAX_ATR_RATIO: float = 2.5            # Max CurrentATR / AvgATR50 ratio before rejecting for extreme vol
    MIN_VOLUME_RATIO: float = 1.20        # 4H Impulse volume vs AvgVolume20
    IMPULSE_BODY_MULTIPLIER: float = 1.25 # Body >= 1.25 * AvgBody10
    IMPULSE_ATR_MULTIPLIER: float = 1.0   # Move >= 1.0 * ATR14

    # ---------------- Pullback & Fibonacci Levels (Section 77) ----------------
    FIB_MIN_RETRACEMENT: float = 0.382    # 38.2%
    FIB_MID_RETRACEMENT: float = 0.500    # 50.0%
    FIB_MAX_PREFERRED: float = 0.618      # 61.8%
    MAX_RETRACEMENT: float = 0.705        # 70.5% max acceptable retracement

    # ---------------- 1H Confirmation & Entry ----------------
    CONFIRMATION_BODY_PERCENT_MIN: float = 0.55 # Confirmation candle body >= 55% of candle range
    ENTRY_MIDPOINT_FACTOR: float = 0.50         # Entry limit placed at 50% retracement of 1H confirm candle
    ENTRY_TIMEOUT_HOURS: int = 6                # Timeout after 6 x 1H candles if unfilled
    SL_ATR_BUFFER_FACTOR: float = 0.10          # SL = PullbackLow/High +/- (0.10 * ATR14_4H)

    # ---------------- Trade Management (Section 77) ----------------
    BREAKEVEN_AT_R: float = 1.0           # Move SL to breakeven after +1R
    BREAKEVEN_BUFFER_R: float = 0.05      # Small buffer on breakeven
    PARTIAL_TP_R: float = 2.0             # Partial TP at +2R
    PARTIAL_CLOSE_PERCENT: float = 0.50   # Close 50% of position at partial TP
    MAX_HOLD_DAYS: int = 30               # Maximum holding period in days

    # ---------------- Fee & Slippage Assumptions ----------------
    TAKER_FEE: float = 0.0005             # 0.05%
    MAKER_FEE: float = 0.0002             # 0.02%
    DEFAULT_SLIPPAGE_BPS: float = 2.0     # 2 bps slippage on market executions

    # ---------------- Database & Paths ----------------
    DB_PATH: str = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "database", "trades.db"))
    DATA_DIR: str = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))


def load_env_file(filepath: str = ".env") -> None:
    """Simple parser for .env file if present."""
    if not os.path.exists(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


# Load environment variables if .env exists
load_env_file(os.path.join(os.path.dirname(__file__), ".env"))
DEFAULT_CONFIG = Config()
