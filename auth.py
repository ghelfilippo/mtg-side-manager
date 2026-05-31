"""Authentication: session cookies (itsdangerous) + bcrypt passwords."""
import json
import secrets
from pathlib import Path
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

DATA_DIR = Path(__file__).parent / "data"
_SECRET_KEY_FILE = DATA_DIR / ".secret_key"
USERS_FILE = DATA_DIR / "users.json"
SESSION_COOKIE = "sb_session"
SESSION_MAX_AGE = 86400 * 30  # 30 days


# ---------- secret key ----------

def _secret_key() -> str:
    DATA_DIR.mkdir(exist_ok=True)
    if _SECRET_KEY_FILE.exists():
        return _SECRET_KEY_FILE.read_text().strip()
    key = secrets.token_hex(32)
    _SECRET_KEY_FILE.write_text(key)
    return key


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret_key())


# ---------- password ----------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------- users ----------

def load_users() -> list[dict]:
    if not USERS_FILE.exists():
        return []
    return json.loads(USERS_FILE.read_text(encoding="utf-8")).get("users", [])


def save_users(users: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    USERS_FILE.write_text(
        json.dumps({"users": users}, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_user(username: str) -> Optional[dict]:
    return next((u for u in load_users() if u["username"] == username), None)


def ensure_default_admin() -> None:
    """On first run create a default admin user and print credentials."""
    if load_users():
        return
    password = secrets.token_urlsafe(12)
    save_users([{
        "username": "admin",
        "password_hash": hash_password(password),
        "archidekt_folder_id": "",
        "is_admin": True,
    }])
    sep = "=" * 52
    print(f"\n{sep}")
    print("  First run — default admin account created")
    print(f"  Username : admin")
    print(f"  Password : {password}")
    print("  Change it in the Admin panel after first login.")
    print(f"{sep}\n")


# ---------- session cookie ----------

def create_session(username: str) -> str:
    return _serializer().dumps(username)


def decode_session(token: str) -> Optional[str]:
    try:
        return _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


# ---------- FastAPI dependencies ----------

def get_current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    username = decode_session(token)
    if not username:
        raise HTTPException(status_code=401, detail="Session expired")
    user = get_user(username)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
