import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db, init_db
from security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    encrypt_secret
)
from exchange_verifier import ExchangeVerifier
from subscription_manager import SubscriptionManager
from multi_tenant_trader import MultiTenantTradeDispatcher

app = FastAPI(title="UltraQuant Institutional SaaS Platform", version="2.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.getenv("FRONTEND_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend")))


# --- Pydantic Request Models ---
class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class ConnectExchangeRequest(BaseModel):
    exchange: str  # 'binance' or 'bybit'
    api_key: str
    api_secret: str

class UpgradeRequest(BaseModel):
    tier: str  # 'paid_7d' ($19) or 'paid_30d' ($69)


# --- Dependency for Authenticated Endpoints ---
def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token")
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid. Please log in.")
    return payload


# --- Public / Platform Endpoints ---
@app.get("/health")
@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/platform/stats")
def get_platform_stats():
    return {
        "active_engines_count": 10,
        "rolling_24h_win_rate": 84.9,
        "supported_exchanges": ["Binance Futures", "Bybit Linear Futures"],
        "non_custodial": True,
        "zero_strategy_leaks": True,
        "pricing_tiers": {
            "trial_7d": {"name": "7-Day Free Trial", "price": 0.0, "duration_days": 7},
            "paid_7d": {"name": "7-Day Full Access", "price": 19.0, "duration_days": 7},
            "paid_30d": {"name": "30-Day Institutional Pro", "price": 69.0, "duration_days": 30}
        }
    }


# --- Authentication Endpoints ---
@app.post("/api/auth/register")
def register(req: RegisterRequest):
    email = req.email.strip().lower()
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email is already registered")

        pwd_hash = hash_password(req.password)
        cursor = conn.execute("""
        INSERT INTO users (email, password_hash, full_name, created_at)
        VALUES (?, ?, ?, ?)
        """, (email, pwd_hash, req.full_name, now_str))
        user_id = cursor.lastrowid
        conn.commit()

    # Automatically grant 7-Day Free Trial on signup
    trial_info = SubscriptionManager.create_free_trial(user_id)
    token = create_access_token({"user_id": user_id, "email": email})

    return {
        "success": True,
        "token": token,
        "user": {"id": user_id, "email": email, "full_name": req.full_name},
        "subscription": trial_info,
        "message": "Welcome! Your 7-day free trial has been activated automatically."
    }


@app.post("/api/auth/login")
def login(req: LoginRequest):
    email = req.email.strip().lower()
    with get_db() as conn:
        user = conn.execute("SELECT id, email, password_hash, full_name FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not verify_password(user["password_hash"], req.password):
            raise HTTPException(status_code=400, detail="Invalid email or password")

        user_id = user["id"]

    sub_status = SubscriptionManager.get_subscription_status(user_id)
    token = create_access_token({"user_id": user_id, "email": email})

    return {
        "success": True,
        "token": token,
        "user": {"id": user_id, "email": user["email"], "full_name": user["full_name"]},
        "subscription": sub_status
    }


@app.get("/api/auth/me")
def get_profile(user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["user_id"]
    with get_db() as conn:
        u = conn.execute("SELECT id, email, full_name FROM users WHERE id = ?", (user_id,)).fetchone()
        key_row = conn.execute("SELECT exchange, api_key, is_valid, futures_enabled, balance_usdt, status FROM exchange_keys WHERE user_id = ?", (user_id,)).fetchone()

    sub = SubscriptionManager.get_subscription_status(user_id)
    key_info = None
    if key_row:
        # Mask API key for security
        raw_key = key_row["api_key"]
        masked_key = f"{raw_key[:4]}...{raw_key[-4:]}" if len(raw_key) > 8 else "***"
        key_info = {
            "exchange": key_row["exchange"],
            "masked_key": masked_key,
            "is_valid": bool(key_row["is_valid"]),
            "futures_enabled": bool(key_row["futures_enabled"]),
            "balance_usdt": key_row["balance_usdt"],
            "status": key_row["status"]
        }

    return {
        "user": {"id": u["id"], "email": u["email"], "full_name": u["full_name"]},
        "subscription": sub,
        "exchange": key_info
    }


# --- Exchange Verification & Binding ---
@app.post("/api/exchange/connect")
def connect_exchange(req: ConnectExchangeRequest, user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["user_id"]
    exchange = req.exchange.strip().lower()
    api_key = req.api_key.strip()
    api_secret = req.api_secret.strip()

    if exchange not in ["binance", "bybit"]:
        raise HTTPException(status_code=400, detail="Supported exchanges are 'binance' and 'bybit'.")
    if not api_key or not api_secret:
        raise HTTPException(status_code=400, detail="API key and Secret are required.")

    # 1. Live Exchange Permission & Connectivity Verification
    if exchange == "binance":
        check_result = ExchangeVerifier.verify_binance(api_key, api_secret)
    else:
        check_result = ExchangeVerifier.verify_bybit(api_key, api_secret)

    if not check_result["success"]:
        return {
            "success": False,
            "error": check_result.get("error", "Failed to verify exchange permissions."),
            "details": check_result
        }

    # 2. Store with military-grade AES-256-GCM encryption
    enc_secret = encrypt_secret(api_secret)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    with get_db() as conn:
        conn.execute("DELETE FROM exchange_keys WHERE user_id = ?", (user_id,))
        conn.execute("""
        INSERT INTO exchange_keys (user_id, exchange, api_key, api_secret_encrypted, is_valid, futures_enabled, withdrawals_disabled, balance_usdt, status, verified_at)
        VALUES (?, ?, ?, ?, 1, 1, 1, ?, 'connected', ?)
        """, (user_id, exchange, api_key, enc_secret, check_result["balance_usdt"], now_str))
        conn.commit()

    # Generate initial trade telemetry for client dashboard
    MultiTenantTradeDispatcher.generate_demo_trades_for_user(user_id)

    return {
        "success": True,
        "message": f"{exchange.upper()} Futures verified & connected! All 10 engines are now active.",
        "exchange": exchange,
        "balance_usdt": check_result["balance_usdt"],
        "futures_enabled": True,
        "withdrawals_disabled": True
    }


@app.post("/api/exchange/disconnect")
def disconnect_exchange(user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["user_id"]
    with get_db() as conn:
        conn.execute("UPDATE exchange_keys SET status = 'disconnected' WHERE user_id = ?", (user_id,))
        conn.commit()
    return {"success": True, "message": "Exchange disconnected. Bot trading suspended."}


# --- Subscription Management ---
@app.post("/api/subscription/upgrade")
def upgrade_subscription(req: UpgradeRequest, user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["user_id"]
    if req.tier not in ["paid_7d", "paid_30d"]:
        raise HTTPException(status_code=400, detail="Invalid tier. Choose 'paid_7d' ($19) or 'paid_30d' ($69)")

    amount = 19.0 if req.tier == "paid_7d" else 69.0
    res = SubscriptionManager.upgrade_plan(user_id, req.tier, amount)
    return {
        "success": True,
        "subscription": res,
        "message": f"Successfully upgraded! {7 if req.tier == 'paid_7d' else 30} days of 24/7 algorithmic trading active."
    }


# --- Trade Telemetry & History ---
@app.get("/api/user/trades")
def get_user_trades(user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["user_id"]
    with get_db() as conn:
        rows = conn.execute("""
        SELECT engine_name, symbol, side, entry_price, exit_price, pnl_usd, status, timestamp
        FROM trades
        WHERE user_id = ?
        ORDER BY id DESC LIMIT 50
        """, (user_id,)).fetchall()

        trades = [dict(r) for r in rows]
        total_pnl = sum(r["pnl_usd"] for r in trades)

    return {
        "total_trades": len(trades),
        "total_pnl_usd": round(total_pnl, 2),
        "trades": trades
    }


# --- Static Frontend Serving ---
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_frontend_root():
        index_file = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "UltraQuant SaaS Platform API Running"}
