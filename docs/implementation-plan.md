# Implementation Plan — Finance Coach

Ordered build steps. Each phase ends with a checkpoint — a concrete test that proves the phase works before moving on.

Reference: `technical-reference.md` for code-ready specs, `oreilly-talk-app-spec.md` for architecture.

---

## Phase 0: Project Scaffolding

**Goal:** Repo structure, dependencies, config, MongoDB connection.

### Steps

1. Create directory structure per `CLAUDE.md` project tree
2. Create `requirements.txt`:
   ```
   pymongo[srv]
   voyageai
   anthropic
   streamlit
   python-dotenv
   pydantic>=2.0
   pytest
   ruff
   ```
3. Create `.env.example` with all four env vars
4. Create `.envrc`:
   ```bash
   dotenv
   export MDB_MCP_CONNECTION_STRING="$MONGODB_URI"
   ```
5. Create `.mcp.json` (MongoDB MCP Server — no secrets, reads from env):
   ```json
   {
     "mcpServers": {
       "MongoDB": {
         "command": "npx",
         "args": ["-y", "mongodb-mcp-server@latest"]
       }
     }
   }
   ```
6. Create `src/config.py` — load env vars, define all constants from `technical-reference.md` Section 1 (including `APP_NAME`)
7. Create `src/db.py` — `get_database()` returns PyMongo database handle using `appname=APP_NAME`
8. Create `Makefile` with all targets from `CLAUDE.md`
9. Create `pyproject.toml` with ruff config
10. Create `.gitignore` (`.env`, `__pycache__`, `.venv`, `.pytest_cache` — note: `.envrc` and `.mcp.json` are safe to commit)

### Checkpoint

```bash
python -c "from src.db import get_database; db = get_database(); print(db.list_collection_names())"
```

Prints collection list (empty is fine). Connection works.

---

## Phase 1: Data Layer

**Goal:** Collections exist, indexes created, seed data loaded.

### Steps

1. Create `src/models/memory.py` — Pydantic models from `technical-reference.md` Section 8
2. Create `scripts/setup_indexes.py`:
   - Vector index on each memory collection (`memory_vector_index`)
   - Text index on each memory collection (`memory_text_index`)
   - TTL index on `flags.expires_at`
   - Note: vector and text indexes must be created via Atlas Admin API or Atlas UI, not PyMongo. Script should print instructions or use the Atlas Admin API if available.
3. Create `scripts/seed_data.py`:
   - Create `transactions` as a time series collection (`timeField: "transaction_date"`, `metaField: "metadata"`)
   - Insert ~47 transactions for `alex_demo` (see outline doc for full dataset)
   - Compute and insert 1 snapshot from the transaction aggregation
   - Embed the snapshot `fact` field via Voyage AI and store the embedding
   - Idempotent — drop and recreate if already exists
4. Create `scripts/reset_demo.py`:
   - Delete preferences and flags for `alex_demo`
   - Keep snapshot and transactions
   - Print confirmation

### Checkpoint

```bash
python scripts/setup_indexes.py
python scripts/seed_data.py

# Verify:
python -c "
from src.db import get_database
db = get_database()
print('transactions:', db.transactions.count_documents({'metadata.user_id': 'alex_demo'}))
print('snapshots:', db.snapshots.count_documents({'user_id': 'alex_demo', 'is_active': True}))
snap = db.snapshots.find_one({'user_id': 'alex_demo', 'is_active': True})
print('has embedding:', len(snap.get('embedding', [])) == 1024)
print('top_categories:', list(snap['structured_data']['top_categories'].keys()))
"
```

Expected: ~47 transactions, 1 active snapshot, 1024-dim embedding, correct category keys.

---

## Phase 2: Embeddings

**Goal:** Voyage AI integration works for both document and query embedding.

### Steps

1. Create `src/embeddings.py` — `embed_document(text)` and `embed_query(text)` from `technical-reference.md` Section 5
2. Handle API errors gracefully (rate limits, auth failures)

