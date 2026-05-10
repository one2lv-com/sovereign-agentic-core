# Sovereign Agentic Core

A real-time AI agent system built with FastAPI, WebSocket, and the Anthropic Claude API.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Sovereign Core                      │
│                                                     │
│  ┌─────────────┐   ┌──────────────┐                │
│  │  Lumenis    │   │  Flux Compass│                │
│  │  Reactor    │   │  (SQLite)    │                │
│  │  temp=0.18  │   │  Memory      │                │
│  │  73ms pulse │   │  Sessions    │                │
│  └─────────────┘   └──────────────┘                │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │         ITT Council of Seven                │   │
│  │  Sentinel · Navigator · Witness             │   │
│  │  Weaver · Forge · Oracle · Architect        │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │     Vanguard Node Pool (144,382 nodes)      │   │
│  │     asyncio.Semaphore(16) concurrency       │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Components

- **LumenisReactor** — Claude claude-opus-4-6 at temperature 0.18, 73ms heartbeat, streaming responses
- **FluxCompass** — SQLite-backed persistent memory: sessions, messages, facts
- **ITT Council of Seven** — 7 specialized Claude agents that orchestrate every request
- **VanguardNodePool** — Async task execution with configurable concurrency

### Council of Seven

| Seat | Role | Function |
|------|------|----------|
| The Sentinel | Security | Validates inputs, flags risks |
| The Navigator | Planning | Classifies intent, routes to seats |
| The Witness | Memory | Retrieves context from SQLite |
| The Weaver | Synthesis | Streams the final response |
| The Forge | Execution | Code and structured output |
| The Oracle | Knowledge | Reasoning with confidence levels |
| The Architect | Governance | Meta decisions and system questions |

## Setup

```bash
pip install fastapi uvicorn anthropic aiofiles
export ANTHROPIC_API_KEY=your_key_here
uvicorn main:app --host 0.0.0.0 --port 3002
```

Open `http://localhost:3002` in your browser.

## API

- `GET /` — Web UI
- `GET /api/status` — Live system status
- `GET /api/sessions` — List sessions
- `POST /api/sessions` — Create session
- `GET /api/sessions/{id}/history` — Chat history
- `WS /ws` — Real-time WebSocket chat
