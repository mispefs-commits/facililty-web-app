import hashlib, hmac, os, time
from datetime import datetime, timedelta, timezone
import jwt
from .config import settings

ITER = 200_000


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITER)
    return f"pbkdf2${ITER}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, it, salt, dk = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(calc.hex(), dk)
    except Exception:
        return False


def check_password_strength(pw: str):
    if len(pw) < 8 or pw.isalpha() or pw.isdigit():
        raise ValueError("Password must be 8+ characters and mix letters with numbers or symbols")


def create_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> int:
    return int(jwt.decode(token, settings.secret_key, algorithms=["HS256"])["sub"])


# In-memory login throttle (swap for Redis when running multiple workers)
_attempts: dict = {}


def throttle(key: str, limit: int = 10, window: int = 300) -> bool:
    t = time.time()
    hits = [x for x in _attempts.get(key, []) if t - x < window]
    if len(hits) >= limit:
        _attempts[key] = hits
        return False
    hits.append(t)
    _attempts[key] = hits
    return True