### Checkpoint

```bash
python -c "
from src.embeddings import embed_document, embed_query
d = embed_document('User prioritizes dining and travel')
q = embed_query('What are my spending priorities?')
print('doc dims:', len(d))
print('query dims:', len(q))
# Sanity: cosine similarity between related doc and query should be > 0.5
import math
dot = sum(a*b for a,b in zip(d,q))
norm_d = math.sqrt(sum(a*a for a in d))
norm_q = math.sqrt(sum(a*a for a in q))
print('cosine sim:', round(dot / (norm_d * norm_q), 3))
"
```

Expected: 1024 dims each, cosine similarity > 0.5.

---

## Phase 3: Agent Core — The Four Functions

**Goal:** All four agent functions work independently. No UI yet.

Build in this order — each function depends on the previous.

### Step 1: load_baseline

Create `src/agent/load_baseline.py` — code from `technical-reference.md` Section 4.

```python
# Test:
from src.agent.load_baseline import load_baseline
from src.db import get_database
db = get_database()

# Warm start (alex_demo has pre-loaded snapshot)
baseline = load_baseline(db, "alex_demo")
assert len(baseline) >= 1
assert baseline[0]["_collection"] == "snapshots"

# Cold start (unknown user)
empty = load_baseline(db, "unknown_user")
assert empty == []
```

### Step 2: select_memories

Create `src/agent/select_memories.py` — hybrid search from `technical-reference.md` Section 4.

```python
# Test:
from src.agent.select_memories import select_all_memories
from src.embeddings import embed_query

query = "What are my spending priorities?"
query_embedding = embed_query(query)
baseline = load_baseline(db, "alex_demo")
results = select_all_memories(db, query_embedding, query, "alex_demo", baseline)
assert len(results) >= 1  # at minimum the snapshot
# No duplicates
ids = [r["_id"] for r in results]
assert len(ids) == len(set(ids))
```

### Step 3: memory_formatter + generate_response

Create `src/agent/memory_formatter.py` — `format_memories()` from `technical-reference.md` Section 6.

Create `src/prompts/system.py` and `src/prompts/extraction.py` — prompts from `technical-reference.md` Section 6.

Create `src/agent/generate_response.py`:
- Takes memories list, user message, chat history
- Calls `format_memories()` to build context block
- Injects into system prompt
- Calls Claude
- Returns response text

```python
# Test (requires Anthropic API key):
from src.agent.generate_response import generate_response

memories = load_baseline(db, "alex_demo")
response = generate_response(memories, "How am I doing this month?", [])
assert "$" in response  # should reference dollar amounts from snapshot
print(response)
```

### Step 4: write_memories

Create `src/agent/write_memories.py`:
- Takes user message, assistant response, user_id, existing memories
- Calls Claude with extraction prompt
- Parses JSON response
- For each extracted memory:
  - Embed the `fact` field
  - Set `is_active: True`, `created_at: utcnow()`
  - If flag: compute `expires_at` from `expires_in_days`
  - Insert to appropriate collection
- Returns list of newly created memories

```python
# Test:
from src.agent.write_memories import write_memories

new_memories = write_memories(
    user_message="I love dining out and traveling. I don't care about clothes or cars.",
    assistant_response="Got it! I'll remember that dining and travel are your priorities...",
    user_id="alex_demo",
    existing_memories=[],
    db=db
)
assert len(new_memories) >= 2  # at least dining + travel preferences
for m in new_memories:
    assert m["_collection"] == "preferences"
    assert m["structured_data"]["priority"] in ("high", "low")
    assert len(m["embedding"]) == 1024
```

### Checkpoint — Full Pipeline (no UI)

Run the 5-message demo flow from the command line:

