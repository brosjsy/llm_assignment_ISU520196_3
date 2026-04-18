# Homework Project Submission Report: WAD Chat

This report documents the architecture, implementation, and features of the WAD Chat project, an LLM-powered conversation platform.

## 🚀 Project Overview
WAD Chat is a ChatGPT-like experience that allows users to create persistent conversation threads with a local LLM. It features a complete authentication system with social login support and high-performance caching.

## 🏗 Architecture
The project follows the **MVC (Model-View-Controller)** architecture, utilizing server-rendered HTML for maximum compatibility and performance.

| Layer | Responsibility |
| :--- | :--- |
| **Model** | SQLAlchemy models (`app/users/models.py`, `app/chats/models.py`) define the data structure and relationships. |
| **View** | Jinja2 templates (`templates/`) handle the rendering of the user interface. |
| **Controller** | FastAPI routers (`app/auth/router.py`, `app/chats/router.py`) handle HTTP requests, validate input, and interface with services. |
| **Service** | Business logic is encapsulated in service layers (`app/auth/service.py`, `app/chats/service.py`) to keep controllers thin. |

## 🔑 Authentication & Security
### JWT flow with Redis
The application implements a robust JWT-based access/refresh token flow:
- **Access Tokens**: Short-lived (30 min) JWTs stored in HTTP-only cookies for authenticating requests.
- **Refresh Tokens**: Long-lived (30 days) tokens stored in **Redis** with a TTL.
- **GitHub OAuth**: Supports social login alongside standard registration.
- **Password Hashing**: Uses **Argon2**, the modern winner of the Password Hashing Competition, to allow arbitrary password lengths and ensure maximum security.

## 📡 API Structure
The API is divided into resource-based groups:

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| **POST** | `/auth/register` | Register a new user | No |
| **POST** | `/auth/login` | Login with credentials | No |
| **POST** | `/auth/refresh` | Refresh JWT tokens | Yes |
| **GET** | `/api/chats` | List user's chats | Yes |
| **POST** | `/api/chats` | Create a new chat | Yes |
| **GET** | `/api/chats/{id}/stream` | SSE stream for LLM response | Yes |

## 🗄 Database Schema
The project uses **PostgreSQL** with the following relational structure:

### Tables
1. **`users`**: Stores user credentials, email, and GitHub IDs.
2. **`chats`**: Stores conversation threads linked to users.
3. **`messages`**: Stores individual messages (user/assistant) within chats.

### Relationships
- `User` -> `Chat` (One-to-Many)
- `Chat` -> `Message` (One-to-Many, cascade deletes)

## ✨ Bonus Features
1. **Incremental Streaming**: LLM responses are streamed via **Server-Sent Events (SSE)**, providing a real-time "typing" experience in the UI.
2. **Redis Caching**: Chat history and refresh sessions are cached in Redis to minimize database latency and load.
3. **Modern Styling**: A dark-themed, glassmorphic UI designed for a premium user experience.

---
*Report generated for WAD Homework Project Submission - 2026*
