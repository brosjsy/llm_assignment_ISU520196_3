import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.chats.models import Chat, Message
from app.users.models import User
from app.redis_client import redis_client

CACHE_TTL = 300  # 5 minutes


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_chats(self, user: User) -> list[Chat]:
        result = await self.db.execute(
            select(Chat).where(Chat.user_id == user.id).order_by(Chat.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_chat(self, user: User, title: str = "New Chat") -> Chat:
        chat = Chat(user_id=user.id, title=title)
        self.db.add(chat)
        await self.db.commit()
        await self.db.refresh(chat)
        return chat

    async def get_chat(self, chat_id: int, user: User) -> Optional[Chat]:
        result = await self.db.execute(
            select(Chat)
            .where(Chat.id == chat_id, Chat.user_id == user.id)
            .options(selectinload(Chat.messages))
        )
        return result.scalar_one_or_none()

    async def delete_chat(self, chat_id: int, user: User) -> bool:
        chat = await self.get_chat(chat_id, user)
        if not chat:
            return False
        await self.db.delete(chat)
        await self.db.commit()
        await redis_client.delete(f"chat_messages:{chat_id}")
        return True

    async def add_message(self, chat_id: int, role: str, content: str) -> Message:
        msg = Message(chat_id=chat_id, role=role, content=content)
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        # Invalidate cache
        await redis_client.delete(f"chat_messages:{chat_id}")
        return msg

    async def get_messages_cached(self, chat_id: int) -> list[dict]:
        cache_key = f"chat_messages:{chat_id}"
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        result = await self.db.execute(
            select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at)
        )
        messages = result.scalars().all()
        data = [{"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in messages]
        await redis_client.setex(cache_key, CACHE_TTL, json.dumps(data))
        return data

    async def update_chat_title(self, chat: Chat, title: str) -> Chat:
        chat.title = title
        await self.db.commit()
        await self.db.refresh(chat)
        return chat
