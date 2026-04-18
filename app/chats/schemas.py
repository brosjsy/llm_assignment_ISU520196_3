from datetime import datetime
from pydantic import BaseModel


class ChatCreate(BaseModel):
    title: str = "New Chat"


class ChatResponse(BaseModel):
    id: int
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatDetail(ChatResponse):
    messages: list[MessageResponse] = []


class AskRequest(BaseModel):
    content: str
