# CLAUDE.md — Finance Coach (O'Reilly AI Superstream Demo)

## What This Is

A Streamlit demo app for the O'Reilly AI Superstream talk "Engineering Context Quality by Architecting Agent Memory." The app is a personal finance coach that demonstrates agent memory engineering using MongoDB Atlas, Voyage AI, and Claude.

**This is a demo app, not a production system.** Optimize for clarity and teachability, not scale. Every architectural choice should be explainable in a 30-minute talk.

## Reference Documents

These documents are the source of truth. Read them before writing any code:

- `docs/oreilly-talk-concepts.md` — Framework, terminology, architecture. Section 0 (where an agent lives), Section 5 (three moves + cold/warm start), Section 9 (four pipelines).
- `docs/oreilly-talk-app-spec.md` — Schemas, diagrams, prompts, UI spec, sample data. This is the implementation blueprint.
- `docs/oreilly-talk-outline-v5.md` — Talk script. The demo walkthrough (Section 2-4) defines the exact user flow.
- `docs/implementation-plan.md` — Ordered build steps with checkpoints.
- `docs/technical-reference.md` — Code-ready schemas, queries, prompts. No prose — just specs.
- `scripts/seed_data.py` — Seed script for transactions and pre-loaded snapshot.

When in doubt about terminology, field names, or architecture, check the concepts doc first, then the app spec.

## Project Structure

```
finance-coach/
├── CLAUDE.md                    # This file
├── .env.example                 # Template for secrets
├── .gitignore
├── Makefile                     # Common commands
├── requirements.txt             # Python dependencies
├── pyproject.toml               # ruff config, project metadata
├── .pre-commit-config.yaml      # Pre-commit hooks
│
├── docs/                        # Reference documents (read-only during dev)
│   ├── oreilly-talk-concepts.md
│   ├── oreilly-talk-app-spec.md
│   ├── oreilly-talk-outline-v5.md
│   ├── implementation-plan.md
│   └── technical-reference.md
│
├── scripts/
│   ├── seed_data.py             # Seed transactions + pre-loaded snapshot
│   ├── setup_indexes.py         # Create vector, text, and TTL indexes
│   └── reset_demo.py            # Reset to pre-loaded state between demo runs
│
├── src/
│   ├── __init__.py
│   ├── config.py                # Environment variables, constants
│   ├── db.py                    # MongoDB connection, collection handles
│   ├── embeddings.py            # Voyage AI embedding calls
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── load_baseline.py     # Deterministic SELECT (session start)
│   │   ├── select_memories.py   # Query-driven SELECT (per request)
│   │   ├── generate_response.py # INJECT + LLM call
│   │   ├── write_memories.py    # WRITE — memory extraction
│   │   └── memory_formatter.py  # Format memories for context window
│   ├── models/
│   │   ├── __init__.py
│   │   └── memory.py            # Pydantic models for memory units
│   └── prompts/
│       ├── __init__.py
│       ├── system.py            # System prompt for generate_response
│       └── extraction.py        # Extraction prompt for write_memories
│
├── app.py                       # Streamlit entry point
├── ui/
│   ├── __init__.py
│   ├── chat.py                  # Main chat interface
│   ├── sidebar.py               # Memory list + sidebar tabs
│   ├── tabs/
│   │   ├── __init__.py
│   │   ├── document_tab.py      # 📋 Document — full memory JSON
│   │   ├── search_tab.py        # 🔍 Search — pipeline + scores + "Run search only"
│   │   ├── context_tab.py       # 📝 Context — assembled prompt + with/without toggle
│   │   └── data_tab.py          # 💾 Data — raw transactions + "View aggregation"
│   └── components/
│       ├── __init__.py
│       ├── memory_card.py       # Single memory display (colored by type)
│       └── raw_query_toggle.py  # "View raw query" toggle component
│
└── tests/
    ├── __init__.py
    ├── conftest.py              # Shared fixtures (test DB, mock embeddings)
    ├── test_load_baseline.py
    ├── test_select_memories.py
    ├── test_generate_response.py
    ├── test_write_memories.py
    ├── test_memory_formatter.py
    └── test_seed_data.py
```

## Environment Setup

### Prerequisites

- Python 3.12+
- MongoDB Atlas account (free tier M0 is sufficient)
- Voyage AI API key (`voyage-3-large`)
- Anthropic API key (Claude Sonnet 4.5)

### Environment Variables (.env)

```
MONGODB_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/
MONGODB_DATABASE=finance_coach_db
VOYAGE_API_KEY=vo-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with your keys

# Setup MongoDB (indexes + seed data)
make setup

# Run the app
make run
```

## Coding Conventions

### General

- **Python 3.12+**, type hints everywhere
- **Pydantic v2** for data models (memory units, config)
- **No frameworks** (no LangChain, no Mem0, no CrewAI) — the whole point is showing it's just Python + MongoDB + Voyage + Claude
- **Minimal abstractions** — prefer explicit over clever. Each of the four agent functions should be readable as a standalone ~30-50 line function
- Functions should be independently testable with clear inputs/outputs
- Use `logging` module, not `print()` for debug output

### Naming

- Follow the terminology in the concepts doc exactly:
  - **Three Moves:** Write, Select, Inject (not "store", "retrieve", "insert")
  - **Memory types:** preferences (semantic), snapshots (episodic), flags (working)
  - **Two SELECT modes:** deterministic (session start), query-driven (per request)
  - **Four functions:** `load_baseline()`, `select_memories()`, `generate_response()`, `write_memories()`
