# Job-Bot

AI-powered job scouting, CV generation, and application orchestration agent.

## Architecture

- **Backend**: FastAPI + Pydantic v2, ChatGPT access via Codex CLI device-auth (no API keys)
- **Frontend**: Vite 6 + React 19 SPA with dark glassmorphism design
- **Storage**: Local JSON files (Supabase Postgres planned for SaaS)
- **AI**: Codex harness using `codex exec --ephemeral --sandbox read-only`

## Quick Start

```bash
# Install Python dependencies + pre-commit hooks
make install

# Start development servers (backend :8000, frontend :5173)
make dev

# Run linters
make lint

# Run tests
make test
```

## Codex Login

The bot authenticates via Codex device-auth flow — no OpenAI API key needed:

```bash
# The frontend triggers this, or run manually:
codex login
```

Follow the URL and enter the one-time code in your browser to authenticate.

## Project Structure

```
job-bot/
├── backend/
│   ├── config.py              # Pydantic Settings
│   ├── models/                # Pydantic request/response schemas
│   │   ├── profile.py         # Master candidate profile
│   │   ├── job.py             # Job listings + search
│   │   ├── cv.py              # CV generation + ATS scoring
│   │   ├── operation.py       # Async operation tracking
│   │   └── application.py     # Application pipeline
│   └── services/
│       ├── codex_harness.py   # Codex CLI subprocess manager
│       ├── ai_client.py       # Provider-agnostic AI wrapper
│       ├── profile_service.py # Profile parsing + persistence
│       └── storage.py         # User-scoped JSON repository
├── frontend/                  # Vite + React SPA
├── tests/                     # pytest suite
├── pyproject.toml
├── Makefile
└── .pre-commit-config.yaml
```
