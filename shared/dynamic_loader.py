import os
import json
from typing import List

CANDIDATE_PATHS = [
    os.getenv("ACTIVE_PAIRS_FILE", ""),
    "/app/shared/active_pairs.json",
    os.path.join(os.path.dirname(__file__), "active_pairs.json"),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared", "active_pairs.json")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "shared", "active_pairs.json"))
]

def get_dynamic_symbols(engine_key: str, default_symbols: List[str]) -> List[str]:
    """
    Dynamically loads the 24-hour vetted active symbols for a specific engine.
    If the shared active_pairs.json file exists and is valid, returns the 50%+ win-rate pairs.
    Otherwise gracefully falls back to default_symbols.
    """
    for filepath in CANDIDATE_PATHS:
        if filepath and os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    allocations = data.get("engine_allocations", {})
                    if engine_key in allocations and allocations[engine_key]:
                        return allocations[engine_key]
            except Exception:
                continue
    return default_symbols
