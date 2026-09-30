"""
Live Trading Safety Gates & Environment Verification
Sections 1, 65, 76 Specification
"""

import logging
from config.settings import Settings

logger = logging.getLogger("LiveGate")


class LiveTradingGate:
    @staticmethod
    def verify_mode(settings: Settings) -> str:
        """
        Verifies the execution mode and enforces dual-confirmation safety for live trading.
        """
        if settings.is_live_allowed():
            print("=" * 70)
            print("⚠️  WARNING: LIVE TRADING IS ENABLED!")
            print("REAL CAPITAL WILL BE AT RISK ON BINANCE USDT-M FUTURES.")
            print("1% RISK PER TRADE AND HARD STOP LOSSES WILL BE ENFORCED.")
            print("=" * 70)
            logger.warning("Live trading mode verified and active.")
            return "LIVE"

        if settings.paper_trading:
            print("[" + settings.get_execution_mode() + "] Paper Trading Active (Simulated execution on live data)")
            return "PAPER"

        if settings.binance_testnet and not settings.dry_run:
            print("[" + settings.get_execution_mode() + "] Binance Futures TESTNET Active")
            return "TESTNET"

        print("[" + settings.get_execution_mode() + "] DRY RUN Mode Active (Calculations only, 0 orders dispatched)")
        return "DRY_RUN"
