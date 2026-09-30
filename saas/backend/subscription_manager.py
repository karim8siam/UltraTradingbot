import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from database import get_db


class SubscriptionManager:
    """
    Manages client subscription lifecycles, trial activations, and automated disconnection.
    """

    @staticmethod
    def create_free_trial(user_id: int) -> Dict[str, Any]:
        """
        Activates a 7-day free trial for a newly registered user.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=7)

        now_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        exp_str = expires_at.strftime("%Y-%m-%d %H:%M:%S UTC")

        with get_db() as conn:
            conn.execute("""
            INSERT INTO subscriptions (user_id, tier, status, starts_at, expires_at, amount_paid, created_at)
            VALUES (?, 'trial_7d', 'active', ?, ?, 0.0, ?)
            """, (user_id, now_str, exp_str, now_str))
            conn.commit()

        return {
            "tier": "trial_7d",
            "status": "active",
            "starts_at": now_str,
            "expires_at": exp_str,
            "days_remaining": 7.0
        }

    @staticmethod
    def upgrade_plan(user_id: int, tier: str, amount_paid: float) -> Dict[str, Any]:
        """
        Upgrades to a paid plan:
        - $19 for 7 Days ('paid_7d')
        - $69 for 30 Days ('paid_30d')
        """
        days_to_add = 7 if tier == "paid_7d" else 30
        now = datetime.now(timezone.utc)

        with get_db() as conn:
            # Check existing active subscription to stack time
            row = conn.execute("""
            SELECT expires_at, status FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY id DESC LIMIT 1
            """, (user_id,)).fetchone()

            base_time = now
            if row:
                try:
                    exp_dt = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                    if exp_dt > now:
                        base_time = exp_dt
                except Exception:
                    base_time = now

            new_expires = base_time + timedelta(days=days_to_add)
            now_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
            exp_str = new_expires.strftime("%Y-%m-%d %H:%M:%S UTC")

            conn.execute("""
            INSERT INTO subscriptions (user_id, tier, status, starts_at, expires_at, amount_paid, created_at)
            VALUES (?, ?, 'active', ?, ?, ?, ?)
            """, (user_id, tier, now_str, exp_str, amount_paid, now_str))

            # Re-enable connected exchange if was previously disconnected due to expiry
            conn.execute("""
            UPDATE exchange_keys SET status = 'connected'
            WHERE user_id = ? AND is_valid = 1
            """, (user_id,))
            conn.commit()

        return {
            "tier": tier,
            "status": "active",
            "starts_at": now_str,
            "expires_at": exp_str,
            "days_remaining": round((new_expires - now).total_seconds() / 86400.0, 1)
        }

    @staticmethod
    def process_bep20_payment(
        user_id: int,
        tx_hash: str,
        amount: float,
        tier: str,
        token_symbol: str,
        sender_address: str,
        receiver_address: str,
        block_number: int
    ) -> Dict[str, Any]:
        """
        Records a verified BEP20 blockchain payment and extends subscription.
        Guarantees that tx_hash can never be reused.
        """
        clean_hash = tx_hash.strip().lower()
        now = datetime.now(timezone.utc)
        now_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        with get_db() as conn:
            # 1. Check if transaction hash has already been redeemed
            existing = conn.execute(
                "SELECT id, user_id, created_at FROM payment_transactions WHERE LOWER(tx_hash) = ?",
                (clean_hash,)
            ).fetchone()
            if existing:
                raise ValueError("This transaction hash has already been redeemed and cannot be used again.")

            # 2. Insert into payment_transactions
            conn.execute("""
            INSERT INTO payment_transactions (
                user_id, tx_hash, amount, token_symbol, tier, sender_address, receiver_address, network, block_number, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'BEP20', ?, 'verified', ?)
            """, (user_id, clean_hash, amount, token_symbol, tier, sender_address, receiver_address, block_number, now_str))

            # 3. Calculate new subscription expiration (stacking if currently active)
            days_to_add = 30 if tier == "paid_30d" else 7

            row = conn.execute("""
            SELECT expires_at, status FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY id DESC LIMIT 1
            """, (user_id,)).fetchone()

            base_time = now
            if row:
                try:
                    exp_dt = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                    if exp_dt > now:
                        base_time = exp_dt
                except Exception:
                    base_time = now

            new_expires = base_time + timedelta(days=days_to_add)
            exp_str = new_expires.strftime("%Y-%m-%d %H:%M:%S UTC")

            conn.execute("""
            INSERT INTO subscriptions (user_id, tier, status, starts_at, expires_at, amount_paid, created_at)
            VALUES (?, ?, 'active', ?, ?, ?, ?)
            """, (user_id, tier, now_str, exp_str, amount, now_str))

            # Re-activate exchange connection if was disconnected
            conn.execute("""
            UPDATE exchange_keys SET status = 'connected'
            WHERE user_id = ? AND is_valid = 1
            """, (user_id,))
            conn.commit()

        return {
            "tier": tier,
            "status": "active",
            "starts_at": now_str,
            "expires_at": exp_str,
            "days_remaining": round((new_expires - now).total_seconds() / 86400.0, 1),
            "amount_paid": amount,
            "token": token_symbol,
            "tx_hash": clean_hash
        }

    @staticmethod
    def get_subscription_status(user_id: int) -> Dict[str, Any]:
        """
        Calculates live subscription status and countdown.
        """
        now = datetime.now(timezone.utc)
        with get_db() as conn:
            row = conn.execute("""
            SELECT id, tier, status, starts_at, expires_at FROM subscriptions
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 1
            """, (user_id,)).fetchone()

            if not row:
                return {
                    "is_active": False,
                    "tier": "none",
                    "status": "expired",
                    "seconds_remaining": 0,
                    "time_display": "Expired",
                    "expires_at": ""
                }

            try:
                exp_dt = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                diff = exp_dt - now
                sec = int(diff.total_seconds())

                if sec <= 0:
                    # Auto-expire
                    conn.execute("UPDATE subscriptions SET status = 'expired' WHERE id = ?", (row["id"],))
                    conn.execute("UPDATE exchange_keys SET status = 'disconnected' WHERE user_id = ?", (user_id,))
                    conn.commit()
                    return {
                        "is_active": False,
                        "tier": row["tier"],
                        "status": "expired",
                        "seconds_remaining": 0,
                        "time_display": "Expired (0d 0h)",
                        "expires_at": row["expires_at"]
                    }

                days = diff.days
                hours = int((diff.seconds) / 3600)
                mins = int(((diff.seconds) % 3600) / 60)

                return {
                    "is_active": True,
                    "tier": row["tier"],
                    "status": "active",
                    "seconds_remaining": sec,
                    "days": days,
                    "hours": hours,
                    "minutes": mins,
                    "time_display": f"{days}d {hours}h {mins}m",
                    "expires_at": row["expires_at"]
                }
            except Exception:
                return {
                    "is_active": False,
                    "tier": row["tier"],
                    "status": "error",
                    "seconds_remaining": 0,
                    "time_display": "Error",
                    "expires_at": ""
                }

    @staticmethod
    def run_auto_disconnect_cycle() -> int:
        """
        Background safety sweeper: disconnects any accounts whose subscription has ended.
        """
        now = datetime.now(timezone.utc)
        now_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        disconnected_count = 0

        with get_db() as conn:
            expired_subs = conn.execute("""
            SELECT id, user_id FROM subscriptions
            WHERE status = 'active' AND expires_at < ?
            """, (now_str,)).fetchall()

            for sub in expired_subs:
                conn.execute("UPDATE subscriptions SET status = 'expired' WHERE id = ?", (sub["id"],))
                conn.execute("UPDATE exchange_keys SET status = 'disconnected' WHERE user_id = ?", (sub["user_id"],))
                disconnected_count += 1
            conn.commit()

        return disconnected_count
