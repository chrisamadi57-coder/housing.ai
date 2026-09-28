"""Auth service: register, login, refresh, profile updates."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError, ValidationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import (
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserLogin,
    UserPasswordChange,
    UserUpdate,
)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    async def _get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        return await self.db.scalar(stmt)

    async def _get_by_id(self, user_id) -> User | None:
        return await self.db.get(User, user_id)

    def _issue_tokens(self, user: User) -> TokenPair:
        return TokenPair(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def register(self, payload: UserCreate) -> User:
        if await self._get_by_email(payload.email):
            raise ConflictError("Email already registered")

        user = User(
            email=payload.email.lower(),
            full_name=payload.full_name,
            phone=payload.phone,
            avatar_url=payload.avatar_url,
            bio=payload.bio,
            hashed_password=hash_password(payload.password),
            # Only admins can create admins — enforced in the route, not here.
            role=payload.role or UserRole.USER,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def login(self, payload: UserLogin) -> TokenPair:
        user = await self._get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.hashed_password):
            # Same message for both cases — don't leak which emails exist.
            raise UnauthorizedError("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedError("Account is inactive")
        return self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> TokenPair:
        try:
            payload = decode_token(refresh_token)
        except ValueError as e:
            raise UnauthorizedError("Invalid refresh token") from e

        if payload.get("type") != "refresh":
            raise UnauthorizedError("Not a refresh token")

        user = await self._get_by_id(payload["sub"])
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or inactive")

        return self._issue_tokens(user)

    async def update_profile(self, actor: User, payload: UserUpdate) -> User:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(actor, field, value)
        await self.db.commit()
        await self.db.refresh(actor)
        return actor

    async def change_password(self, actor: User, payload: UserPasswordChange) -> None:
        if not verify_password(payload.current_password, actor.hashed_password):
            raise ValidationError("Current password is incorrect")
        actor.hashed_password = hash_password(payload.new_password)
        await self.db.commit()