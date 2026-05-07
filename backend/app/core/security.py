"""Security utilities using Python stdlib only — no external crypto deps."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import timedelta
from hashlib import sha256

from app.core.time import utc_now_naive

# ---------------------------------------------------------------------------
# API key utilities
# ---------------------------------------------------------------------------


def generate_api_key(prefix: str = "fsl") -> str:
    return f"{prefix}_{secrets.token_urlsafe(24)}"


def hash_secret(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def verify_secret(value: str, expected_hash: str) -> bool:
    current_hash = hash_secret(value)
    return hmac.compare_digest(current_hash, expected_hash)


# ---------------------------------------------------------------------------
# Password hashing — PBKDF2-HMAC-SHA256 (NIST SP 800-132)
# ---------------------------------------------------------------------------
_PBKDF2_ITERATIONS = 480_000
_SALT_SIZE = 32
_KEY_SIZE = 32


def hash_password(password: str) -> str:
    """Return a hex-encoded salt+key string safe for storage."""
    salt = os.urandom(_SALT_SIZE)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS, _KEY_SIZE)
    return (salt + key).hex()


def verify_password(plain: str, stored: str) -> bool:
    """Return True if *plain* matches the stored hash."""
    try:
        stored_bytes = bytes.fromhex(stored)
    except ValueError:
        return False
    salt = stored_bytes[:_SALT_SIZE]
    stored_key = stored_bytes[_SALT_SIZE:]
    computed = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, _PBKDF2_ITERATIONS, _KEY_SIZE)
    return hmac.compare_digest(computed, stored_key)


# ---------------------------------------------------------------------------
# JWT utilities — HS256 only, stdlib-only implementation
# ---------------------------------------------------------------------------


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = 4 - len(data) % 4
    if pad != 4:
        data += "=" * pad
    return base64.urlsafe_b64decode(data.encode("ascii"))


def _hs256_sign(signing_input: str, secret: str) -> str:
    return _b64url_encode(
        hmac.new(
            secret.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )


def create_access_token(
    data: dict,
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: timedelta | None = None,
) -> str:
    """Encode *data* as a signed HS256 JWT access token."""
    to_encode = data.copy()
    expire = utc_now_naive() + (expires_delta or timedelta(minutes=480))
    to_encode["exp"] = int(expire.timestamp())

    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url_encode(json.dumps(to_encode, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}"
    signature = _hs256_sign(signing_input, secret_key)
    return f"{signing_input}.{signature}"


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> dict | None:
    """Decode and verify a HS256 JWT; return the payload dict or None on failure."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}"

        # Verify signature (constant-time)
        expected_sig = _hs256_sign(signing_input, secret_key)
        if not hmac.compare_digest(sig_b64, expected_sig):
            return None

        payload = json.loads(_b64url_decode(payload_b64))

        # Verify expiration
        exp = payload.get("exp")
        if exp is not None and time.time() > exp:
            return None

        return payload
    except Exception:
        return None
