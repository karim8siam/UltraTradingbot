"""
Binance Futures GFS (Grandfather-Father-Son) Trading Bot Configuration
Mathematical & Deterministic Multi-Timeframe System (1D -> 4H -> 15M)
"""

import os
from dataclasses import dataclass, field
from typing import List, Tuple

# Auto-load .env file if present
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path, "r") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                val = _v.strip().strip('"').strip("'")
                os.environ[_k.strip()] = val

# Default Symbols (Verified dynamically through exchangeInfo - Top 30 Pairs)
DEFAULT_SYMBOLS: List[str] = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "SUIUSDT",
    "NEARUSDT",
    "APTUSDT",
    "1000PEPEUSDT",
    "WIFUSDT",
    "1000SHIBUSDT",
    "ARBUSDT",
    "OPUSDT",
    "INJUSDT",
    "FETUSDT",
    "SEIUSDT",
    "TIAUSDT",
    "RENDERUSDT",
    "AAVEUSDT",
    "DOTUSDT",
    "ATOMUSDT",
    "UNIUSDT",
    "LTCUSDT",
    "ENAUSDT",
    "FILUSDT",
    "WLDUSDT",
]

# Timeframes
TIMEFRAME_GRANDFATHER = "1d"
TIMEFRAME_FATHER = "4h"
TIMEFRAME_SON = "15m"

# Strategy Parameters
SWING_LENGTH = 2
DAILY_EMA_FAST = 50
DAILY_EMA_SLOW = 200
FOUR_HOUR_EMA_FAST = 20
FOUR_HOUR_EMA_SLOW = 50
SON_ATR_PERIOD = 14
SON_ATR_AVG_PERIOD = 50

# Displacement & Confirmation Filters
DISPLACEMENT_BODY_MULTIPLIER = 1.25
MIN_BODY_PERCENTAGE = 0.55
DISPLACEMENT_LOOKBACK = 10

# Entry & SL / TP Filters
ENTRY_RETRACEMENT_RATIO = 0.50
MAX_ENTRY_DEVIATION_ATR = 0.25
SL_ATR_BUFFER = 0.10
MIN_RR = 2.0
MIN_SETUP_SCORE = 11
MAX_SETUP_AGE = 20
ENTRY_ORDER_TIMEOUT_MINUTES = 30

# Volatility Filter
MAX_ATR_RATIO = 2.5

# Risk Management
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.02"))
DEFAULT_LEVERAGE = int(os.getenv("DEFAULT_LEVERAGE", "5"))
TARGET_PROFIT_EQUITY_PCT = float(os.getenv("TARGET_PROFIT_EQUITY_PCT", "0.02"))
STOP_LOSS_EQUITY_PCT = float(os.getenv("STOP_LOSS_EQUITY_PCT", "0.01"))
ENABLE_STOP_LOSS = os.getenv("ENABLE_STOP_LOSS", "true").lower() == "true"
USE_MARKET_ENTRY = os.getenv("USE_MARKET_ENTRY", "true").lower() == "true"
MARGIN_TYPE = os.getenv("MARGIN_TYPE", "ISOLATED")
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0.02"))
MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))
CONSECUTIVE_LOSS_COOLDOWN_HOURS = 4
MAX_DAILY_TRADES = int(os.getenv("MAX_DAILY_TRADES", "999"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "1"))
ONE_POSITION_PER_SYMBOL = True

# Trading Sessions (UTC)
TRADING_SESSIONS: List[Tuple[str, str]] = [
    ("07:00", "11:00"),
    ("13:00", "17:00"),
]
ENFORCE_TRADING_SESSIONS = False

# Fees & Backtesting Simulation
MAKER_FEE_RATE = 0.0002
TAKER_FEE_RATE = 0.0005
SLIPPAGE_RATE = 0.0001
ESTIMATED_FUNDING_RATE = 0.0001

# Execution Mode Gates
PAPER_TRADING = os.getenv("LIVE_TRADING", "false").lower() != "true"
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
LIVE_TRADING = os.getenv("LIVE_TRADING", "false").lower() == "true"
LIVE_TRADING_CONFIRMATION = os.getenv("LIVE_TRADING_CONFIRMATION", "false").lower() == "true"

# API URLs & Endpoints
BINANCE_FUTURES_LIVE_REST = "https://fapi.binance.com"
BINANCE_FUTURES_TESTNET_REST = "https://testnet.binancefuture.com"
BINANCE_FUTURES_LIVE_WS = "wss://fstream.binance.com/ws"
BINANCE_FUTURES_TESTNET_WS = "wss://stream.binancefuture.com/ws"

# Database Configuration
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "gfs_bot.db")

def load_dynamic_symbols(engine_key: str, default_symbols: List[str]) -> List[str]:
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
                    return alloc
        except Exception:
            pass
    return default_symbols

@dataclass
class BotConfig:
    symbols: List[str] = field(default_factory=lambda: load_dynamic_symbols("engine_8_gfs_multitimeframe", list(DEFAULT_SYMBOLS)))
    paper_trading: bool = PAPER_TRADING
    binance_testnet: bool = BINANCE_TESTNET
    live_trading: bool = LIVE_TRADING
    live_confirmation: bool = LIVE_TRADING_CONFIRMATION
    risk_per_trade: float = RISK_PER_TRADE
    max_daily_loss: float = MAX_DAILY_LOSS
    max_consecutive_losses: int = MAX_CONSECUTIVE_LOSSES
    max_daily_trades: int = MAX_DAILY_TRADES
    max_open_positions: int = MAX_OPEN_POSITIONS
    min_rr: float = MIN_RR
    min_setup_score: int = MIN_SETUP_SCORE
    default_leverage: int = DEFAULT_LEVERAGE
    target_profit_equity_pct: float = TARGET_PROFIT_EQUITY_PCT
    stop_loss_equity_pct: float = STOP_LOSS_EQUITY_PCT
    enable_stop_loss: bool = ENABLE_STOP_LOSS
    use_market_entry: bool = USE_MARKET_ENTRY
    margin_type: str = MARGIN_TYPE
    enforce_sessions: bool = ENFORCE_TRADING_SESSIONS
    api_key: str = os.getenv("BINANCE_API_KEY", "")
    api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    db_path: str = DATABASE_PATH

    @property
    def mode_name(self) -> str:
        if self.live_trading and self.live_confirmation and not self.binance_testnet:
            return "LIVE"
        elif self.binance_testnet and not self.paper_trading:
            return "TESTNET"
        elif self.paper_trading:
            return "PAPER"
        return "DRY_RUN"
