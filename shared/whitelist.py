"""
shared/whitelist.py — Authoritative Global Whitelist for All 10 Trading Engines

STRICT ENFORCEMENT RULE:
Only these 30 Tier-1 Binance USDT-M Futures coins are accepted.
The 1st coin is BTCUSDT.
Without these 30 coins, NO other coin is accepted under any circumstances.
"""

from typing import List, Set

FIXED_30_COINS: List[str] = [
    "BTCUSDT",       # 1st Coin: Primary High-Liquidity Anchor
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
    "BCHUSDT",
    "DOTUSDT",
    "UNIUSDT",
    "FETUSDT",
    "TAOUSDT",
    "ARBUSDT",
    "INJUSDT",
    "ONDOUSDT",
    "ENAUSDT",
    "WLDUSDT",
    "AAVEUSDT",
    "XLMUSDT",
    "ICPUSDT",
    "HBARUSDT",
    "TIAUSDT",
    "FILUSDT",
    "OPUSDT"
]

ALLOWED_SET: Set[str] = set(FIXED_30_COINS)


def is_symbol_allowed(symbol: str) -> bool:
    """Returns True if and only if the symbol belongs to the approved 30-coin whitelist."""
    if not symbol:
        return False
    return symbol.upper().strip() in ALLOWED_SET


def filter_allowed_symbols(symbols: List[str]) -> List[str]:
    """Filters an incoming list of symbols to strictly contain only the approved 30 coins in order."""
    if not symbols:
        return list(FIXED_30_COINS)
    filtered = [s for s in symbols if is_symbol_allowed(s)]
    return filtered if filtered else list(FIXED_30_COINS)


def validate_symbol_or_reject(symbol: str) -> str:
    """Strict assertion: raises ValueError if symbol is outside the 30-coin whitelist."""
    s = symbol.upper().strip()
    if s not in ALLOWED_SET:
        raise ValueError(
            f"STRICT GATE REJECTION: Symbol '{symbol}' is NOT in the approved 30-coin whitelist! "
            f"Only the 30 fixed coins are permitted."
        )
    return s
