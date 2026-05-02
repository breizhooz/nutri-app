from email.policy import default

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import crud

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.session import get_session
from app.models.user import User
from app.schemas.user import RefreshRequest, TokenResponse, UserLogin

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
async def login(
        data:UserLogin,
        session: AsyncSession = Depends(get_session),
):
    #looking for user by mail
    result = await session.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    #same error if email doesnt exist or incorect password
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id))
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest):
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return TokenResponse(
        access_token=create_access_token(str(user_id)),
        refresh_token=create_refresh_token(str(user_id))
    )