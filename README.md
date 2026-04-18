# WAD Chat — Homework Project

A ChatGPT-like LLM chat application built with **FastAPI**, **PostgreSQL**, **Redis**, **JWT auth**, **GitHub OAuth**, and a local **llama-cpp** model.

---

## Architecture

This project uses **MVC (Model–View–Controller)** with **server-rendered HTML** (Jinja2 templates).

| Layer | Location | Role |
|-------|----------|------|
| **Models** | `app/users/models.py`, `app/chats/models.py` | SQLAlchemy ORM tables |
| **Views** | `templates/` | Jinja2 HTML templates |
| **Controllers** | `app/auth/router.py`, `app/chats/router.py` | FastAPI route handlers |
| **Services** | `app/auth/service.py`, `app/chats/service.py` | Business logic |

---

## Stack

- **Python 3.11+** / **FastAPI** — async REST + server-rendered views
- **PostgreSQL** — primary database (via SQLAlchemy async + asyncpg)
- **Alembic** — database migrations
- **Redis** — refresh token sessions (TTL 30 days) + chat message cache (TTL 5 min)
- **JWT** — access + refresh token flow (python-jose)
- **bcrypt** — password hashing (passlib)
- **GitHub OAuth** — social login
- **llama-cpp-python** — local GGUF LLM inference with SSE streaming

---

## Prerequisites

- Python 3.11+
- Docker & Docker Compose (for Postgres + Redis)
- A GGUF model file (e.g. `tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf`)
- A GitHub OAuth App (for social login)

---

## Quick Start

### 1. Clone / set up the repo

```bash
git clone https://github.com/<your-username>/wad-homework.git
cd wad-homework
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# macOS / Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `llama-cpp-python` may need a C++ compiler. On Ubuntu: `sudo apt install build-essential`. On macOS it works with Xcode CLT.

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/wad_chat
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-very-secret-key-here
GITHUB_CLIENT_ID=<from GitHub OAuth App>
GITHUB_CLIENT_SECRET=<from GitHub OAuth App>
GITHUB_REDIRECT_URI=http://localhost:8000/auth/github/callback
MODEL_PATH=model.gguf
```

### 5. Start Postgres and Redis

```bash
docker compose up -d
```

### 6. Run database migrations

```bash
alembic upgrade head
```

### 7. Place your LLM model file

Download a GGUF model (e.g. TinyLlama or Mistral Q4) and place it in the project root:

```bash
# Example — download TinyLlama (637 MB):
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf -O model.gguf
```

Set `MODEL_PATH=model.gguf` in `.env`.

> **Note:** The app works without a model — it returns a placeholder message. You can test all other features (auth, chats, Redis, DB) without a GGUF file.

### 8. Start the application

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open your browser at **http://localhost:8000**

---

## GitHub OAuth Setup

1. Go to https://github.com/settings/developers → **OAuth Apps** → **New OAuth App**
2. Set:
   - **Homepage URL:** `http://localhost:8000`
   - **Authorization callback URL:** `http://localhost:8000/auth/github/callback`
3. Copy **Client ID** and **Client Secret** into `.env`

---

## API Overview

All API endpoints are prefixed with `/api` and return JSON. Protected routes require a JWT either in the `Authorization: Bearer <token>` header or in the `access_token` cookie.

### Auth (`/auth`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Register with login + password |
| POST | `/auth/login` | Login, receive access + refresh tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Invalidate session (deletes Redis key) |
| GET | `/auth/github` | Redirect to GitHub OAuth |
| GET | `/auth/github/callback` | GitHub OAuth callback |

### Chats (`/api/chats`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/chats` | List user's chats |
| POST | `/api/chats` | Create a new chat |
| GET | `/api/chats/{id}` | Get chat with messages |
| DELETE | `/api/chats/{id}` | Delete a chat |
| POST | `/api/chats/{id}/ask` | Send a message, get LLM response (non-streaming) |
| GET | `/api/chats/{id}/stream?content=...` | SSE streaming LLM response |

