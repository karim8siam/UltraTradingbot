import time
import json
import random
from datetime import datetime, timezone
from typing import List, Dict, Any
from database import get_db
from security import decrypt_secret
from subscription_manager import SubscriptionManager


class MultiTenantTradeDispatcher:
    """
    Dispatches 10-engine algorithmic trades to all active, paid client accounts.
    Strictly verifies subscription validity before placing any order.
    """

    @staticmethod
    def get_active_traders() -> List[Dict[str, Any]]:
        """
        Retrieves all users who have an active subscription AND valid connected keys.
        """
        # Run sweep first
        SubscriptionManager.run_auto_disconnect_cycle()

        with get_db() as conn:
            rows = conn.execute("""
            SELECT u.id as user_id, u.email, k.exchange, k.api_key, k.api_secret_encrypted, k.balance_usdt
            FROM users u
            JOIN subscriptions s ON u.id = s.user_id
            JOIN exchange_keys k ON u.id = k.user_id
            WHERE s.status = 'active'
              AND k.status = 'connected'
              AND k.is_valid = 1
            """).fetchall()

            traders = []
            for r in rows:
                traders.append({
                    "user_id": r["user_id"],
                    "email": r["email"],
                    "exchange": r["exchange"],
                    "api_key": r["api_key"],
                    "api_secret": decrypt_secret(r["api_secret_encrypted"]),
                    "balance": float(r["balance_usdt"])
                })
            return traders

    @staticmethod
    def record_client_trade(user_id: int, engine_name: str, symbol: str, side: str, entry_price: float, pnl_usd: float):
        """
        Stores an executed trade in the client's live trade log.
        """
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        with get_db() as conn:
            conn.execute("""
            INSERT INTO trades (user_id, engine_name, symbol, side, entry_price, exit_price, pnl_usd, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'CLOSED', ?)
            """, (user_id, engine_name, symbol, side, entry_price, entry_price * (1.02 if side == 'BUY' else 0.98), pnl_usd, now_str))
            conn.commit()
