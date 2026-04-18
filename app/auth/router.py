import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, RefreshRequest
from app.auth.service import AuthService
from app.auth.depends import get_current_user
from app.auth.security import decode_token
from app.config import settings
from app.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    try:
        user = await svc.register(body.login, body.password, body.email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    access, refresh = await svc._issue_tokens(user)
    response.set_cookie("access_token", access, httponly=True, samesite="lax")
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax")
    return TokenResponse(access_token=access)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    try:
        access, refresh = await svc.login(body.login, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    response.set_cookie("access_token", access, httponly=True, samesite="lax")
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax")
    return TokenResponse(access_token=access)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, response: Response, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    try:
        access, refresh = await svc.refresh(body.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    response.set_cookie("access_token", access, httponly=True, samesite="lax")
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax")
    return TokenResponse(access_token=access)


@router.post("/logout")
async def logout(request: Request, response: Response, user: User = Depends(get_current_user)):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        payload = decode_token(refresh_token)
        if payload:
            session_id = payload.get("session_id", "")
            from app.redis_client import redis_client
            await redis_client.delete(f"refresh:{session_id}")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"detail": "Logged out"}


# ── GitHub OAuth ──────────────────────────────────────────────────────────────

@router.get("/github")
async def github_login():
    params = f"client_id={settings.github_client_id}&redirect_uri={settings.github_redirect_uri}&scope=user:email"
    return RedirectResponse(f"{GITHUB_AUTHORIZE_URL}?{params}")


@router.get("/github/callback")
async def github_callback(code: str, response: Response, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": settings.github_redirect_uri,
            },
        )
        token_data = token_resp.json()
        gh_access = token_data.get("access_token")
        if not gh_access:
            raise HTTPException(status_code=400, detail="GitHub OAuth failed")

        # Fetch user info
        user_resp = await client.get(
            GITHUB_USER_URL,
            headers={"Authorization": f"Bearer {gh_access}", "Accept": "application/json"},
        )
        gh_user = user_resp.json()

    svc = AuthService(db)
    user = await svc.get_or_create_github_user(
        github_id=str(gh_user["id"]),
        login=gh_user.get("login", f"gh_{gh_user['id']}"),
        email=gh_user.get("email"),
    )
    access, refresh = await svc._issue_tokens(user)
    resp = RedirectResponse(url="/chats", status_code=302)
    resp.set_cookie("access_token", access, httponly=True, samesite="lax")
    resp.set_cookie("refresh_token", refresh, httponly=True, samesite="lax")
    return resp
