from datetime import datetime, timedelta, timezone
from typing import Union
import hashlib
import uuid

import bcrypt
from jose import jwt

from app.config import settings


def _prepare_for_bcrypt_bytes(password: Union[str, bytes]) -> bytes:
    pw_bytes = password.encode("utf-8") if isinstance(password, str) else password
    if len(pw_bytes) > 72:
        return hashlib.sha256(pw_bytes).hexdigest().encode("utf-8")
    return pw_bytes


def get_password_hash(password: str) -> str:
    pw_bytes = _prepare_for_bcrypt_bytes(password)
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    stored = hashed_password.encode("utf-8") if isinstance(hashed_password, str) else hashed_password
    try:
        return bcrypt.checkpw(_prepare_for_bcrypt_bytes(plain_password), stored)
    except Exception:
        return False


def create_access_token(subject: str, jti: str | None = None) -> tuple[str, str, datetime]:
    """Issue a JWT. Returns (token, jti, expires_at).

    The ``jti`` identifies the session document that must exist in Mongo for
    the token to be accepted — see ``session_service``.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = jti or uuid.uuid4().hex
    payload = {"sub": str(subject), "exp": expires_at, "jti": jti}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, jti, expires_at


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
