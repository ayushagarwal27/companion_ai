# WorldWiseAI

> A LangGraph-based conversational agent that acts as a friendly, knowledgeable
> guide for learning about the world's countries, with persistent long-term
> memory per user across sessions — backed by a Redis checkpointer for live
> conversation state and a Postgres/pgvector store for durable, cross-session
> facts.

![WorldWiseAI landing page](images/landing.png)

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-green.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-orange.svg)](https://langchain-ai.github.io/langgraph)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000.svg)](https://nextjs.org)
[![Docker](https://img.shields.io/badge/Docker-Traefik-2496ED.svg)](https://www.docker.com)

---

## Table of Contents

- [Project Description](#project-description)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Running](#running)
- [Frontend](#frontend)
- [API Documentation](#api-documentation)
- [Deployment](#deployment)

---

## Project Description

WorldWiseAI is a chat agent that plays friendly, knowledgeable assistant for
learning about a specific country — its history, culture, geography, and
customs — remembering who you are across every future conversation instead of
forgetting you the moment the session ends.

**The problem it solves:** a chatbot that forgets you between sessions has to
relearn your interests, knowledge level, and past questions every single time
— which makes long-running, personal use cases (an ongoing study companion,
a curious learner coming back to the same country over weeks) feel shallow.
WorldWiseAI separates *short-term* conversation state from *long-term*
per-user memory, so a brand-new session for a returning user still knows what
they said weeks ago.

**What makes it different:**

- **Two-tier memory** — a Redis checkpointer holds the live conversation
  (messages, rolling summary, turn counters) per `session_id`; a Postgres +
  pgvector store holds durable, semantically-searchable facts per `user_id`
  that persist across every future session
- **Non-blocking memory writes** — extraction always runs via `BackgroundTasks`,
  scheduled during the request but executed *after* the response is already
  sent, so memory never adds latency to a reply
- **Four independent triggers, same memory flush** — periodic (every N turns),
  on summarization, on explicit session end, and on idle-session expiry — so
  memory is captured whether a session is long, short, or abandoned mid-chat
- **Idle-session backstop via Redis keyspace events** — no polling, no cron: a
  Redis key TTL expiry notifies a listener to flush any session a client never
  explicitly closed

---

## Features

### Country-Focused Learning Assistant

- One LangGraph agent per conversation, scoped to a `country` set at session start
- Persona + a rolling conversation `summary` + long-term memory for the
  `user_id` are composed into every prompt

### Two-Tier Memory System

| Layer | Store | Scope | Lifetime |
| --- | --- | --- | --- |
| Short-term | Redis (LangGraph checkpointer) | per `session_id` | cleared when the session ends |
| Long-term | Postgres + pgvector (LangGraph store) | per `user_id` | durable, across every future session |

- **Semantic** facts about the user are written additively
- A returning `user_id` starting a **new** `session_id` still benefits from
  everything learned in prior sessions — short-term state never carries over,
  long-term memory is what bridges sessions

### Automatic Summarization

- Once a session passes `history_summarize_trigger` messages (default 10),
  everything except the last `history_keep_last_n` (default 6) is archived
  into a running `summary` and removed from the checkpoint via `RemoveMessage`
  — keeping prompt size bounded in long conversations

### Four-Way Memory Flush Guarantee

- Periodic (every `memory_extraction_every_n_turns` turns), on summarization,
  on explicit `POST /chat/{session_id}/end`, and on idle-session TTL expiry —
  overlapping triggers can double-write facts, which is cheap and preferred
  over silently losing them

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Language | Python 3.12 |
| Agent Framework | LangGraph + LangChain |
| LLM / Embeddings | OpenAI (`gpt-6-luna` + `text-embedding-3-small`) |
| API | FastAPI + Uvicorn |
| Frontend | Next.js 16 (React 19, TypeScript) + Tailwind CSS v4 |
| Short-term store | Redis Stack (via `langgraph-checkpoint-redis`, uses RediSearch) |
| Long-term store | PostgreSQL + pgvector (via `langgraph-checkpoint-postgres`) |
| Validation | Pydantic v2 / pydantic-settings |
| Package management | `uv` |
| Containerization | Docker (multi-service compose) |
| Reverse Proxy / TLS | Traefik (Docker labels, Let's Encrypt) |

---

## Architecture

```text
CLIENT (Next.js frontend)
        │
        ▼
POST /chat  (backend/api/server.py)
        │
        ▼
LANGGRAPH CONVERSATION GRAPH (backend/graph/, backend/agents/)
├── country_agent_node          (generates the user-visible reply)
├── maybe_extract_memory_node   (every N turns → long-term memory)
└── summarize_conversation_node (past history_summarize_trigger)
        │
        ├──────────────────────────────┐
        ▼                               ▼
SHORT-TERM MEMORY               LONG-TERM MEMORY
Redis checkpointer               Postgres + pgvector store
(per session_id)                 (per user_id, cross-session)
├── messages                     └── semantic facts (additive,
├── summary                          embedded via OpenAI)
└── turns_since_extraction
        │
        ▼
IDLE-SESSION BACKSTOP (Redis keyspace-expiry listener)
└── flushes any pending memory a client never explicitly ended
```

### Conversation flow

```mermaid
flowchart LR
    START((START)) --> A["country_agent_node\ngenerate the reply"]
    A --> B["maybe_extract_memory_node\nevery N turns"]
    B --> C["summarize_conversation_node\npast history_summarize_trigger"]
    C --> END((END))

    style A fill:#4f8ff7,color:#fff,stroke:none
    style B fill:#f7b84f,color:#1a1a1a,stroke:none
    style C fill:#f76f6f,color:#fff,stroke:none
```

- **`country_agent_node`** — the only node that produces the user-visible reply. Prompt = persona + running `summary` + long-term memory for `user_id`.
- **`maybe_extract_memory_node`** — counts turns since the last extraction; at `memory_extraction_every_n_turns` (default 4) it extracts and resets the counter.
- **`summarize_conversation_node`** — past `history_summarize_trigger` messages (default 10), archives everything except the last `history_keep_last_n` (default 6) into `summary` and deletes them from the checkpoint via `RemoveMessage`.

### Memory architecture

```mermaid
flowchart TB
    subgraph ST["Short-term — Redis checkpointer (per session_id)"]
        direction LR
        M["messages"] ~~~ S["summary"] ~~~ T["turns_since_extraction"]
    end

    subgraph LT["Long-term — Postgres store (per user_id, cross-session)"]
        direction LR
        SEM["semantic facts\nembedded, additive"]
    end

    ST -- "extraction LLM call\n(background task)" --> LT
    LT -- "read on every turn" --> ST
```

Short-term state never crosses sessions — a new `session_id` starts empty even for
a returning `user_id`. Long-term memory is how a *new* session knows what the user
said in a *previous* one.

### Extraction triggers

Extraction always runs via `BackgroundTasks` — scheduled during the request,
executed *after* the response is already sent — never inline in `/chat`.

```mermaid
flowchart LR
    T1["Every N turns"] --> EX["finalize_pending_memory\n(background task)"]
    T2["Archived on summarize\n(safety net)"] --> EX
    T3["Client calls /end"] --> EX
    T4["Idle TTL expiry"] --> EX
    EX --> PG[("Postgres store")]
```

Triggers 1 and 2 can overlap and double-write facts — cheap, and preferred over
losing them. Triggers 3 and 4 exist for short sessions that never reach 1 or 2.

### Idle-session backstop

```mermaid
sequenceDiagram
    participant C as Client
    participant API as POST /chat
    participant R as Redis
    participant L as Idle listener

    C->>API: query (user_id, session_id)
    API->>R: SET session:alive:{id} EX 600
    API->>R: SET session:user:{id} EX 660
    Note over R: 600s pass, no new /chat call
    R-->>L: keyspace event: session:alive:{id} expired
    L->>R: GETDEL session:user:{id}
    L->>L: finalize pending memory (off event loop)
```

Requires Redis `notify-keyspace-events` to include `Ex` — the app sets this itself
on startup. If `CONFIG SET` is blocked (some managed Redis), this fails soft: a
warning is logged, and the periodic/explicit-end triggers still cover memory.

---

## Project Structure

```text
companion_ai/
├── backend/
│   ├── agents/
│   │   └── country_agent.py        # agent node + memory extraction/finalization
│   ├── api/
│   │   ├── server.py               # FastAPI app, lifespan, /chat, /chat/{id}/end
│   │   ├── dependency.py           # per-request compiled-graph dependency
│   │   └── models.py               # request/response Pydantic models
│   ├── config/
│   │   └── settings.py             # pydantic-settings, all env vars
│   ├── graph/
│   │   └── graph.py                # wires the LangGraph conversation graph
│   ├── prompts/
│   │   └── country_agent.py        # persona / system prompt
│   ├── state/
│   │   └── country_state.py        # LangGraph state schema
│   └── Dockerfile
│
├── frontend/                        # Next.js console
│   └── src/
│       ├── app/
│       │   ├── page.tsx            # landing page — pick a country
│       │   └── chat/               # chat page + client
│       ├── components/ui/          # shadcn/radix UI primitives
│       └── lib/                    # api client, countries list, user id helper
│
├── designs/                         # reference UI designs (not shipped)
├── images/                          # README screenshots
├── docker-compose.yml                # backend + Redis Stack, joins Traefik network
├── main.py                          # minimal placeholder app — NOT the entrypoint
├── pyproject.toml
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+ (for the frontend)
- A PostgreSQL 15+ instance with the `pgvector` extension (long-term memory)
- A reachable Redis instance that supports RediSearch (e.g. Redis Stack) —
  needed because `langgraph-checkpoint-redis` issues `FT.*` commands
- An OpenAI API key

### 1. Clone the repository

```bash
git clone <repo-url>
cd companion_ai
```

### 2. Install backend dependencies

```bash
uv sync
```

### 3. Configure environment variables

```bash
cp .env.example .env
# fill in OPENAI_API_KEY, DATABASE_URL, REDIS_URL — see below
```

### 4. Install frontend dependencies

```bash
cd frontend && npm install && cd ..
```

### 5. Run the app — see [Running](#running) below

---

## Environment Variables

Copy `.env.example` to `.env` and fill in every value:

```env
OPENAI_API_KEY=
DATABASE_URL=postgresql://user:password@host:5432/dbname
REDIS_URL=redis://host:6379/0

# Domain Traefik routes to this container (VPS only, unused by the app itself)
BACKEND_DOMAIN=

# pydantic-settings parses list fields as JSON:
FRONTEND_ORIGINS=["https://your-app.vercel.app"]

# --- Optional (defaults shown in backend/config/settings.py) ---
CHAT_MODEL=gpt-6-luna
```

| Setting | Default | Purpose |
| --- | --- | --- |
| `openai_api_key` | — | required |
| `chat_model` | `gpt-6-luna` | model for responses and extraction |
| `database_url` | — | Postgres connection string (long-term store) |
| `redis_url` | — | Redis connection string (checkpointer + session markers) |
| `history_summarize_trigger` | `10` | message count that triggers summarization |
| `history_keep_last_n` | `6` | messages kept verbatim when summarizing |
| `memory_extraction_every_n_turns` | `4` | periodic long-term memory extraction cadence |
| `session_idle_seconds` | `600` | idle time before the Redis-expiry backstop fires |
| `frontend_origins` | `["http://localhost:3000"]` | origins allowed via CORS |

---

## Running

### Backend

```bash
uv run python -m backend.api.server
```

Requires a reachable Redis and Postgres (connection strings in `.env`). Runs
checkpointer/store migrations on startup, then serves on `127.0.0.1:8001`.

> `main.py` at the repo root is a separate, minimal FastAPI app — not the real
> entrypoint.

### Frontend dev server

```bash
cd frontend
npm run dev
```

Open [localhost:3000](http://localhost:3000) — pick a country on the landing
page to start a chat session against the backend.

---

## Frontend

A Next.js console in front of the `/chat` API: pick a country (or type a
custom one) on the landing page, then converse with the country-learning
agent on the chat page.

![WorldWiseAI chat](images/chat.png)

| Page | Route | Talks to |
| --- | --- | --- |
| Landing | `/` | — (navigates to `/chat`) |
| Chat | `/chat?country=...` | `POST /chat`, `POST /chat/{session_id}/end` |

---

## API Documentation

### `POST /chat`

```json
{
  "query": "What's the best time to visit Japan?",
  "session_id": "optional - omit to start a new session",
  "user_id": "optional - omit for an anonymous, non-persisted conversation",
  "country": "Japan (required to start a new session)"
}
```

Returns `{"session_id", "user_id", "response"}`. Reuse `session_id` to continue a conversation.

```bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "What should I pack for Japan in winter?", "country": "Japan"}' \
  http://127.0.0.1:8001/chat | python3 -m json.tool
```

### `POST /chat/{session_id}/end?user_id=...`

Call when a conversation is over. Flushes any pending long-term memory immediately.
Optional — the idle listener does the same thing automatically if skipped.

---

## Deployment

The backend ships as a Docker Compose stack (`docker-compose.yml`) that joins
an existing Traefik-managed Docker network (`n8n_default`) and routes to it via
Docker labels — TLS handled by Traefik's Let's Encrypt resolver. Postgres is
expected to be external (e.g. a managed/serverless provider with `pgvector`);
Redis Stack runs self-hosted in its own container since the checkpointer's
RediSearch (`FT.*`) commands aren't supported by providers like Upstash.

```bash
docker compose up -d --build
```

The frontend is a standard Next.js app and can be deployed independently
(e.g. Vercel) — point it at the deployed backend via its API base URL and
make sure `FRONTEND_ORIGINS` on the backend includes that origin.
