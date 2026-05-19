# WAD Chat — LLM Chat Application

A ChatGPT-like chat application built with **FastAPI**, **PostgreSQL**, **Redis**, **JWT** auth, **GitHub OAuth**, and a **local GGUF LLM** (via `llama-cpp-python`).

---

## Architecture

**UI mode:** Server-rendered HTML (Jinja2 templates)  
**Pattern:** MVC — Models · Views (templates) · Controllers (routers call one service method each)

```
app/
├── auth/
│   ├── depends.py      # FastAPI dependency — extract user from JWT
│   ├── router.py       # Controllers (thin — one svc call per endpoint)
│   ├── schemas.py      # Pydantic request/response models
│   ├── security.py     # JWT creation/verification, password hashing
│   └── service.py      # All auth logic: register, login, refresh, GitHub OAuth
├── chats/
│   ├── models.py       # SQLAlchemy ORM: Chat, Message
│   ├── router.py       # Controllers (thin — one svc call per endpoint)
│   ├── schemas.py      # Pydantic request/response models
│   └── service.py      # Chat CRUD + LLM orchestration (ask, ask_stream)
├── llm/
│   └── service.py      # LLMService: wraps llama-cpp-python, build_prompt
├── users/
│   └── models.py       # SQLAlchemy ORM: User
├── config.py           # Pydantic Settings (reads .env)
├── database.py         # Async SQLAlchemy engine + session factory
├── main.py             # FastAPI app, router registration
└── redis_client.py     # Shared async Redis client
templates/              # Jinja2 HTML views (base, auth/login, chats/list, chats/detail)
static/css/style.css    # Dark-theme UI
alembic/                # DB migration scripts
```

**JWT + Redis flow:**
- On login/register/GitHub OAuth → access token (30 min) + refresh token (30 days) issued.
- Refresh token `session_id` is stored in Redis with a 30-day TTL.
- Refresh endpoint validates the Redis entry and rotates the session (deletes old, creates new).
- Logout deletes the Redis key, invalidating the session server-side immediately.

---

## Prerequisites

- Python 3.11+
- Docker & Docker Compose (for PostgreSQL + Redis)
- A GGUF model file (e.g. `qwen.gguf`) — place it in the project root
- A GitHub OAuth App (for GitHub login)

---

## Quick Start

### 1. Clone & enter the project

```bash
git clone https://github.com/brosjsy/llm_assignment_ISU520196_3.git
cd llm_assignment_ISU520196_3
```

### 2. Start PostgreSQL and Redis

```bash
docker-compose up -d
```

### 3. Create and activate a virtual environment

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note on `llama-cpp-python` on Windows:** if `pip install` fails, use the pre-built CPU wheel:
> ```bash
> pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
> ```

### 5. Place the GGUF model

Copy your model file to the project root:

```bash
cp /path/to/your/model.gguf ./model.gguf
```

Or point `MODEL_PATH` in `.env` to any path (e.g. `MODEL_PATH=qwen.gguf`).

### 6. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/wad_chat
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-very-secret-key-change-me
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=http://localhost:8000/auth/github/callback
MODEL_PATH=model.gguf
```

**GitHub OAuth App setup:**
1. Go to https://github.com/settings/developers → **New OAuth App**
2. Homepage URL: `http://localhost:8000`
3. Authorization callback URL: `http://localhost:8000/auth/github/callback`
4. Copy **Client ID** and **Client Secret** into `.env`

### 7. Run database migrations

```bash
alembic upgrade head
```

### 8. Start the application

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | — | Register with login + password |
| `POST` | `/auth/login` | — | Login, receive JWT pair in cookies |
| `POST` | `/auth/refresh` | — | Rotate refresh token |
| `POST` | `/auth/logout` | JWT | Invalidate session in Redis |
| `GET` | `/auth/github` | — | Redirect to GitHub OAuth |
| `GET` | `/auth/github/callback` | — | GitHub OAuth callback handler |
| `GET` | `/api/chats` | JWT | List all chats for the current user |
| `POST` | `/api/chats` | JWT | Create a new chat |
| `GET` | `/api/chats/{id}` | JWT | Get a chat with its messages |
| `DELETE` | `/api/chats/{id}` | JWT | Delete a chat |
| `POST` | `/api/chats/{id}/ask` | JWT | Send a message, get LLM reply |
| `GET` | `/api/chats/{id}/stream?content=…` | JWT | SSE streaming LLM reply |

Interactive API docs (Swagger UI): **http://localhost:8000/docs**

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/wad_chat` | Async PostgreSQL URL |
| `REDIS_URL` | `redis://localhost:6379` | Redis URL |
| `SECRET_KEY` | `changeme-secret` | JWT signing key — **change in production** |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime (minutes) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token lifetime / Redis TTL (days) |
| `GITHUB_CLIENT_ID` | — | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | — | GitHub OAuth App client secret |
| `GITHUB_REDIRECT_URI` | `http://localhost:8000/auth/github/callback` | Must match GitHub App settings |
| `MODEL_PATH` | `model.gguf` | Relative or absolute path to GGUF model file |

---

## Bonus Features Implemented

- **Streaming LLM output** — tokens arrive incrementally via SSE; the UI renders them live with a blinking cursor (`▋`)
- **Chat history caching** — message lists cached in Redis for 5 minutes, invalidated on new message or chat deletion
- **Auto-title** — the first user message (up to 40 chars) becomes the chat title automatically