- Collection names: `preferences`, `snapshots`, `flags`, `transactions`
- Database name: `finance_coach_db`
- Demo user ID: `"alex_demo"`

### MongoDB

- Use **PyMongo** directly — no ODM (no MongoEngine, no Motor for this demo)
- All memory collections share the base schema fields: `user_id`, `subject`, `fact`, `embedding`, `citations`, `is_active`, `created_at`
- Pre-filter on `{ user_id, is_active: true }` in ALL search queries
- Vector indexes: 1024 dimensions, cosine similarity
- Text indexes: on `subject` + `fact` fields
- TTL index: on `flags.expires_at` only
- Use `$rankFusion` for hybrid search (not sequential vector-then-text)

### Voyage AI

- Model: `voyage-3-large`
- Dimensions: 1024
- **Asymmetric input types:** `input_type="document"` when embedding memories for storage, `input_type="query"` when embedding user queries for search
- Only embed the `fact` field — that's where the semantic meaning lives

### Claude (Anthropic SDK)

- Model: `claude-sonnet-4-5-20250514`
- Used for TWO separate calls per message:
  1. `generate_response()` — response generation with memory context
  2. `write_memories()` — memory extraction from conversation
- NOT used for: embeddings, search, storage

### Streamlit

- Use `st.session_state` for all state management (baseline memories, chat history, selected memory, active tab)
- Sidebar is the "Memory Engineering" panel — always visible
- Main area is the chat interface
- Four tabs in sidebar: 📋 Document, 🔍 Search, 📝 Context, 💾 Data
- Each tab has a "View raw query" toggle
- Color-code memories: 🟢 preferences, 🔵 snapshots, 🟡 flags

### Testing

- Use **pytest** with fixtures for:
  - A test MongoDB database (separate from demo DB)
  - Mock Voyage AI embeddings (deterministic 1024-dim vectors)
  - Mock Claude responses (canned extraction results)
- Test each agent function independently
- Key test scenarios:
  - Cold start (new user, `load_baseline()` returns empty)
  - Warm start (returning user, `load_baseline()` returns snapshot + preferences)
  - Hybrid search ranking (text boost for specific queries, vector-only for abstract queries)
  - Memory dedup (baseline + query-driven results don't duplicate)
  - Memory extraction (preferences, snapshots, flags created correctly)
  - TTL expiration (flag `expires_at` is set correctly)
  - Supersedes chain (`is_active: false` on old version)

## Architecture Rules

### The Agent Is Four Functions

```
Session Start → load_baseline(user_id)
                     │
                     ▼ (per message)
               select_memories() → generate_response() → write_memories()
```

1. **`load_baseline(user_id)`** — Deterministic SELECT. Direct MongoDB queries, no embedding, no search. Returns latest snapshot + top preferences. Empty list for new users.
2. **`select_memories(query, user_id)`** — Query-driven SELECT. Embed query (Voyage), run `$rankFusion` hybrid search (MongoDB), merge with baseline (dedup). Returns top-k memories.
3. **`generate_response(memories, message, history)`** — INJECT + LLM. Format memories as structured context block, assemble prompt, call Claude. Returns response text.
4. **`write_memories(response, message, user_id)`** — WRITE. Ask Claude to extract memory-worthy units, embed each `fact` field (Voyage), insert to MongoDB. Handle supersedes if contradicting existing memory.

### Direct Queries (Sidebar)

The sidebar tabs query MongoDB directly — no agent involvement. This is intentional: it demonstrates that MongoDB's search capabilities are standalone, not agent-specific.

- Memory tab: `db.{collection}.find({ user_id, is_active: true })`
- Search tab: `$rankFusion` pipeline (same as agent uses, but without LLM reasoning)
- Data tab: `db.transactions.find({ "metadata.user_id": user_id })`
- Context tab: no direct query (only exists because the agent exists)

### What NOT to Build

- No authentication/login (demo app, single user)
- No error recovery UI (if something fails, show the error clearly)
- No caching layer (demo scale, single-digit ms queries)
- No async processing (keep `write_memories` synchronous for demo clarity — audience sees memories appear in real time)
- No multi-user concurrency handling
- No framework integrations (LangChain, CrewAI, etc.)

## Demo-Specific Requirements

### User Switching

The app must support switching between users to demonstrate cold start vs. warm start:
- **Pre-loaded user ("alex_demo"):** Has a spending snapshot and ~50 transactions. Warm start.
- **New user:** Created fresh. Cold start — no memories, generic responses.
- A dropdown or button in the UI to switch users and reset the session.

### Reset Between Demo Runs

`make reset` should:
1. Delete all agent-written memories (preferences, flags) for `alex_demo`
2. Keep the pre-loaded snapshot and transactions
3. Clear Streamlit session state

### The Five Demo Messages

The app should handle this exact conversation flow (from the talk script):
1. "I love dining out and traveling. I don't care about clothes or cars." → WRITE (creates preferences)
2. "What's my dining priority?" → SELECT specific (text boost)
3. "Where am I wasting money?" → SELECT abstract (vector-only)
4. "How am I doing this month?" → Full pipeline (select + inject + write flag)
5. "What should I do about the car payments?" → Agent cites its own flag

## Makefile Targets

```makefile
setup:     # Create indexes + seed data
run:       # streamlit run app.py
reset:     # Reset to pre-loaded state
seed:      # Seed transactions + snapshot only
indexes:   # Create vector, text, TTL indexes
test:      # pytest
lint:      # ruff check + ruff format --check
format:    # ruff format
clean:     # Remove .pyc, __pycache__, .pytest_cache
```