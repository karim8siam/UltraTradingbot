import os
from dataclasses import dataclass, field
from typing import List, Tuple

def get_env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key, '').strip().lower()
    if val in ('true', '1', 'yes', 't'):
        return True
    elif val in ('false', '0', 'no', 'f'):
        return False
    return default

def get_env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default

def get_env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

@dataclass
class Config:
    # 1. Trading Environment
    BINANCE_API_KEY: str = field(default_factory=lambda: os.getenv('BINANCE_API_KEY', ''))
    BINANCE_API_SECRET: str = field(default_factory=lambda: os.getenv('BINANCE_API_SECRET', ''))
    BINANCE_TESTNET: bool = field(default_factory=lambda: get_env_bool('BINANCE_TESTNET', True))
    LIVE_TRADING: bool = field(default_factory=lambda: get_env_bool('LIVE_TRADING', False))
    LIVE_TRADING_CONFIRMATION: bool = field(default_factory=lambda: get_env_bool('LIVE_TRADING_CONFIRMATION', False))
    DRY_RUN: bool = field(default_factory=lambda: get_env_bool('DRY_RUN', True))
    PAPER_TRADING: bool = field(default_factory=lambda: get_env_bool('PAPER_TRADING', False))
    EMERGENCY_STOP: bool = field(default_factory=lambda: get_env_bool('EMERGENCY_STOP', False))

    # 2. Trading Pairs (Top 20 most liquid pairs)
    SYMBOLS: List[str] = field(default_factory=lambda: [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
        'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'SUIUSDT',
        'NEARUSDT', 'PEPEUSDT', 'SHIBUSDT', 'APTUSDT', 'LTCUSDT',
        'TONUSDT', 'WIFUSDT', 'BCHUSDT', 'FETUSDT', 'TIAUSDT'
    ])

    # 3. Strategy Parameters
    SWING_LENGTH: int = 2
    EQUAL_LEVEL_TOLERANCE: float = 0.001  # 0.1% tolerance
    DISPLACEMENT_BODY_MULTIPLIER: float = 1.5
    MIN_BODY_PERCENTAGE: float = 0.60
    FVG_ENTRY_PERCENTAGE: float = 0.50  # 50% midpoint
    SL_ATR_BUFFER_MULTIPLIER: float = 0.10
    MIN_RR: float = 2.0
    MIN_SETUP_SCORE: int = 11
    MIN_STOP_DISTANCE_PCT: float = 0.002  # 0.20% minimum stop distance to eliminate fee drag

    # 4. Profit-Locking & Trade Management
    BREAKEVEN_R_TRIGGER: float = 1.5       # Move SL to breakeven once price reaches +1.5R
    PARTIAL_TP_R: float = 2.0              # Take 50% profit at +2.0R
    PARTIAL_TP_RATIO: float = 0.50         # 50% position closed at TP1
    SYMBOL_COOLDOWN_MINUTES: int = 60      # Cooldown before re-entering same symbol after loss

    # 5. Risk Management Limits
    RISK_PER_TRADE: float = 0.01  # 1% equity risk
    DEFAULT_LEVERAGE: int = 5
    MAX_DAILY_LOSS: float = 0.02  # 2% max daily loss
    MAX_CONSECUTIVE_LOSSES: int = 3
    CONSECUTIVE_LOSS_COOLDOWN_HOURS: int = 4
    MAX_DAILY_TRADES: int = 5
    MAX_OPEN_POSITIONS: int = 3
    MAX_POSITIONS_PER_SYMBOL: int = 1

    # 6. Order Management
    ENTRY_ORDER_TIMEOUT_MINUTES: int = 30
    MAX_ATR_RATIO: float = 2.5  # ATR(14) / SMA(ATR, 50) on 15M

    # 6. Trading Sessions (UTC Hours: (start_hour, end_hour))
    ALLOWED_SESSIONS: List[Tuple[int, int]] = field(default_factory=lambda: [
        (7, 11),   # London session (07:00 - 11:00 UTC)
        (13, 17)   # NY session (13:00 - 17:00 UTC)
    ])

    # 7. Warm-up Candle Requirements
    WARMUP_CANDLES_4H: int = 500
    WARMUP_CANDLES_1H: int = 1000
    WARMUP_CANDLES_15M: int = 2000
    WARMUP_CANDLES_5M: int = 3000

    # 8. Fees & Slippage for Realistic Backtesting & Simulation
    MAKER_FEE_RATE: float = 0.0002  # 0.02% maker fee
    TAKER_FEE_RATE: float = 0.0005  # 0.05% taker fee
    ESTIMATED_SLIPPAGE: float = 0.0001 # 0.01% slippage
    INITIAL_EQUITY: float = 10000.0

    # 9. Database & Storage Paths
    DATABASE_PATH: str = field(default_factory=lambda: os.getenv(
        "DATABASE_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "smc_trading.db")
    ))
    LOG_FILE: str = field(default_factory=lambda: os.getenv(
        "LOG_FILE",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.log")
    ))

    def get_mode_name(self) -> str:
        if self.LIVE_TRADING and self.LIVE_TRADING_CONFIRMATION and not self.BINANCE_TESTNET:
            return 'LIVE'
        elif self.BINANCE_TESTNET and not self.DRY_RUN and not self.PAPER_TRADING:
            return 'TESTNET'
        elif self.PAPER_TRADING:
            return 'PAPER'
        return 'DRY_RUN'

    def is_live_allowed(self) -> bool:
        return (not self.BINANCE_TESTNET) and self.LIVE_TRADING and self.LIVE_TRADING_CONFIRMATION
