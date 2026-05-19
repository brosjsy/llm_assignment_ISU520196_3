"""Chats router — thin controllers, one service call per endpoint."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.depends import get_current_user, get_current_user_optional
from app.chats.service import ChatService
from app.chats.schemas import ChatCreate, ChatResponse, ChatDetail, AskRequest, MessageResponse
from app.users.models import User

router = APIRouter(tags=["chats"])
templates = Jinja2Templates(directory="templates")


# ── HTML Views ────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: Optional[User] = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/chats")
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.get("/chats", response_class=HTMLResponse)
async def chats_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ChatService(db)
    chats = await svc.get_user_chats(user)
    return templates.TemplateResponse(
        "chats/list.html", {"request": request, "user": user, "chats": chats}
    )


@router.get("/chats/{chat_id}", response_class=HTMLResponse)
async def chat_detail_page(
    chat_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ChatService(db)
    chat = await svc.get_chat(chat_id, user)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    all_chats = await svc.get_user_chats(user)
    return templates.TemplateResponse(
        "chats/detail.html",
        {"request": request, "user": user, "chat": chat, "chats": all_chats},
    )


# ── REST API ──────────────────────────────────────────────────────────────────

@router.get("/api/chats", response_model=list[ChatResponse])
async def api_list_chats(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    svc = ChatService(db)
    return await svc.get_user_chats(user)


@router.post("/api/chats", response_model=ChatResponse, status_code=201)
async def api_create_chat(
    body: ChatCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ChatService(db)
    return await svc.create_chat(user, body.title)


@router.get("/api/chats/{chat_id}", response_model=ChatDetail)
async def api_get_chat(
    chat_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ChatService(db)
    chat = await svc.get_chat(chat_id, user)
    if not chat:
        raise HTTPException(status_code=404)
    return chat


@router.delete("/api/chats/{chat_id}", status_code=204)
async def api_delete_chat(
    chat_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ChatService(db)
    deleted = await svc.delete_chat(chat_id, user)
    if not deleted:
        raise HTTPException(status_code=404)


@router.post("/api/chats/{chat_id}/ask", response_model=MessageResponse)
async def api_ask(
    chat_id: int,
    body: AskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Non-streaming LLM turn — returns the assistant message."""
    svc = ChatService(db)
    try:
        return await svc.ask(chat_id, user, body.content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/chats/{chat_id}/stream")
async def api_ask_stream(
    chat_id: int,
    content: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming endpoint — yields tokens as they are generated."""
    svc = ChatService(db)
    try:
        generator = svc.ask_stream(chat_id, user, content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return StreamingResponse(generator, media_type="text/event-stream")
