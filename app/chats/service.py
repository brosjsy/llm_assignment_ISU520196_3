"""Chat service — all chat and LLM orchestration logic lives here."""
import json
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.chats.models import Chat, Message
from app.chats.schemas import MessageResponse
from app.users.models import User
from app.redis_client import redis_client

CACHE_TTL = 300  # 5 minutes


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Chat CRUD ─────────────────────────────────────────────────────────────

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

    async def update_chat_title(self, chat: Chat, title: str) -> Chat:
        chat.title = title
        await self.db.commit()
        await self.db.refresh(chat)
        return chat

    # ── Messages ──────────────────────────────────────────────────────────────

    async def add_message(self, chat_id: int, role: str, content: str) -> Message:
        msg = Message(chat_id=chat_id, role=role, content=content)
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        await redis_client.delete(f"chat_messages:{chat_id}")
        return msg

    async def get_messages_cached(self, chat_id: int) -> list[dict]:
        """Return message list from Redis cache, falling back to DB."""
        cache_key = f"chat_messages:{chat_id}"
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        result = await self.db.execute(
            select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at)
        )
        messages = result.scalars().all()
        data = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]
        await redis_client.setex(cache_key, CACHE_TTL, json.dumps(data))
        return data

    # ── LLM orchestration ────────────────────────────────────────────────────

    async def ask(self, chat_id: int, user: User, content: str) -> MessageResponse:
        """
        Full non-streaming LLM turn:
        1. Validate chat ownership
        2. Auto-title on first message
        3. Persist user message
        4. Fetch history (cached)
        5. Generate LLM answer
        6. Persist assistant message
        7. Return assistant MessageResponse
        """
        from app.llm.service import LLMService

        chat = await self.get_chat(chat_id, user)
        if not chat:
            raise ValueError("Chat not found")

        if not chat.messages and chat.title == "New Chat":
            await self.update_chat_title(chat, content[:40])

        await self.add_message(chat_id, "user", content)
        history = await self.get_messages_cached(chat_id)

        llm = LLMService()
        answer = llm.generate(llm.build_prompt(history))
        msg = await self.add_message(chat_id, "assistant", answer)
        return MessageResponse.model_validate(msg)

    async def ask_stream(
        self, chat_id: int, user: User, content: str
    ) -> AsyncGenerator[str, None]:
        """
        Streaming LLM turn — yields SSE-formatted strings.
        1. Validate chat ownership
        2. Auto-title on first message
        3. Persist user message
        4. Fetch history (cached)
        5. Stream LLM tokens (yields SSE data lines)
        6. Persist full assistant response
        7. Yield [DONE] sentinel
        """
        from app.llm.service import LLMService

        chat = await self.get_chat(chat_id, user)
        if not chat:
            raise ValueError("Chat not found")

        if not chat.messages and chat.title == "New Chat":
            await self.update_chat_title(chat, content[:40])

        await self.add_message(chat_id, "user", content)
        history = await self.get_messages_cached(chat_id)

        llm = LLMService()
        prompt = llm.build_prompt(history)

        collected: list[str] = []
        for token in llm.generate_streaming(prompt):
            collected.append(token)
            yield f"data: {token}\n\n"

        answer = "".join(collected)
        await self.add_message(chat_id, "assistant", answer)
        yield "data: [DONE]\n\n"
