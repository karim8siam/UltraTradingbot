"""
Application Configuration & Settings
Implements strict security, live trading gates, and environment loading.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from config import constants


def _load_env_file(filepath: str = ".env"):
    """Simple .env parser without external dependencies."""
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key not in os.environ:
                os.environ[key] = val


_load_env_file()


@dataclass
class Settings:
    # API Credentials (never logged, never hardcoded)
    binance_api_key: str = field(default_factory=lambda: os.getenv("BINANCE_API_KEY", ""))
    binance_api_secret: str = field(default_factory=lambda: os.getenv("BINANCE_API_SECRET", ""))

    # Environment & Safety Flags
    binance_testnet: bool = field(
        default_factory=lambda: os.getenv("BINANCE_TESTNET", "true").lower() in ("true", "1", "yes")
    )
    live_trading: bool = field(
        default_factory=lambda: os.getenv("LIVE_TRADING", "false").lower() in ("true", "1", "yes")
    )
    live_trading_confirmation: bool = field(
        default_factory=lambda: os.getenv("LIVE_TRADING_CONFIRMATION", "false").lower() in ("true", "1", "yes")
    )
    paper_trading: bool = field(
        default_factory=lambda: os.getenv("PAPER_TRADING", "false").lower() in ("true", "1", "yes")
    )
    dry_run: bool = field(
        default_factory=lambda: os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")
    )
    emergency_stop: bool = field(
        default_factory=lambda: os.getenv("EMERGENCY_STOP", "false").lower() in ("true", "1", "yes")
    )

    # Strategy Parameters
    symbols: List[str] = field(
        default_factory=lambda: [
            s.strip().upper()
            for s in os.getenv("SYMBOLS", ",".join(constants.DEFAULT_SYMBOLS)).split(",")
            if s.strip()
        ]
    )
    risk_per_trade: float = float(os.getenv("RISK_PER_TRADE", str(constants.RISK_PER_TRADE)))
    default_leverage: int = int(os.getenv("DEFAULT_LEVERAGE", str(constants.DEFAULT_LEVERAGE)))
    min_rr: float = float(os.getenv("MIN_RR", str(constants.MIN_RR)))
    min_setup_score: int = int(os.getenv("MIN_SETUP_SCORE", str(constants.MIN_SETUP_SCORE)))
    max_daily_loss: Optional[float] = (
        float(os.getenv("MAX_DAILY_LOSS"))
        if os.getenv("MAX_DAILY_LOSS") and os.getenv("MAX_DAILY_LOSS").lower() not in ("none", "0", "false")
        else constants.MAX_DAILY_LOSS
    )
    max_consecutive_losses: int = int(os.getenv("MAX_CONSECUTIVE_LOSSES", str(constants.MAX_CONSECUTIVE_LOSSES)))
    cooldown_hours: float = float(os.getenv("COOLDOWN_HOURS", str(constants.COOLDOWN_HOURS)))
    max_daily_trades: int = int(os.getenv("MAX_DAILY_TRADES", str(constants.MAX_DAILY_TRADES)))
    max_open_positions: int = int(os.getenv("MAX_OPEN_POSITIONS", str(constants.MAX_OPEN_POSITIONS)))
    entry_order_timeout_minutes: int = int(
        os.getenv("ENTRY_ORDER_TIMEOUT", str(constants.ENTRY_ORDER_TIMEOUT_MINUTES))
    )
    max_setup_age_candles: int = int(
        os.getenv("MAX_SETUP_AGE", str(constants.MAX_SETUP_AGE_CANDLES))
    )
    impulse_min_atr: float = float(os.getenv("IMPULSE_MIN_ATR", str(constants.IMPULSE_MIN_ATR)))
    max_atr_ratio: float = float(os.getenv("MAX_ATR_RATIO", str(constants.MAX_ATR_RATIO)))
    database_path: str = os.getenv("DATABASE_PATH", "data/trading_bot.db")

    def is_live_allowed(self) -> bool:
        """Live trading strictly requires LIVE_TRADING=true AND LIVE_TRADING_CONFIRMATION=true AND NOT binance_testnet."""
        return (
            self.live_trading is True
            and self.live_trading_confirmation is True
            and self.binance_testnet is False
            and self.emergency_stop is False
            and self.dry_run is False
            and self.paper_trading is False
        )

    def get_execution_mode(self) -> str:
        if self.is_live_allowed():
            return "LIVE"
        if self.paper_trading:
            return "PAPER"
        if self.binance_testnet and not self.dry_run:
            return "TESTNET"
        return "DRY_RUN"


# Global settings instance
settings = Settings()