### Interactive Docs

Available at **http://localhost:8000/docs** (Swagger UI) when the server is running.

---

## Database Schema

```
users
├── id (PK)
├── login (unique, not null)
├── email (nullable)
├── hashed_password (nullable — null for GitHub-only users)
├── github_id (unique, nullable)
├── is_active
└── created_at

chats
├── id (PK)
├── title
├── user_id (FK → users.id)
└── created_at

messages
├── id (PK)
├── chat_id (FK → chats.id)
├── role  ("user" | "assistant")
├── content
└── created_at
```

---

## JWT + Refresh Token + Redis Flow

1. On login/register, the server issues:
   - **Access token** (30 min TTL) — sent as cookie + JSON response
   - **Refresh token** (30 days TTL) — sent as httpOnly cookie
2. Refresh token session stored in Redis as `refresh:<session_uuid>` → `user_id`
3. On `/auth/refresh`, the old Redis key is deleted and new tokens are issued (rotation)
4. On `/auth/logout`, the Redis key is deleted immediately

---

## Project Structure

```
wad-homework/
├── app/
│   ├── auth/
│   │   ├── depends.py      # get_current_user FastAPI dependency
│   │   ├── router.py       # auth endpoints + GitHub OAuth
│   │   ├── schemas.py      # Pydantic request/response models
│   │   ├── security.py     # JWT, bcrypt helpers
│   │   └── service.py      # register, login, refresh business logic
│   ├── chats/
│   │   ├── models.py       # Chat, Message ORM models
│   │   ├── router.py       # HTML views + REST API endpoints
│   │   ├── schemas.py      # Pydantic schemas
│   │   └── service.py      # CRUD + Redis cache logic
│   ├── llm/
│   │   └── service.py      # llama-cpp wrapper, streaming generator
│   ├── users/
│   │   └── models.py       # User ORM model
│   ├── config.py           # pydantic-settings config
│   ├── database.py         # async SQLAlchemy engine + session
│   ├── main.py             # FastAPI app, router registration
│   └── redis_client.py     # Redis async client
├── alembic/
│   ├── versions/
│   │   └── 0001_initial.py # Initial migration (users, chats, messages)
│   ├── env.py
│   └── script.py.mako
├── templates/
│   ├── base.html
│   ├── auth/login.html
│   └── chats/
│       ├── list.html
│       └── detail.html
├── static/css/style.css
├── alembic.ini
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Uploading to GitHub (Step-by-Step)

### Step 1 — Create a new GitHub repository

Go to https://github.com/new and create a **new empty repository** (do NOT add README or .gitignore on GitHub).

### Step 2 — Initialize git locally

Run these commands in your project folder:

```bash
cd wad-homework

git init
git add .
git commit -m "Initial commit: WAD homework — FastAPI LLM chat app"
```

### Step 3 — Connect to GitHub and push

```bash
git remote add origin https://github.com/<your-username>/<repo-name>.git
git branch -M main
git push -u origin main
```

### Step 4 — Verify

Visit `https://github.com/<your-username>/<repo-name>` — all files should be visible.

### Step 5 — Share with professor

Send the professor the link: `https://github.com/<your-username>/<repo-name>`

---

## All Commands — Complete Reference

```bash
# ── Environment ──────────────────────────────────────
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
.venv\Scripts\activate             # Windows

pip install -r requirements.txt

cp .env.example .env               # then edit .env

# ── Services ─────────────────────────────────────────
docker compose up -d               # start Postgres + Redis
docker compose down                # stop services
docker compose logs -f             # view service logs

# ── Database ─────────────────────────────────────────
alembic upgrade head               # apply all migrations
alembic downgrade base             # roll back all migrations
alembic revision --autogenerate -m "description"  # create new migration

# ── Run App ──────────────────────────────────────────
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ── Git / GitHub ─────────────────────────────────────
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/<user>/<repo>.git
git branch -M main
git push -u origin main

# Subsequent updates:
git add .
git commit -m "Your message"
git push
```
