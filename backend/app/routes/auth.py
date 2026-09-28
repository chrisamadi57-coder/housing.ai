"""Authentication routes: register, login, refresh, profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.user import (
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserLogin,
    UserPasswordChange,
    UserRead,
    UserUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    return await AuthService(db).register(payload)


@router.post("/login", response_model=TokenPair)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenPair:
    return await AuthService(db).login(payload)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    return await AuthService(db).refresh(payload.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(current: User = Depends(get_current_user)) -> User:
    return current


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> User:
    return await AuthService(db).update_profile(current, payload)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: UserPasswordChange,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> MessageResponse:
    await AuthService(db).change_password(current, payload)
    return MessageResponse(message="Password updated")