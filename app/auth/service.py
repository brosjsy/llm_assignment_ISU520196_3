import uuid
from datetime import timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.users.models import User
from app.auth.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.redis_client import redis_client
from app.config import settings


REFRESH_TTL = int(timedelta(days=settings.refresh_token_expire_days).total_seconds())


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, login: str, password: str, email: Optional[str] = None) -> User:
        result = await self.db.execute(select(User).where(User.login == login))
        if result.scalar_one_or_none():
            raise ValueError("Login already taken")

        user = User(login=login, hashed_password=hash_password(password), email=email)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def login(self, login: str, password: str) -> tuple[str, str]:
        result = await self.db.execute(select(User).where(User.login == login))
        user = result.scalar_one_or_none()
        if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid credentials")

        return await self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")

        session_id = payload.get("session_id")
        stored = await redis_client.get(f"refresh:{session_id}")
        if not stored or stored != str(payload["sub"]):
            raise ValueError("Session expired or invalid")

        result = await self.db.execute(select(User).where(User.id == int(payload["sub"])))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        # Rotate: delete old session, issue new
        await redis_client.delete(f"refresh:{session_id}")
        return await self._issue_tokens(user)

    async def logout(self, session_id: str) -> None:
        await redis_client.delete(f"refresh:{session_id}")

    async def get_or_create_github_user(self, github_id: str, login: str, email: Optional[str]) -> User:
        result = await self.db.execute(select(User).where(User.github_id == github_id))
        user = result.scalar_one_or_none()
        if user:
            return user

        # Check login uniqueness, append suffix if needed
        base_login = login
        suffix = 0
        while True:
            check = await self.db.execute(select(User).where(User.login == login))
            if not check.scalar_one_or_none():
                break
            suffix += 1
            login = f"{base_login}{suffix}"

        user = User(github_id=github_id, login=login, email=email)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def _issue_tokens(self, user: User) -> tuple[str, str]:
        session_id = str(uuid.uuid4())
        access = create_access_token({"sub": str(user.id), "login": user.login})
        refresh = create_refresh_token({"sub": str(user.id), "session_id": session_id})
        await redis_client.setex(f"refresh:{session_id}", REFRESH_TTL, str(user.id))
        return access, refresh
