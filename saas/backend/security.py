import os
import hmac
import hashlib
import base64
import json
import time
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Master key initialization for AES-256-GCM
KEY_DIR = os.getenv("SAAS_DATA_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")))
KEY_FILE = os.path.join(KEY_DIR, "master_vault.key")
JWT_SECRET = os.getenv("JWT_SECRET", "ultra_trading_bot_jwt_secret_salt_998822")

os.makedirs(KEY_DIR, exist_ok=True)
if os.path.exists(KEY_FILE):
    with open(KEY_FILE, "rb") as f:
        MASTER_AES_KEY = f.read()
else:
    MASTER_AES_KEY = AESGCM.generate_key(bit_length=256)
    with open(KEY_FILE, "wb") as f:
        f.write(MASTER_AES_KEY)


def hash_password(password: str) -> str:
    """Hashes password using PBKDF2-HMAC-SHA256 with random salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return base64.b64encode(salt + key).decode('utf-8')


def verify_password(stored_hash: str, password: str) -> bool:
    """Verifies a password against the stored salt + hash."""
    try:
        decoded = base64.b64decode(stored_hash.encode('utf-8'))
        salt = decoded[:16]
        expected_key = decoded[16:]
        actual_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return hmac.compare_digest(expected_key, actual_key)
    except Exception:
        return False


def encrypt_secret(secret_text: str) -> str:
    """Encrypts plaintext API secret into AES-256-GCM ciphertext."""
    if not secret_text:
        return ""
    aesgcm = AESGCM(MASTER_AES_KEY)
    nonce = os.urandom(12)  # 96-bit nonce standard for GCM
    ciphertext = aesgcm.encrypt(nonce, secret_text.encode('utf-8'), None)
    return base64.b64encode(nonce + ciphertext).decode('utf-8')


def decrypt_secret(encrypted_text: str) -> str:
    """Decrypts AES-256-GCM ciphertext back into plaintext."""
    if not encrypted_text:
        return ""
    try:
        raw = base64.b64decode(encrypted_text.encode('utf-8'))
        nonce = raw[:12]
        ciphertext = raw[12:]
        aesgcm = AESGCM(MASTER_AES_KEY)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    except Exception as e:
        return ""


def create_access_token(payload: Dict[str, Any], expires_delta_seconds: int = 86400 * 7) -> str:
    """Generates an HMAC-SHA256 authenticated JWT."""
    header = {"alg": "HS256", "typ": "JWT"}
    body = payload.copy()
    body["exp"] = int(time.time()) + expires_delta_seconds

    hdr_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    body_b64 = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    signing_input = f"{hdr_b64}.{body_b64}".encode()
    signature = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

    return f"{hdr_b64}.{body_b64}.{sig_b64}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Validates signature and expiration of an access token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        hdr_b64, body_b64, sig_b64 = parts
        signing_input = f"{hdr_b64}.{body_b64}".encode()
        expected_sig = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(sig_b64 + "==")
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        body_json = base64.urlsafe_b64decode(body_b64 + "==").decode()
        payload = json.loads(body_json)
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None
