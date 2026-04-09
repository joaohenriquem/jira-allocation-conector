"""
Encryption utilities for sensitive data.

Uses Fernet symmetric encryption to protect PII (emails, IPs, etc.)
stored in session state, cache, or logs.
"""

import base64
import hashlib
import os
from typing import Optional

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    import streamlit as st
except ImportError:
    st = None


def _get_encryption_key() -> bytes:
    """
    Get or generate encryption key.
    Uses ENCRYPTION_KEY from secrets/env, or derives one from a stable seed.
    """
    key = ""
    try:
        if st:
            key = st.secrets.get("ENCRYPTION_KEY", "")
    except Exception:
        pass
    if not key:
        key = os.getenv("ENCRYPTION_KEY", "")
    if not key:
        # Derive a stable key from machine-specific seed
        seed = os.getenv("JIRA_BASE_URL", "jira-allocation-default-seed")
        key_bytes = hashlib.sha256(seed.encode()).digest()
        return base64.urlsafe_b64encode(key_bytes)
    return key.encode() if isinstance(key, str) else key


def encrypt(value: str) -> str:
    """Encrypt a string value. Returns encrypted string or original if crypto unavailable."""
    if not value or not HAS_CRYPTO:
        return value
    try:
        f = Fernet(_get_encryption_key())
        return f.encrypt(value.encode()).decode()
    except Exception:
        return value


def decrypt(value: str) -> str:
    """Decrypt a string value. Returns decrypted string or original if crypto unavailable."""
    if not value or not HAS_CRYPTO:
        return value
    try:
        f = Fernet(_get_encryption_key())
        return f.decrypt(value.encode()).decode()
    except Exception:
        return value


def mask_email(email: str) -> str:
    """Mask email for safe logging. ex: j***@sejaefi.com.br"""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return f"{local[0]}***@{domain}"


def mask_ip(ip: str) -> str:
    """Mask IP for safe logging. ex: 192.168.0.***"""
    if not ip:
        return "***"
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.***"
    return "***"


def encrypt_json_file(json_path: str) -> bool:
    """
    Encrypt a JSON file in-place, replacing it with .enc version.
    The original .json is removed after encryption.
    
    Returns True if successful.
    """
    if not HAS_CRYPTO:
        return False
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        f = Fernet(_get_encryption_key())
        encrypted = f.encrypt(content.encode())
        
        enc_path = json_path + ".enc"
        with open(enc_path, "wb") as f:
            f.write(encrypted)
        
        os.remove(json_path)
        return True
    except Exception:
        return False


def decrypt_json_file(enc_path: str) -> Optional[str]:
    """
    Decrypt an encrypted JSON file and return its content as string.
    Falls back to reading plain JSON if .enc doesn't exist.
    """
    # Try encrypted file first
    if HAS_CRYPTO and os.path.exists(enc_path):
        try:
            with open(enc_path, "rb") as f:
                encrypted = f.read()
            fernet = Fernet(_get_encryption_key())
            return fernet.decrypt(encrypted).decode()
        except Exception:
            pass
    
    # Fallback: try plain JSON (without .enc extension)
    plain_path = enc_path.replace(".enc", "") if enc_path.endswith(".enc") else enc_path
    if os.path.exists(plain_path):
        try:
            with open(plain_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    
    return None


def load_encrypted_json(json_path: str) -> Optional[list]:
    """
    Load a JSON file, trying encrypted version first, then plain.
    
    Args:
        json_path: Path to the .json file (will also check .json.enc)
    
    Returns:
        Parsed JSON data or None.
    """
    import json
    
    enc_path = json_path + ".enc"
    
    # Try encrypted first
    content = decrypt_json_file(enc_path)
    if content:
        try:
            return json.loads(content)
        except Exception:
            pass
    
    # Fallback to plain
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    
    return None
