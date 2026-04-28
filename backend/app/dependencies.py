from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.services.auth_service import decode_access_token
from app.services.session_service import session_active
from app.services.user_service import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def _user_from_token(token: str | None):
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except JWTError:
        return None
    jti = payload.get("jti")
    if jti and not await session_active(jti):
        return None
    return await get_user_by_id(payload.get("sub"))


async def get_optional_current_user(token: str = Depends(oauth2_scheme_optional)):
    user = await _user_from_token(token)
    if user and user.get("is_active"):
        return user
    return None


async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = await _user_from_token(token)
    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_owner(user=Depends(get_current_user)):
    if not user.get("is_owner"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner account required.")
    return user


async def get_current_session_jti(token: str = Depends(oauth2_scheme)) -> str | None:
    try:
        return decode_access_token(token).get("jti")
    except JWTError:
        return None