```python
"""Full pipeline test — mirrors the 5 demo messages."""
from src.db import get_database
from src.agent.load_baseline import load_baseline
from src.agent.select_memories import select_all_memories
from src.agent.generate_response import generate_response
from src.agent.write_memories import write_memories
from src.embeddings import embed_query

db = get_database()
user_id = "alex_demo"

# Reset
db.preferences.delete_many({"user_id": user_id})
db.flags.delete_many({"user_id": user_id})

# Session start
baseline = load_baseline(db, user_id)
print(f"Baseline: {len(baseline)} memories")
history = []

messages = [
    "I love dining out and traveling. I don't care about clothes or cars.",
    "What's my dining priority?",
    "Where am I wasting money?",
    "How am I doing this month?",
    "What should I do about the car payments?",
]

for msg in messages:
    print(f"\n--- USER: {msg}")

    # Select
    query_emb = embed_query(msg)
    memories = select_all_memories(db, query_emb, msg, user_id, baseline)
    print(f"  Selected: {len(memories)} memories")

    # Generate
    response = generate_response(memories, msg, history)
    print(f"  AGENT: {response[:200]}...")

    # Write
    new = write_memories(msg, response, user_id, memories, db)
    print(f"  Wrote: {len(new)} new memories")

    # Update baseline if new memories written
    if new:
        baseline = load_baseline(db, user_id)

    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": response})

# Verify final state
prefs = db.preferences.count_documents({"user_id": user_id, "is_active": True})
flags = db.flags.count_documents({"user_id": user_id, "is_active": True})
print(f"\nFinal state: {prefs} preferences, {flags} flags")
assert prefs >= 2, "Should have at least dining + travel preferences"
```

This is the most important checkpoint. If this passes, the agent works. Everything after this is UI.

---

## Phase 4: Streamlit — Chat Interface

**Goal:** Working chat with agent. No sidebar tabs yet.

### Steps

1. Create `app.py` — Streamlit entry point:
   - User selector dropdown (alex_demo vs. new user)
   - On user change: call `load_baseline()`, store in `st.session_state`
   - Chat input → `select_memories()` → `generate_response()` → `write_memories()`
   - Display chat history with `st.chat_message`
2. Create `ui/chat.py` — chat display logic
3. Wire up session state:
   - `st.session_state.user_id`
   - `st.session_state.baseline`
   - `st.session_state.chat_history`
   - `st.session_state.all_memories` (updated after each write)

### Checkpoint

```bash
make run
```

Walk through the 5 demo messages in the browser. Agent responds with personalized financial advice. Preferences are created after message 1. Flag appears after message 4.

---

## Phase 5: Sidebar — Memory List

**Goal:** Sidebar shows live memory state, color-coded by type.

### Steps

1. Create `ui/sidebar.py` — memory panel:
   - Header: memory count + approximate token count
   - List all active memories, color-coded (🟢 🔵 🟡)
   - Click a memory to select it (sets `st.session_state.selected_memory`)
   - Update after each message (re-query active memories)
2. Create `ui/components/memory_card.py` — single memory display:
   - Color badge by type
   - Show `subject` and `fact`
   - Show `created_at` as relative time
   - For flags: show `expires_at`

### Checkpoint

Run 5 messages. Sidebar starts with 1 🔵, gains 3 🟢 after message 1, gains 1 🟡 after message 4.

---

## Phase 6: Sidebar — Four Tabs

**Goal:** All four sidebar tabs working with "View raw query" toggles.

Build one tab at a time.

### Tab 1: 📋 Document

Create `ui/tabs/document_tab.py`:
- Shows full JSON of the selected memory (from `st.session_state.selected_memory`)
- Syntax-highlighted
- "View raw query" toggle shows `db.{collection}.find_one({ _id: ObjectId("...") })`

### Tab 2: 🔍 Search

Create `ui/tabs/search_tab.py`:
- After each message, shows the `$rankFusion` pipeline that was executed
- Displays per-result scores (vector score, text score, combined rank)
- "Run search only" button: executes the same pipeline without agent reasoning, displays raw results
- "View raw query" toggle shows the full aggregation pipeline

### Tab 3: 📝 Context

