from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.schemas.auth import LoginRequest, SignupRequest
from app.schemas.user import UserWithToken
from app.services.auth_service import verify_password, create_access_token
from app.services.session_service import create_session, revoke_session
from app.services.user_service import get_user_by_email, create_user
from app.dependencies import get_current_user, get_current_session_jti
from app.kafka_utils import Topics, publish_event

router = APIRouter()


@router.post("/signup", response_model=UserWithToken, status_code=status.HTTP_201_CREATED)
async def signup(data: SignupRequest, request: Request):
    if await get_user_by_email(data.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    user = await create_user(data)
    token, jti, expires_at = create_access_token(user["id"])
    await create_session(user["id"], jti, expires_at, user_agent=request.headers.get("user-agent"))
    await publish_event(Topics.USER_CREATED, {
        "user_id": user["id"],
        "email": user["email"],
        "account_type": user.get("account_type", "user"),
    }, key=user["id"])
    return UserWithToken(user=user, access_token=token)


@router.post("/login", response_model=UserWithToken)
async def login(data: LoginRequest, request: Request):
    user = await get_user_by_email(data.email)
    if not user or not verify_password(data.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if not user.get("is_active"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated.")
    token, jti, expires_at = create_access_token(user["id"])
    await create_session(user["id"], jti, expires_at, user_agent=request.headers.get("user-agent"))
    return UserWithToken(user=user, access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(jti: str | None = Depends(get_current_session_jti), _=Depends(get_current_user)):
    if jti:
        await revoke_session(jti)
    return None
