"""Auth router — thin controllers, one service call per endpoint."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, RefreshRequest
from app.auth.service import AuthService
from app.auth.depends import get_current_user
from app.auth.security import decode_token
from app.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    try:
        user = await svc.register(body.login, body.password, body.email)
        access, refresh = await svc._issue_tokens(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _set_auth_cookies(response, access, refresh)
    return TokenResponse(access_token=access)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    try:
        access, refresh = await svc.login(body.login, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    _set_auth_cookies(response, access, refresh)
    return TokenResponse(access_token=access)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, response: Response, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    try:
        access, refresh = await svc.refresh(body.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    _set_auth_cookies(response, access, refresh)
    return TokenResponse(access_token=access)


@router.post("/logout")
async def logout(request: Request, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        payload = decode_token(refresh_token)
        if payload:
            await svc.logout(payload.get("session_id", ""))
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"detail": "Logged out"}


# ── GitHub OAuth ──────────────────────────────────────────────────────────────

@router.get("/github")
async def github_login():
    """Redirect browser to GitHub authorization page."""
    from app.config import settings
    params = (
        f"client_id={settings.github_client_id}"
        f"&redirect_uri={settings.github_redirect_uri}"
        f"&scope=user:email"
    )
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@router.get("/github/callback")
async def github_callback(code: str, response: Response, db: AsyncSession = Depends(get_db)):
    """Handle GitHub OAuth callback — all logic delegated to AuthService."""
    svc = AuthService(db)
    try:
        access, refresh = await svc.github_oauth_callback(code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    resp = RedirectResponse(url="/chats", status_code=302)
    _set_auth_cookies(resp, access, refresh)
    return resp


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie("access_token", access, httponly=True, samesite="lax")
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax")