Create `ui/tabs/context_tab.py`:
- Shows the assembled `<user_context>` block that was injected into the system prompt
- Toggle: "With memory" vs "Without memory" — shows the full prompt both ways
- Token count for each

### Tab 4: 💾 Data

Create `ui/tabs/data_tab.py`:
- Shows raw transactions via `db.transactions.find()`
- Filterable by month and category
- "View aggregation" button shows the pipeline that produces snapshots
- "View raw query" toggle shows the `find()` command

### Shared component

Create `ui/components/raw_query_toggle.py`:
- Reusable toggle component
- Takes a MongoDB command string
- Renders as collapsible code block

### Checkpoint

All four tabs render. Each toggle reveals a valid MongoDB command. "Run search only" returns results without triggering the agent.

---

## Phase 7: Polish & Demo Prep

**Goal:** Ready for live demo.

### Steps

1. **Reset flow:** `make reset` clears preferences + flags, keeps snapshot + transactions. Verify sidebar resets to 1 🔵.
2. **Cold/warm start:** Switch to new user → sidebar empty, generic responses. Switch back to alex_demo → snapshot loaded, personalized from first message.
3. **Hook slide:** Add the side-by-side comparison as the initial state before any messages are sent (from spec Section 1: "The Hook"). Can be a static display or generated live.
4. **Timing:** Run through all 5 messages. Target: under 3 minutes total, with natural pauses for sidebar inspection.
5. **Error handling:** If Voyage or Claude API fails, show the error clearly in the chat (no silent failures).
6. **Visual cleanup:**
   - Page title and favicon
   - Consistent spacing
   - Memory cards look clean at various content lengths
   - Tabs don't jump/resize on content change

### Checkpoint

Full dry run: `make reset` → `make run` → walk through 5 messages → switch to new user → switch back. Everything works, looks clean, finishes in under 3 minutes.

---

## Phase 8: Tests

**Goal:** Automated test coverage for the four agent functions.

### Steps

1. Create `tests/conftest.py`:
   - Fixture: test database (separate from demo DB, e.g., `finance_coach_test_db`)
   - Fixture: mock Voyage embeddings (deterministic 1024-dim vectors, no API calls)
   - Fixture: mock Claude responses (canned extraction JSON)
   - Fixture: seeded test data (1 snapshot, 2 preferences, 1 flag)
2. Create test files per CLAUDE.md test list:
   - `test_load_baseline.py` — cold start returns [], warm start returns snapshot + prefs
   - `test_select_memories.py` — hybrid search returns results, dedup works
   - `test_generate_response.py` — response references snapshot numbers
   - `test_write_memories.py` — preferences created with correct schema, flags get `expires_at`, empty array when nothing to extract
   - `test_memory_formatter.py` — formatted output matches expected template
   - `test_seed_data.py` — seed script is idempotent, correct counts

### Checkpoint

```bash
make test
```

All tests pass. No live API calls in tests (all mocked).

---

## Build Order Summary

| Phase | What | Depends On | Key Risk |
|-------|------|-----------|----------|
| 0 | Scaffolding | Nothing | MongoDB Atlas connection |
| 1 | Data layer | Phase 0 | Vector/text index creation (Atlas UI vs API) |
| 2 | Embeddings | Phase 0 | Voyage API key, rate limits |
| 3 | Agent core | Phases 1 + 2 | Prompt tuning (extraction quality) |
| 4 | Chat UI | Phase 3 | Streamlit session state management |
| 5 | Sidebar | Phase 4 | Memory state updates after writes |
| 6 | Tabs | Phase 5 | Search score display, raw query formatting |
| 7 | Polish | Phase 6 | Timing the demo flow |
| 8 | Tests | Phase 3 | Mocking Voyage + Claude cleanly |

**Critical path:** Phases 0 → 1 → 2 → 3. Once the agent works from the command line (Phase 3 checkpoint), the UI phases are incremental and lower-risk.

**Highest risk:** Phase 3 Step 4 (write_memories) — extraction prompt quality determines whether the right memories get created. Budget extra time for prompt iteration here.