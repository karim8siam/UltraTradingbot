import os
import json
from typing import List

# Import authoritative 30-coin whitelist
try:
    from whitelist import FIXED_30_COINS, filter_allowed_symbols, is_symbol_allowed
except ImportError:
    from shared.whitelist import FIXED_30_COINS, filter_allowed_symbols, is_symbol_allowed

CANDIDATE_PATHS = [
    os.getenv("ACTIVE_PAIRS_FILE", ""),
    "/app/shared/active_pairs.json",
    os.path.join(os.path.dirname(__file__), "active_pairs.json"),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared", "active_pairs.json")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "shared", "active_pairs.json"))
]

def get_dynamic_symbols(engine_key: str, default_symbols: List[str] = None) -> List[str]:
    """
    Dynamically loads vetted active symbols for a specific engine.
    STRICT ENFORCEMENT:
    Any returned symbol MUST be inside FIXED_30_COINS.
    Symbols outside the 30 coins are strictly purged.
    """
    if default_symbols is None:
        default_symbols = list(FIXED_30_COINS)
    else:
        default_symbols = filter_allowed_symbols(default_symbols)

    for filepath in CANDIDATE_PATHS:
        if filepath and os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    allocations = data.get("engine_allocations", {})
                    if engine_key in allocations and allocations[engine_key]:
                        # Strictly filter against FIXED_30_COINS
                        vetted = filter_allowed_symbols(allocations[engine_key])
                        if vetted:
                            return vetted
            except Exception:
                continue
    return default_symbols
