import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import hash_password
from app.db.session import get_session
from app.models.user import User
from app.schemas.user import UserCreate, UserOut

router = APIRouter()


@router.post("",
             response_model=UserOut,
             status_code=status.HTTP_201_CREATED)
async def create_user(
        data: UserCreate,
        session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(User).where(User.email == data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    user = User(
        email=data.email, hashed_password=hash_password(data.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

@router.get("/me", response_model=UserOut)
async def get_me(
    current_user: User = Depends(get_current_user),  # ← injecte l'user connecté
):
    return current_user

@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden access"
        )
    return current_user

@router.get("", response_model=list[UserOut])
async def list_users(
        session: AsyncSession = Depends(get_session)
):
    result = await session.execute(select(User).order_by(User.email))
    return result.scalars().all()

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
        user_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden access")

    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    await session.delete(user)
    await session.commit()