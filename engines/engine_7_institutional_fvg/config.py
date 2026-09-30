"""
Configuration Module for Binance USDT-M Futures Automated FVG Trading Bot (Version 1)
Strictly adheres to Section 78 and prompt specifications.
"""

import os
from dataclasses import dataclass, field
from typing import List, Tuple

def load_env_file(filepath: str = ".env") -> dict:
    """Load key-value pairs from .env file without external dependencies."""
    env_vars = {}
    if not os.path.exists(filepath):
        return env_vars
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("\"'")
                env_vars[k] = v
                if k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass
    return env_vars

# Auto-load .env on import
load_env_file()


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
    # 1. Trading Environment & Modes
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
    BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() == "true"
    PAPER_TRADING: bool = os.getenv("PAPER_TRADING", "false").lower() == "true"
    LIVE_TRADING: bool = os.getenv("LIVE_TRADING", "false").lower() == "true"
    LIVE_TRADING_CONFIRMATION: bool = os.getenv("LIVE_TRADING_CONFIRMATION", "false").lower() == "true"
    EMERGENCY_STOP: bool = os.getenv("EMERGENCY_STOP", "false").lower() == "true"

    # API Endpoints
    LIVE_REST_URL: str = "https://fapi.binance.com"
    TESTNET_REST_URL: str = "https://testnet.binancefuture.com"

    # 2. Trading Pairs (Dynamically refreshed from 24h screener with 50%+ win-rate)
    SYMBOLS: List[str] = field(default_factory=lambda: load_dynamic_symbols("engine_7_institutional_fvg", [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "SUIUSDT",
        "NEARUSDT", "APTUSDT", "LTCUSDT", "BCHUSDT", "DOTUSDT",
        "POLUSDT", "ETCUSDT", "XLMUSDT", "FILUSDT", "INJUSDT",
        "RENDERUSDT", "1000PEPEUSDT", "1000SHIBUSDT", "1000BONKUSDT", "1000FLOKIUSDT",
        "TIAUSDT", "SEIUSDT", "FETUSDT", "ARBUSDT", "OPUSDT"
    ]))

    # 3. Timeframes (Section 3)
    TF_BIAS_MAJOR: str = "4h"
    TF_BIAS_TREND: str = "1h"
    TF_SETUP_FVG: str = "15m"
    TF_CONFIRMATION: str = "5m"

    # 4. Market Structure & Swings (Section 10, 78)
    SWING_LENGTH: int = 2

    # 5. FVG & Displacement Parameters (Section 7, 8, 15, 78)
    DISPLACEMENT_LOOKBACK: int = 10
    DISPLACEMENT_BODY_MULTIPLIER: float = 1.5
    MIN_BODY_PERCENTAGE: float = 0.60
    MIN_FVG_ATR: float = 0.05
    IMPULSE_MIN_ATR: float = 1.5
    FVG_ENTRY_PERCENTAGE: float = 0.50  # 50% midpoint
    MAX_FVG_AGE: int = 50  # 50 candles on 5M timeframe (Section 44, 78)
    MAX_SETUP_AGE: int = 20  # candles

    # 6. Quality Scoring (Section 45, 78)
    MIN_SETUP_SCORE: int = 10

    # 7. Entry & Stops (Section 27, 28, 29, 30, 31, 32, 78)
    MAX_ENTRY_DEVIATION_ATR: float = 1.5
    SL_ATR_BUFFER: float = 0.10
    MIN_RR: float = 2.0                 # Exact 1:2 Risk to Reward
    ENTRY_ORDER_TIMEOUT_MINUTES: int = 30

    # 8. Risk Management & Sizing
    RISK_PER_TRADE: float = 0.02        # 2% equity maximum risk per trade
    DEFAULT_LEVERAGE: int = 5           # 5x leverage fixed
    MAX_LEVERAGE_CAP: int = 5           # 5x leverage cap
    MAX_DAILY_LOSS: float = 0.06        # 6% equity daily circuit-breaker
    MAX_CONSECUTIVE_LOSSES: int = 999   # No artificial consecutive loss cap
    CONSECUTIVE_LOSS_COOLDOWN_HOURS: float = 0.0
    MAX_DAILY_TRADES: int = 999         # No maximum trade limit
    MAX_OPEN_POSITIONS: int = 5         # Allow positions up to margin capacity
    MAX_POSITIONS_PER_SYMBOL: int = 1
    MAX_ATR_RATIO: float = 2.5
    EXTREME_FUNDING_RATE_THRESHOLD: float = 0.0005  # 0.05% per 8h

    # ── Trade Execution & Exit Rules ──────────────────────────────────────────
    USE_MARKET_ENTRY: bool = True       # Immediate market execution on confirmation
    USE_SL: bool = True                 # Predefined Stop Loss (1:2 ratio)
    TARGET_SESSION_PNL_PCT: float = 0.02  # Close open positions if total unrealized PnL >= 2%

    # Trading Sessions (UTC) - 24/7 Continuous Trading Window
    TRADING_SESSIONS: List[Tuple[int, int]] = field(default_factory=lambda: [
        (0, 24),   # 24H continuous market coverage
    ])

    # 9. Costs & Slippage Simulation for Backtesting (Section 61, 66)
    TAKER_FEE_RATE: float = 0.0005  # 0.05% Binance Futures VIP0 / BNB discount
    MAKER_FEE_RATE: float = 0.0002  # 0.02%
    SLIPPAGE_RATE: float = 0.0003   # 0.03% realistic slippage
    DEFAULT_FUNDING_RATE: float = 0.0001  # 0.01% per 8h

    # 10. Database
    DATABASE_PATH: str = "trades.db"

    @property
    def rest_url(self) -> str:
        return self.TESTNET_REST_URL if self.BINANCE_TESTNET else self.LIVE_REST_URL

    def get_mode_name(self) -> str:
        if self.EMERGENCY_STOP:
            return "EMERGENCY STOPPED"
        if self.LIVE_TRADING and self.LIVE_TRADING_CONFIRMATION and not self.BINANCE_TESTNET:
            return "LIVE TRADING (REAL FUNDS)"
        if self.BINANCE_TESTNET and not self.DRY_RUN and not self.PAPER_TRADING:
            return "TESTNET (EXCHANGE SANDBOX)"
        if self.PAPER_TRADING:
            return "PAPER TRADING (REAL-TIME SIMULATION)"
        return "DRY RUN (CALCULATION ONLY)"

    def validate_safety(self) -> None:
        """Enforces live trading gates."""
        if self.LIVE_TRADING:
            if not self.LIVE_TRADING_CONFIRMATION:
                raise ValueError("SAFETY ERROR: LIVE_TRADING is true but LIVE_TRADING_CONFIRMATION is false.")
            if self.BINANCE_TESTNET:
                raise ValueError("SAFETY ERROR: LIVE_TRADING is enabled while BINANCE_TESTNET is true.")
            if not self.BINANCE_API_KEY or not self.BINANCE_API_SECRET:
                raise ValueError("SAFETY ERROR: Live trading requires BINANCE_API_KEY and BINANCE_API_SECRET.")
