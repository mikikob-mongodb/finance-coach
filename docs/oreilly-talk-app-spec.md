# Engineering Context Quality by Architecting Agent Memory

## App Specification & Implementation Reference

**Talk:** O'Reilly AI Superstream, 30 min
**Speaker:** Mikiko Bazeley, Staff Developer Advocate, MongoDB
**Demo app:** Personal Finance Coach (Streamlit)
**Stack:** Python, PyMongo, Voyage AI, Claude (Anthropic SDK)
**Companion doc:** `oreilly-talk-concepts.md` — definitions, positioning, Q&A, academic grounding
**Sample data:** `oreilly-talk-outline-v4.md` — full 47-transaction dataset, snapshot JSON, expected memory outputs

### Contents

| # | Section | What It Covers |
|---|---------|---------------|
| 1 | Demo Story & UI | User persona, the hook, UI layout, sidebar tabs, 5-message walkthrough with voiceover |
| 2 | Architecture Diagrams | System overview, request lifecycle, data structures, memory lifecycle, hybrid search flow |
| 3 | Technical Architecture | Database, schemas, indexes, four functions, Voyage/Claude details, tech stack, reset script |
| 4 | Hybrid Search Deep Dive | `$rankFusion` pipeline code, parallel execution, query type comparison |
| 5 | Prompt Templates | System prompt, memory formatting code, extraction prompt, two-LLM-call rationale |
| 6 | Scaling Notes | Scale thresholds, what changes at 10K/1M users, latency table |

---

## 1. Demo Story & UI

### The Demo User

**Alex** (`user_id: "alex_demo"`) — a 30-something professional in the Bay Area earning ~$120K ($9,757/month take-home). Alex has strong opinions about what matters: dining out, travel, and fitness are top priorities. Cars and clothes are not.

But Alex's spending tells a different story. Car payments dominate at $1,245/month (8% interest, 48 months remaining). Dining is high at $890/month across 18 transactions — which actually *aligns* with the stated priority. Fitness spending is $0. Travel is $0.

**The story the data tells:** Alex's values and spending are misaligned in ways the user can't see from raw transactions alone. The agent's job is to surface this — but only after it *learns* what Alex cares about. That learning is the demo.

**Why this user works for the talk:**
- 18 dining transactions prove the priority is real (not just talk)
- $1,245 car payment at 8% is the elephant in the room (user says they don't care about cars)
- $0 fitness / $0 travel are conspicuous absences that create the mismatch
- 47 total transactions fit in a context window — this defeats the "just use long context" argument. The point isn't volume; it's that raw transactions don't contain "user prioritizes dining over cars." The agent creates that knowledge.

**Full sample data** (47 transactions, snapshot JSON, expected memory outputs) is in `oreilly-talk-outline-v4.md`.

### The Hook: Side-by-Side Comparison

This is the first thing the audience sees — two responses to the same question, showing the difference memory makes:

```
WITHOUT MEMORY                          WITH MEMORY
─────────────────                       ─────────────────

User: How am I doing this month?        User: How am I doing this month?

Agent: You spent $6,870 on fixed        Agent: You told me health and fitness
costs, $1,023 on investments, and       is your top priority — but I see $0
$1,000 on discretionary spending.       going to fitness and $1,245/month on
Consider reducing your Uber and         car payments. Your cars are crowding
dining expenses.                        out what you actually care about.
                                        Meanwhile, your dining spending is
                                        aligned — that's your thing, keep it.
```

"Same LLM. Same transaction data. Same user. Completely different output. The difference? Five structured memory units — about 300 tokens — that the agent wrote itself."

### Demo UI Layout

```
┌─ Personal Finance Coach ─────────────────────┬─ Memory Engineering ──────────────────────┐
│                                               │                                           │
│                                               │  MEMORIES  (always visible)               │
│                                               │  ───────────────────────                   │
│    Chat Interface                             │  🔵 Snapshot: Feb 2026 Spending            │
│                                               │                                           │
│    (standard Streamlit chat)                  │  (after Message 1:)                        │
│                                               │  🟢 Preference: Dining Out — high         │
│                                               │  🟢 Preference: Travel — high              │
│                                               │  🟢 Preference: Cars/Clothes — low         │
│                                               │                                           │
│                                               │  (after Message 4:)                        │
│                                               │  🟡 Flag: spending mismatch                │
│                                               │                                           │
│                                               │  Total: N memories │ ~X tokens             │
│                                               │                                           │
│                                               ├───────────────────────────────────────────┤
│                                               │                                           │
│                                               │  📋 Document │ 🔍 Search │ 📝 Context    │
│                                               │  💾 Data                                   │
│                                               │                                           │
│                                               │  (detail view for selected tab)            │
│                                               │                                           │
│  ┌─────────────────────────────────────────┐  │                                           │
│  │ 💬 Message...                           │  │                                           │
│  └─────────────────────────────────────────┘  │                                           │
└───────────────────────────────────────────────┴───────────────────────────────────────────┘

Pre-loaded state: 🔵 snapshot only (1 memory, ~80 tokens)
After Message 1:  + 🟢🟢🟢 preferences (4 memories, ~240 tokens)
After Message 4:  + 🟡 flag (5 memories, ~300 tokens)
```

**Sidebar tabs:**
- **📋 Document** — Click a memory in the list → shows full JSON with annotations
- **🔍 Search** — After a query → shows pipeline JSON, results with scores from each sub-pipeline. **"Run search only" button** — executes the same `$rankFusion` hybrid search but skips agent reasoning. Shows ranked results without interpretation. Demonstrates that MongoDB's hybrid search is a standalone capability, not just an agent internal.
- **📝 Context** — After a query → shows the assembled prompt. Toggle: with memory / without memory
- **💾 Data** — Displays raw Layer 1 data: transactions via `db.transactions.find()`, filterable by month/category. This is the data the agent never searches directly — it's aggregated into snapshots by the Ingestion Pipeline. The audience sees the "before" (47 raw transactions) that becomes the "after" (1 structured snapshot). **"View aggregation" button** — shows the MongoDB aggregation pipeline that produces the snapshot from raw transactions.

**Direct query features across tabs:**

Each tab that displays MongoDB data includes a **"View raw query"** toggle that reveals the exact MongoDB query or aggregation pipeline producing the displayed results. This serves two purposes:

1. **For the talk:** demonstrates that these are standard MongoDB operations — full-text search, vector search, hybrid search, aggregation — not agent-specific magic. The audience sees the actual `$search`, `$vectorSearch`, `$rankFusion`, and `find()` commands.
2. **For the principle:** makes the "agent vs. direct query" distinction tangible. The sidebar shows what MongoDB does on its own. The chat shows what happens when you add a reasoning layer on top. Same data, same collections, two access patterns.

**Memory tab "View raw query" example:**
```javascript
// What the toggle reveals:
db.memories.find(
  { user_id: "alex_demo", is_active: true },
  { sort: { updated_at: -1 } }
)
// Returns: the same memory documents displayed in the sidebar
```

**Search tab "Run search only" example:**
```javascript
// What the button executes (same pipeline the agent uses, without the LLM call):
db.memories.aggregate([
  { $rankFusion: {
    input: {
      pipelines: {
        vector: [{ $vectorSearch: { queryVector: embed("dining spending"), path: "embedding", ... }}],
        text:   [{ $search: { compound: { should: [
          { text: { query: "dining spending", path: "fact" }},
          { text: { query: "dining spending", path: "subject" }}
        ]}}}]
      }
    }
  }},
  { $match: { user_id: "alex_demo", is_active: true }},
  { $limit: 5 }
])
// Returns: ranked memories with fusion scores — no agent reasoning applied
```

### Pre-loaded State
- Sidebar Memory list: 1 spending snapshot (🔵 episodic)
- Data tab: ~50 raw transactions (Layer 1 data — filterable by month/category)
- Memory count: 1 memory, ~60 tokens

### Message 1 — WRITE (Talk: "What Is a Memory Unit?")
**User types:** "I love dining out and traveling. I don't care about clothes or cars."

**Agent creates:** 2–3 preference memories (🟢 semantic)

**Show in UI:**
- Document tab: full JSON of a preference memory — walk through `fact`, `structured_data`, `citations`
- Sidebar: new green dots appear
- Memory count updates: 3–4 memories, ~180 tokens

**Teaching point:** "Two fields, two consumers. `fact` is what the LLM reads. `structured_data` is what your app logic reads."

**Framework comparison voiceover (while showing JSON):** "This is what Mem0 stores as an opaque text blob. We're storing it as a structured document with typed fields. That `structured_data` with `area: dining, priority: high`? I can query that directly — filter all memories where `priority` is `high`, aggregate across areas, validate the schema. In a framework, this is buried inside the embedding. The only way to find it is semantic search and hope."

### Message 2 — SELECT, specific (Talk: "How Do You Get Memories Back?")
**User types:** "What's my dining priority?"

**Show in UI:**
- Search tab: $rankFusion pipeline scores — text score boosts Dining to top
- Point out: both vector and text found Dining, but text match made it decisive

**Teaching point:** "Keywords match. Text search amplifies the signal."

**Framework comparison voiceover (while showing search scores):** "This is hybrid search — vector and text running in parallel. Most memory frameworks only give you vector search. For this query, the text match on 'dining' is what makes it decisive — 0.95 text score vs 0.85 vector. If you only had vector search, you'd still get the right result here, but the ranking would be fuzzier. When your agent has 200 memories instead of 4, that precision matters."

### Message 3 — SELECT, abstract (Talk: "How Do You Get Memories Back?")
**User types:** "Where am I wasting money?"

**Show in UI:**
- Search tab: vector found spending snapshot, text found nothing
- Same pipeline, completely different query type, still works

**Teaching point:** "No memory contains the word 'wasting.' Vector understands the semantic meaning. Text gracefully returns nothing. One pipeline handles both."

### Message 4 — INJECT, the payoff (Talk: "Context Injection")
**User types:** "How am I doing this month?"

**Show in UI:**
- Context tab: toggle between with-memory (~650 tokens) and without-memory (~30 tokens)
- Main chat: personalized response referencing priorities, flagging car payment mismatch
- Sidebar: new yellow dot appears — flag memory with `expires_at`

**Teaching point:** "Same model. ~300 tokens of the right context. That's the difference between 'consider reducing expenses' and 'your cars are crowding out what you care about.'"

**Framework comparison voiceover (while showing flag creation):** "Watch the sidebar — see that yellow dot? The agent just created a working memory flag with `expires_at` set 30 days from now. MongoDB's TTL index will auto-delete that document when the timestamp passes. Zero app code. Most memory frameworks don't even have a concept of memory that expires. Everything is permanent. But working memory should be temporary by definition — it's a short-term inference, not a permanent fact about the user."

### Message 5 (if time) — Agent uses its own memory
**User types:** "What should I do about the car payments?"

**Show in UI:**
- Agent references the flag it just created
- Citations on the response trace back to the flag, which traces back to the preference + snapshot

**Teaching point:** "The agent is citing its own knowledge store. Not external documents — its own memories. That's a read-write system."

**Framework comparison voiceover (while showing citation chain):** "Follow the citations: the response cites the flag. The flag cites the preference and the snapshot. The snapshot cites the raw transactions. That's a provenance chain from the agent's advice all the way back to source data. If a user asks 'why did you tell me that?' — you can trace it. In a framework, the memory is a text blob with an embedding. There's no `citations` field. There's no traceability. When the 'Anatomy of Agentic Memory' paper talks about silent failure — agents that chat fluently while memory degrades — this is how you detect it. You can inspect every memory the agent wrote."

**Wrap-up voiceover (if using this as final demo moment):** "So what did we actually build here? Three Python functions. Three MongoDB collections. Three types of indexes. No framework. Everything you saw — the write, the hybrid search, the TTL expiration, the provenance chain — is MongoDB primitives and about 100 lines of Python. That's the point: memory engineering is a data modeling problem. If you understand your schema and your lifecycle rules, the database does the heavy lifting."

### Memory State Progression

| After | Memories | Types | ~Tokens | What Changed |
|-------|----------|-------|---------|-------------|
| Pre-load | 1 | 🔵 snapshot | 80 | Snapshot computed from 47 transactions |
| Message 1 | 4 | 🔵 + 🟢🟢🟢 | 240 | 3 preferences written from conversation |
| Message 2 | 4 | (unchanged) | 240 | Read-only: hybrid search, text boost |
| Message 3 | 4 | (unchanged) | 240 | Read-only: hybrid search, vector only |
| Message 4 | 5 | 🔵 + 🟢🟢🟢 + 🟡 | 300 | Flag inferred from preferences × snapshot |
| Message 5 | 5 | (unchanged) | 300 | Read-only: agent cites its own flag |
| +30 days | 4 | 🔵 + 🟢🟢🟢 | 240 | TTL auto-deletes the flag |

---

## 2. Architecture Diagrams

### Diagram A: Full System Overview

Shows every component and how they connect. This is the "map of the territory" — not for a slide, but for understanding the whole system.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STREAMLIT UI                                       │
│                                                                                 │
│  ┌───────────────────────────────┐    ┌────────────────────────────────────┐    │
│  │        MAIN CHAT AREA         │    │           SIDEBAR                  │    │
│  │                               │    │                                    │    │
│  │  User message input           │    │  Memory List                       │    │
│  │  Agent response display       │    │    🟢 preference: dining (high)    │    │
│  │                               │    │    🟢 preference: travel (high)    │    │
│  │                               │    │    🔵 snapshot: Feb 2026           │    │
│  │  (routes through agent)       │    │    🟡 flag: fitness mismatch       │    │
│  │                               │    │                                    │    │
│  │                               │    │  Count: 4 memories · ~240 tokens   │    │
│  │                               │    │                                    │    │
│  │                               │    │  ┌──────┐ ┌──────┐ ┌───────┐     │    │
│  │                               │    │  │ Doc  │ │Search│ │Context│     │    │
│  │                               │    │  │ tab  │ │ tab  │ │  tab  │     │    │
│  │                               │    │  └──────┘ └──────┘ └───────┘     │    │
│  │                               │    │  ┌──────┐                         │    │
│  │                               │    │  │ Data │                         │    │
│  │                               │    │  │ tab  │                         │    │
│  │                               │    │  └──────┘                         │    │
│  │                               │    │                                    │    │
│  │                               │    │  Each tab has "View raw query"     │    │
│  │                               │    │  toggle showing MongoDB command    │    │
│  └───────────────────────────────┘    └────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
         │                                   │    ▲
         │ user message                      │    │ response + sidebar updates
         │                                   │    │
         │    ┌──────────────────────────────┐│    │
         │    │ DIRECT QUERY PATH            ││    │
         │    │ (sidebar tabs query MongoDB  ││    │
         │    │  without agent involvement)  ││    │
         │    └──────────────┬───────────────┘│    │
         │                   │                │    │
         ▼                   │                │    │
┌────────────────────────────│────────────────│────│───────────────────────────────┐
│                  AGENT (Python)             │    │                               │
│                                            │    │                               │
│  ┌──────────────────┐                      │    │                               │
│  │ load_baseline()  │ (once per session)   │    │                               │
│  └────────┬─────────┘                      │    │                               │
│           ▼                                │    │                               │
│  ┌──────────────────┐  ┌──────────────────┐│ ┌──────────────────┐              │
│  │ select_memories() │─▶│generate_response()├─▶│ write_memories() │              │
│  └────────┬─────────┘  └────────┬─────────┘│ └────────┬─────────┘              │
│           │                     │           │          │                        │
│           │ embed query         │ format context       │ extract new units      │
│           │ hybrid search       │ call LLM             │ embed facts            │
│           │                     │                      │ insert to MongoDB      │
└───────────┼─────────────────────┼──────────────────────┼────────────────────────┘
            │                     │                      │
            ▼                     ▼                      ▼
┌───────────────────┐  ┌──────────────────┐  ┌───────────────────┐
│    Voyage AI      │  │   Claude         │  │    Voyage AI      │
│                   │  │   Sonnet 4.5     │  │                   │
│  embed(query,     │  │                  │  │  embed(fact,      │
│  type="query")    │  │  Anthropic SDK   │  │  type="document") │
│                   │  │                  │  │                   │
│  1024 dims        │  │  Response gen    │  │  1024 dims        │
│                   │  │  + memory        │  │                   │
│                   │  │    extraction    │  │                   │
└───────────────────┘  └──────────────────┘  └───────────────────┘
            │                   │                        │
            ▼                   │                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          MongoDB Atlas                                          │
│                                                                                 │
│  finance_coach_db                                     ▲                        │
│                                                       │                        │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────┴──────┐ ┌──────────────┐ │
│  │ 🟢 preferences  │ │ 🔵 snapshots    │ │ 🟡 flags        │ │ ⚪ transact- │ │
│  │                 │ │                 │ │                 │ │    ions      │ │
│  │ Semantic Memory │ │ Episodic Memory │ │ Working Memory  │ │ Time Series  │ │
│  │                 │ │                 │ │                 │ │              │ │
│  │ Vector idx ✓    │ │ Vector idx ✓    │ │ Vector idx ✓    │ │ (queried     │ │
│  │ Text idx ✓      │ │ Text idx ✓      │ │ Text idx ✓      │ │  directly by │ │
│  │                 │ │                 │ │ TTL idx ✓       │ │  Data tab)   │ │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘ └──────────────┘ │
│                                                                                 │
│  ▲ Direct queries from sidebar (find, $search, $vectorSearch, $rankFusion)     │
│  $rankFusion: runs $vectorSearch + $search in parallel, pre-filtered            │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Diagram B: Request Lifecycle (Single User Message)

Shows the complete flow from session start through all four functions and back.

```
SESSION START (once)
 │
 ▼
╔═══════════════════════════════════════════════════════════════╗
║ 0. load_baseline("alex_demo")                                 ║
║    Deterministic SELECT — no search, no embedding             ║
╚═══════════════════════════════════════════════════════════════╝
 │
 ├──▶ MongoDB: db.snapshots.find({ user_id: "alex_demo", is_active: true })
 │              .sort({ updated_at: -1 }).limit(1)
 │    → Latest spending snapshot (~80 tokens)
 │
 ├──▶ MongoDB: db.preferences.find({ user_id: "alex_demo", is_active: true })
 │              .sort({ updated_at: -1 }).limit(5)
 │    → Top preferences by recency (~40 tokens each)
 │
 ├──▶ Baseline context established (or empty for new users)
 │
 ▼
═══════════════════════════════════════════════════════════════
PER MESSAGE (repeats for each user message)
═══════════════════════════════════════════════════════════════

USER: "How am I doing this month?"
 │
 ▼
╔═══════════════════════════════════════════════════════════════╗
║ 1. select_memories("How am I doing this month?", "alex_demo") ║
║    Query-driven SELECT — hybrid search                        ║
╚═══════════════════════════════════════════════════════════════╝
 │
 ├──▶ Voyage AI: embed("How am I doing this month?", type="query")
 │    → [0.023, -0.118, 0.445, ... ] (1024 floats)
 │
 ├──▶ MongoDB $rankFusion:
 │    ┌─ $vectorSearch(embedding, pre-filter: alex_demo + is_active)
 │    │   → snapshot (0.88), dining_pref (0.82), travel_pref (0.79)
 │    │
 │    └─ $search("how am I doing this month", fields: [subject, fact])
 │        → snapshot (0.91), dining_pref (0.72)
 │    
 │    Combined → [snapshot, dining_pref, travel_pref, cars_pref, fitness_flag]
 │
 ├──▶ Merge with baseline context (dedup — skip memories already loaded)
 │
 ▼
╔═══════════════════════════════════════════════════════════════╗
║ 2. generate_response(memories, message, history)              ║
╚═══════════════════════════════════════════════════════════════╝
 │
 ├──▶ Format memories as context block:
 │    ┌─────────────────────────────────────────────────────┐
 │    │ <user_context>                                      │
 │    │ Stated Preferences:                                 │
 │    │ - Dining: high priority (user-stated)               │
 │    │ - Travel: high priority (user-stated)               │
 │    │ - Cars: low priority (user-stated)                  │
 │    │                                                     │
 │    │ Spending Snapshots:                                 │
 │    │ - 2026-02-01: Income $12,500, Fixed $6,870,         │
 │    │   Discretionary $1,000. Top spending: car payments: │
 │    │   $1,245, dining: $890, groceries: $650             │
 │    │ </user_context>                                     │
 │    └─────────────────────────────────────────────────────┘
 │    (~300 tokens of structured context)
 │
 ├──▶ Assemble prompt: system persona + context block + user message
 │
 ├──▶ Claude Sonnet 4.5: generate response
 │    → "You told me health and fitness is your top priority — but
 │       I see $0 going to fitness and $1,245/month on car payments.
 │       Your cars are crowding out what you actually care about..."
 │
 ▼
╔═══════════════════════════════════════════════════════════════╗
║ 3. write_memories(response, message, "alex_demo")               ║
╚═══════════════════════════════════════════════════════════════╝
 │
 ├──▶ Claude: extract new memory units from this exchange
 │    → Detected: spending mismatch (fitness priority vs $0 spend)
 │
 ├──▶ Construct flag memory:
 │    {
 │      user_id: "alex_demo",
 │      subject: "spending mismatch: fitness",
 │      fact: "User states fitness is high priority but spending
 │             is $0. Car payments ($1,245/mo) consuming budget.",
 │      structured_data: {
 │        flag_type: "spending_mismatch",
 │        severity: "high",
 │        mismatch: { stated_priority: "fitness:high", actual_spending: 0 }
 │      },
 │      citations: ["pref_fitness_id", "snapshot_feb_id"],
 │      expires_at: 2026-03-24T00:00:00Z,
 │      is_active: true
 │    }
 │
 ├──▶ Voyage AI: embed(fact, type="document") → [1024 floats]
 │
 └──▶ MongoDB: insert to flags collection
      (TTL index will auto-delete in 30 days)
 │
 ▼
RESPONSE RETURNED TO UI
 + Sidebar updates: 🟡 flag appears
 + Search tab: shows $rankFusion scores
 + Context tab: shows with/without memory toggle
```

### Diagram C: Data Structures — All Four Collections

Shows every field in every collection, with index annotations.

```
┌─────────────────────────────────────────────────────────────┐
│  🟢 preferences (Semantic Memory)                           │
├─────────────────────────────────────────────────────────────┤
│  _id:             ObjectId                                  │
│  user_id:         string          ◄── pre-filter            │
│  subject:         string          ◄── text index            │
│  fact:            string          ◄── text index + embedded │
│  embedding:       [1024 floats]   ◄── vector index (cosine) │
│  structured_data: {                                         │
│    area:          string   ("dining", "travel", "fitness")  │
│    priority:      string   ("high", "low")                  │
│  }                                                          │
│  citations:       [string]        (source message IDs)      │
│  is_active:       boolean         ◄── pre-filter            │
│  created_at:      datetime                                  │
│                                                             │
│  Lifecycle: No expiration. Permanent until user contradicts.│
│  Origin: Extracted from user conversation.                  │
│  Example fact: "User prioritizes dining and travel,         │
│                 deprioritizes cars and clothes"              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  🔵 snapshots (Episodic Memory)                             │
├─────────────────────────────────────────────────────────────┤
│  _id:             ObjectId                                  │
│  user_id:         string          ◄── pre-filter            │
│  subject:         string          ◄── text index            │
│  fact:            string          ◄── text index + embedded │
│  embedding:       [1024 floats]   ◄── vector index (cosine) │
│  structured_data: {                                         │
│    as_of_date:    date                                      │
│    income:        number                                    │
│    fixed_expenses:number                                    │
│    discretionary: number                                    │
│    investments:   number                                    │
│    top_categories:{                                         │
│      car_payments:  number                                  │
│      dining:        number                                  │
│      groceries:     number                                  │
│    }                                                        │
│  }                                                          │
│  supersedes:      ObjectId        (prev snapshot _id)       │
│  citations:       [string]        (transaction IDs)         │
│  is_active:       boolean         ◄── pre-filter            │
│  created_at:      datetime                                  │
│                                                             │
│  Lifecycle: Versioned. New snapshot supersedes old.          │
│             Old snapshot gets is_active: false.              │
│  Origin: Computed from transactions via aggregation.         │
│  Example fact: "Feb 2026 spending: $12,500 income,          │
│                 $1,245 car payments, $890 dining"            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  🟡 flags (Working Memory)                                  │
├─────────────────────────────────────────────────────────────┤
│  _id:             ObjectId                                  │
│  user_id:         string          ◄── pre-filter            │
│  subject:         string          ◄── text index            │
│  fact:            string          ◄── text index + embedded │
│  embedding:       [1024 floats]   ◄── vector index (cosine) │
│  structured_data: {                                         │
│    flag_type:     string   ("spending_mismatch")            │
│    severity:      string   ("high", "medium", "low")        │
│    mismatch: {                                              │
│      stated_priority: string ("fitness:high")               │
│      actual_spending: number (0)                            │
│    }                                                        │
│  }                                                          │
│  expires_at:      datetime        ◄── TTL index             │
│  citations:       [string]        (other memory IDs)        │
│  is_active:       boolean         ◄── pre-filter            │
│  created_at:      datetime                                  │
│                                                             │
│  Lifecycle: Auto-expires. MongoDB TTL index deletes when    │
│             expires_at passes. No app code needed.           │
│  Origin: Agent-inferred from cross-referencing preferences  │
│          against snapshots.                                  │
│  Example fact: "User states fitness is high priority but    │
│                 spending is $0. Car payments consuming       │
│                 budget at $1,245/mo."                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  ⚪ transactions (Time Series — Operational Data)            │
├─────────────────────────────────────────────────────────────┤
│  _id:               ObjectId                                │
│  transaction_date:   datetime                               │
│  metadata: {                                                │
│    user_id:          string                                 │
│    category:         string                                 │
│  }                                                          │
│  amount:             number                                 │
│  merchant:           string                                 │
│  description:        string                                 │
│                                                             │
│  NOT searched by the agent. Never enters hybrid search.     │
│  Provides raw data for computing snapshots.                 │
│  Provides provenance (cited by snapshots).                  │
│  ~50 pre-loaded records for demo.                           │
└─────────────────────────────────────────────────────────────┘
```

### Diagram D: Memory Lifecycle Across Demo Messages

Shows how memory state evolves through the five demo messages.

```
INITIAL STATE
  Memories: 🔵 snapshot (Feb 2026)
  Count: 1 · Tokens: ~60

MESSAGE 1: "I love dining out and traveling. I don't care about clothes or cars."
  ├── Agent WRITES:
  │   + 🟢 preference: dining (high)
  │   + 🟢 preference: travel (high)
  │   + 🟢 preference: cars (low)
  │
  Memories: 🔵 snapshot, 🟢🟢🟢 preferences
  Count: 4 · Tokens: ~240

MESSAGE 2: "What's my dining priority?"
  ├── Agent SELECTS (hybrid search):
  │   $rankFusion → dining_pref #1 (text: 0.95, vector: 0.85)
  │   No new memories written.
  │
  Memories: (unchanged)
  Count: 4 · Tokens: ~240

MESSAGE 3: "Where am I wasting money?"
  ├── Agent SELECTS (hybrid search):
  │   $rankFusion → snapshot #1 (vector: 0.88, text: no match)
  │   No new memories written.
  │
  Memories: (unchanged)
  Count: 4 · Tokens: ~240

MESSAGE 4: "How am I doing this month?"
  ├── Agent SELECTS: snapshot + all preferences
  ├── Agent INJECTS: ~300 tokens of structured context
  ├── Agent GENERATES: personalized response with priority-aware advice
  ├── Agent WRITES:
  │   + 🟡 flag: spending_mismatch (fitness priority, $0 spend)
  │     citations → [preference_fitness_id, snapshot_feb_id]
  │     expires_at → 30 days from now
  │
  Memories: 🔵 snapshot, 🟢🟢🟢 preferences, 🟡 flag
  Count: 5 · Tokens: ~300

MESSAGE 5 (if time): "What should I do about the car payments?"
  ├── Agent SELECTS: flag + cars_pref + snapshot
  │   (flag was just created — now it's being retrieved and used)
  ├── Agent GENERATES: response citing the mismatch flag
  │   citations trace: flag → preference + snapshot → transactions
  │
  Memories: (unchanged)
  Count: 5 · Tokens: ~300

  ... 30 days later ...

  MongoDB TTL auto-deletes the flag.
  Memories: 🔵 snapshot, 🟢🟢🟢 preferences
  Count: 4 · Tokens: ~240
```

### Diagram E: Hybrid Search Pipeline Detail

Shows what happens inside `select_memories()` for a single query.

```
select_memories("Where am I wasting money?", alex_demo)
 │
 ├──▶ STEP 1: Embed query
 │    Voyage AI: embed("Where am I wasting money?", input_type="query")
 │    → query_vector = [0.034, -0.221, 0.518, ... ] (1024 floats)
 │
 ├──▶ STEP 2: Build $rankFusion pipeline
 │    {
 │      "$rankFusion": {
 │        "input": {
 │          "pipelines": {
 │            "vector": [{
 │              "$vectorSearch": {
 │                index: "memory_vector_index",
 │                path: "embedding",
 │                queryVector: query_vector,
 │                numCandidates: 50,
 │                limit: 5,
 │                filter: { user_id: "alex_demo", is_active: true }
 │              }
 │            }],
 │            "text": [{
 │              "$search": {
 │                index: "memory_text_index",
 │                text: { query: "Where am I wasting money?",
 │                        path: ["subject", "fact"] },
 │                filter: { must: [
 │                  { equals: { path: "user_id", value: "alex_demo" } },
 │                  { equals: { path: "is_active", value: true } }
 │                ]}
 │              }
 │            }, { "$limit": 5 }]
 │          }
 │        }
 │      }
 │    }
 │
 ├──▶ STEP 3: MongoDB executes BOTH pipelines in parallel
 │
 │    Vector results:                    Text results:
 │    ┌──────────────────────────┐      ┌──────────────────────────┐
 │    │ 1. snapshot      (0.88) │      │ (no keyword matches for  │
 │    │ 2. cars_pref     (0.84) │      │  "wasting" or "money"    │
 │    │ 3. dining_pref   (0.79) │      │  in any memory's subject │
 │    │ 4. travel_pref   (0.76) │      │  or fact fields)         │
 │    │ 5. fitness_pref  (0.71) │      │                          │
 │    └──────────────────────────┘      └──────────────────────────┘
 │
 ├──▶ STEP 4: $rankFusion combines via Reciprocal Rank Fusion
 │    → snapshot: rank 1 (vector only, but decisive)
 │    → cars_pref: rank 2
 │    → dining_pref: rank 3
 │    → travel_pref: rank 4
 │    → fitness_pref: rank 5
 │
 └──▶ RETURN: [snapshot, cars_pref, dining_pref, travel_pref, fitness_pref]
```

---

## 3. Technical Architecture

### Demo Application: Personal Finance Coach

**Domain:** Spending priorities (dining, travel, cars, fitness)
**Pre-loaded data:** 1 spending snapshot, ~50 transactions (time series)
**User creates during demo:** 2–3 preference memories via conversation
**Agent creates during demo:** 1 flag memory with TTL expiration

### Database: `finance_coach_db`

Four collections:

| Collection | Memory Type | Purpose |
|---|---|---|
| `preferences` | Semantic Memory | User-stated values and priorities |
| `snapshots` | Episodic Memory | Monthly spending summaries |
| `flags` | Working Memory | Temporary agent-inferred insights |
| `transactions` | Time Series (operational data) | Raw transaction data — never queried by agent |

### Base Memory Unit Schema (shared by preferences, snapshots, flags)

```json
{
  "user_id": "string",
  "subject": "string",
  "fact": "string",
  "embedding": [1024 floats],
  "citations": [{"type": "user_message | memory", "ref": "source_id", "collection": "optional"}],
  "is_active": true,
  "created_at": "datetime"
}
```

**`fact`** — natural language the LLM reads. This is what gets embedded and searched.
**`structured_data`** — typed fields the app reads. Varies by collection type.
**`embedding`** — Voyage AI `voyage-3-large`, 1024 dimensions. Embed the `fact` field only.
**`citations`** — traces provenance back to source data or other memories. `type` distinguishes user messages from other memories; `ref` is the source `_id`; `collection` identifies which memory collection (for cross-memory citations).
**`is_active`** — `false` when superseded by a newer version. Pre-filter excludes these from search.

### Type-Specific Fields

**preferences (Semantic Memory)**
```json
{
  "structured_data": { "area": "dining", "priority": "high" }
}
```
- No expiration — permanent user values
- Origin: extracted from user conversation

**snapshots (Episodic Memory)**
```json
{
  "structured_data": {
    "as_of_date": "2026-02-01",
    "income": 12500,
    "fixed_expenses": 6870,
    "discretionary": 1000,
    "investments": 1023,
    "top_categories": { "car_payments": 1245, "dining": 890, "groceries": 650 }
  },
  "supersedes": "ObjectId(previous_snapshot_id)"
}
```
- Versioned: `supersedes` points to previous snapshot. Old snapshot gets `is_active: false`.
- This implements a lightweight version of MongoDB's [Document Versioning Pattern](https://www.mongodb.com/blog/post/building-with-patterns-the-document-versioning-pattern). The search pre-filter (`is_active: true`) ensures only the current version is selected, but the full history is preserved — walk the `supersedes` chain to see how spending evolved month over month.
- Only snapshots need versioning. Preferences don't version (if your dining priority changes, the old one is just wrong — deactivate and write new). Flags don't version (they're temporary insights that expire via TTL, not revisions of the same observation).
- Origin: computed from transaction data via aggregation

**flags (Working Memory)**
```json
{
  "structured_data": {
    "flag_type": "spending_mismatch",
    "severity": "high",
    "mismatch": { "stated_priority": "fitness:high", "actual_spending": 0 }
  },
  "expires_at": "2026-03-24T00:00:00Z"
}
```
- Auto-expires: MongoDB TTL index on `expires_at` deletes the document automatically
- Origin: agent-inferred by cross-referencing preferences against snapshots

### Indexes

Every memory collection gets:
- **Vector index:** `embedding` field, 1024 dims, cosine similarity, pre-filter on `user_id` + `is_active`
- **Text index:** `subject` + `fact` fields, compound filter on `user_id` + `is_active`

Flags additionally get:
- **TTL index:** `expires_at` field — MongoDB auto-deletes when the timestamp passes

### The Agent: Four Functions

```
Session Start
     │
     ▼
load_baseline()
     │
     ▼ (per message)
select_memories()  ──→  generate_response()  ──→  write_memories()
```

**`load_baseline(user_id)` — Deterministic SELECT (session start)**
1. Fetch latest snapshot: `db.snapshots.find({ user_id, is_active: true }).sort({ updated_at: -1 }).limit(1)`
2. Fetch top preferences: `db.preferences.find({ user_id, is_active: true }).sort({ updated_at: -1 }).limit(5)`
3. Return baseline memories (empty list for new users — cold start)
4. No embedding, no search — just direct MongoDB queries

**`select_memories(query, user_id)` — Query-driven SELECT (per request)**
1. Embed query using Voyage AI (`input_type="query"`)
2. Run `$rankFusion` hybrid search via PyMongo:
   - `$vectorSearch` on embedding field with pre-filter `{ user_id, is_active: true }`
   - `$search` on subject + fact fields with same pre-filter
3. Merge with baseline memories (dedup — skip memories already loaded at session start)
4. Return top-k memory documents

**`generate_response(memories, user_message, chat_history)`**
1. Format selected memories as a context block (structured text, not raw JSON)
2. Assemble system prompt: persona + context block + instructions
3. Call Claude Sonnet 4.5 via Anthropic SDK
4. Return response text

**`write_memories(response, user_message, user_id)`**
1. Ask Claude to extract any new memory units from the conversation
2. For each new memory unit:
   a. Embed the `fact` field using Voyage AI (`input_type="document"`)
   b. Set `citations` to trace provenance
   c. Insert to appropriate MongoDB collection via PyMongo
3. If the new memory supersedes an existing one, set old memory's `is_active: false`

**No framework needed.** This works with LangGraph, CrewAI, or whatever you're already using. A framework would abstract away exactly the parts we want to teach.

### Voyage AI Details

- **Model:** `voyage-3-large`
- **Dimensions:** 1024
- **Asymmetric input types:** `input_type="document"` when storing memories, `input_type="query"` when searching. This asymmetry improves retrieval quality — the model optimizes embeddings differently for documents vs. queries.
- **What gets embedded:** The `fact` field only — that's where the semantic meaning lives.
- **Scale-up:** Add Voyage reranking after hybrid search to refine top results before injection.

### Claude Details

- **Model:** Claude Sonnet 4.5 (via Anthropic SDK)
- **Used for:** Response generation AND memory extraction (both in `generate_response` and `write_memories`)
- **Not used for:** Embeddings (that's Voyage), search (that's MongoDB), memory storage (that's PyMongo)

### The Entry Point

```python
# Called once per session
def start_session(user_id):
    baseline = load_baseline(user_id)
    # baseline is [] for new users (cold start)
    # baseline is [snapshot, pref1, pref2, ...] for returning users (warm start)
    return baseline

# Called on every user message
def handle_message(user_message, user_id, baseline_memories):
    # 1. SELECT (query-driven) — search for memories relevant to this message
    query_embedding = voyage_embed(user_message, input_type="query")
    selected = select_memories(query_embedding, user_message, user_id)
    memories = merge_and_dedup(baseline_memories, selected)

    # 2. GENERATE — format memories as context, call Claude
    context = format_memories_for_context(memories)
    response = generate_response(user_message, context)

    # 3. WRITE — extract new memory units, embed, store
    new_memories = write_memories(user_message, response, memories, user_id)

    return response, memories, new_memories
```

### Reset Script (between demo runs)

```python
# Clear all agent-written memories, keep pre-loaded snapshot and transactions
db.preferences.delete_many({"user_id": "alex_demo"})
db.flags.delete_many({"user_id": "alex_demo"})
# snapshots: keep the pre-loaded one
# transactions: never modified
```

### Tech Stack Summary

| Component | Technology |
|-----------|-----------|
| Frontend | Streamlit |
| Agent | Plain Python (4 functions: `load_baseline`, `select_memories`, `generate_response`, `write_memories`) |
| Direct queries | Sidebar tabs query MongoDB directly (no agent) via `find`, `$search`, `$vectorSearch`, `$rankFusion` |
| LLM | Claude Sonnet 4.5 (Anthropic SDK) |
| Memory DB | MongoDB Atlas (PyMongo) |
| Embeddings | Voyage AI `voyage-3-large` |

### DevRel Attribution (appName)

All MongoDB connections must include `appName` for DevRel tracking per team policy. Use the PyMongo `appname` kwarg — not the connection string parameter — so users can't accidentally overwrite it when pasting their own Atlas URI.

```python
APP_NAME = "devrel-presentation-python-financial-coach-oreilly"

client = MongoClient(MONGODB_URI, appname=APP_NAME)
```

If the demo code is published to a GitHub repo, use a separate appName for the repo and track both in Wrike:

```python
APP_NAME_GITHUB = "devrel-github-python-financial-coach-oreilly"
```

---

## 4. Hybrid Search: $rankFusion Deep Dive

This section is the deep-dive reference for Diagram E (Section 2). Diagram E shows the visual flow; this section provides the runnable pipeline code and the reasoning behind hybrid vs. single-mode search.

### The Pipeline

```python
pipeline = [
    {
        "$rankFusion": {
            "input": {
                "pipelines": {
                    "vector": [
                        {
                            "$vectorSearch": {
                                "index": "memory_vector_index",
                                "path": "embedding",
                                "queryVector": query_embedding,
                                "numCandidates": 50,
                                "limit": 5,
                                "filter": {
                                    "user_id": user_id,
                                    "is_active": True
                                }
                            }
                        }
                    ],
                    "text": [
                        {
                            "$search": {
                                "index": "memory_text_index",
                                "text": {
                                    "query": user_query,
                                    "path": ["subject", "fact"]
                                },
                                "filter": {
                                    "compound": {
                                        "must": [
                                            { "equals": { "path": "user_id", "value": user_id } },
                                            { "equals": { "path": "is_active", "value": True } }
                                        ]
                                    }
                                }
                            }
                        },
                        { "$limit": 5 }
                    ]
                }
            }
        }
    }
]
```

### How $rankFusion Works

- Runs vector and text pipelines **in parallel** (not sequential)
- Each pipeline returns ranked results with scores
- $rankFusion combines rankings using Reciprocal Rank Fusion (RRF)
- Documents that appear in both pipelines get boosted
- Documents that appear in only one pipeline still surface

### Two Query Types, One Pipeline

| Query Type | Vector behavior | Text behavior | Result |
|---|---|---|---|
| **Specific** ("What's my dining priority?") | Dining: 0.85, Travel: 0.81 | **Dining: 0.95** | Text widens the gap — Dining is decisively #1 |
| **Abstract** ("Where am I wasting money?") | **Snapshot: 0.88**, Cars: 0.84 | *(no matches)* | Vector carries it — Snapshot is #1 despite no keyword match |

### Why Not Route to One Search Type?

Alternative approach: build a routing layer that classifies each query as "semantic" or "keyword" and sends it to only one pipeline.

**Problems with routing:**
- The router itself is a source of errors (misclassification → wrong pipeline → bad results)
- The router adds latency (another LLM call or classifier)
- Many queries benefit from both signals simultaneously
- You're building and maintaining two code paths instead of one

**Hybrid search avoids all of this.** One pipeline, always. When text matches exist, they amplify. When they don't, vector handles it gracefully. The pre-filter scopes both pipelines to a small user partition before any search begins.

---

## 5. Prompt Templates

These are the actual prompts used in `generate_response()` and `write_memories()`. The exact wording matters — these control what the agent says, what it remembers, and what it ignores.

### System Prompt for `generate_response()`

```
You are a personal finance coach. You help users understand their spending patterns, align their spending with their stated priorities, and make informed financial decisions.

You have access to the user's memory context below. This includes their stated preferences, spending snapshots, and any active flags. Use this information to personalize your advice.

RULES:
- Reference the user's stated priorities when giving advice. If their spending contradicts their priorities, say so directly.
- Use specific numbers from snapshots when available. Don't generalize — say "$1,245/month on car payments" not "a lot on cars."
- If you don't have enough context to answer well, say so. Don't hallucinate financial details.
- Be direct and concise. This isn't therapy — it's financial coaching.
- Never invent transactions or spending data that isn't in your context.

<user_context>
{formatted_memories}
</user_context>
```

**Design notes:**
- The `<user_context>` block is where memories go after formatting — both baseline memories (from `load_baseline()`) and query-driven results (from `select_memories()`), merged and deduped.
- Rules are explicit about grounding in data — prevents the LLM from making up numbers.
- "Be direct" sets the tone so responses feel like coaching, not generic chatbot pleasantries.
- No mention of the memory system itself — the agent shouldn't say "I have a memory that says..."

### Memory Formatting Template (inside `generate_response()`)

This transforms raw memory documents into the context block that goes inside `<user_context>`.

```python
def format_memories(memories: list[dict]) -> str:
    """Format selected memories into a structured context block."""
    sections = {"preferences": [], "snapshots": [], "flags": []}
    
    for mem in memories:
        collection = mem["_collection"]  # tagged during retrieval
        if collection == "preferences":
            sections["preferences"].append(
                f"- {mem['structured_data']['area'].title()}: "
                f"{mem['structured_data']['priority']} priority "
                f"(user-stated)"
            )
        elif collection == "snapshots":
            sd = mem["structured_data"]
            top = ", ".join(
                f"{k.replace('_', ' ')}: ${v:,}" 
                for k, v in sd["top_categories"].items()
            )
            sections["snapshots"].append(
                f"- {sd['as_of_date']}: Income ${sd['income']:,}, "
                f"Fixed ${sd['fixed_expenses']:,}, "
                f"Discretionary ${sd['discretionary']:,}. "
                f"Top spending: {top}"
            )
        elif collection == "flags":
            sd = mem["structured_data"]
            sections["flags"].append(
                f"- ⚠ {sd['flag_type'].replace('_', ' ').title()}: "
                f"{mem['fact']}"
            )
    
    output = ""
    if sections["preferences"]:
        output += "Stated Preferences:\n" + "\n".join(sections["preferences"]) + "\n\n"
    if sections["snapshots"]:
        output += "Spending Snapshots:\n" + "\n".join(sections["snapshots"]) + "\n\n"
    if sections["flags"]:
        output += "Active Flags:\n" + "\n".join(sections["flags"]) + "\n"
    
    return output.strip()
```

**Design notes:**
- Groups by type with clear headers — the LLM sees structure, not a jumble of memories.
- Uses `structured_data` for formatting, not `fact` — so the context block is crisp and consistent regardless of how the LLM originally phrased the fact.
- Flags get a ⚠ prefix so they visually pop in the context.
- This is what the Context tab in the demo displays.

**Example output (~300 tokens):**
```
Stated Preferences:
- Dining: high priority (user-stated)
- Travel: high priority (user-stated)
- Cars: low priority (user-stated)

Spending Snapshots:
- 2026-02-01: Income $12,500, Fixed $6,870, Discretionary $1,000. Top spending: car payments: $1,245, dining: $890, groceries: $650

Active Flags:
- ⚠ Spending Mismatch: User states fitness is high priority but spending is $0. Car payments ($1,245/mo) consuming budget.
```

### Extraction Prompt for `write_memories()`

This is the prompt sent to Claude *after* the response is generated, to determine if any new memories should be written.

```
You just had this exchange with a user:

USER: {user_message}
ASSISTANT: {assistant_response}

Your task: extract any new facts worth remembering as structured memory units. Only extract facts that are:
1. Explicitly stated by the user (preferences, priorities, life details)
2. Inferred from cross-referencing existing data (mismatches, patterns, anomalies)

Do NOT create memories for:
- Things already in the existing memory context (no duplicates)
- Vague or uncertain statements ("I might want to..." — wait until they commit)
- Transient conversational details ("thanks!" or "ok sounds good")

For each memory unit, provide:

```json
[
  {
    "collection": "preferences" | "flags",
    "subject": "short topic label",
    "fact": "natural language statement the LLM can read",
    "structured_data": { ... },
    "citations": ["source_ids"],
    "expires_in_days": null | number
  }
]
```

If no new memories should be created, return an empty array: []

EXISTING MEMORIES (do not duplicate):
{existing_memory_summaries}
```

**Design notes:**
- Explicitly tells the LLM what NOT to remember — this is the primary defense against over-remembering.
- `expires_in_days` is used for flags only — the app converts this to an `expires_at` datetime.
- `existing_memory_summaries` prevents duplicates — the LLM sees what's already stored and skips it.
- Returns JSON array — empty array is a valid response (most turns don't produce new memories).
- Only `preferences` and `flags` are writable by the agent. `snapshots` are computed from transactions via a separate pipeline, not extracted from conversation.

### Why Two LLM Calls Per Turn

The agent makes two Claude calls per user message:
1. `generate_response()` — produce the user-facing answer
2. `write_memories()` — extract new memory units from the exchange

**Why not one call?** Combining generation and extraction in a single prompt degrades both. The generation prompt needs to focus on being a good coach. The extraction prompt needs to focus on structured output. Mixing them leads to the LLM either over-annotating its response with memory metadata or under-extracting because it's focused on being helpful.

**Cost implication:** Two calls per turn at Claude Sonnet 4.5 pricing. At demo scale, negligible. At production scale, the extraction call can be routed to a smaller/cheaper model if the structured output quality holds up — this is where backbone model sensitivity (see Concepts doc, Section 10: Academic Grounding) becomes relevant.

---

## 6. Scaling Notes

The demo runs with 1 user, ~5 memories, ~50 transactions. Here's what changes at production scale.

### Scale Thresholds

| Scale | Users | Memories/User | Total Memories | What Changes |
|---|---|---|---|---|
| **Demo** | 1 | 5 | 5 | Nothing — everything fits in context |
| **Small app** | 100 | 50 | 5,000 | Need proper indexing, pre-filters mandatory |
| **Medium app** | 10K | 200 | 2M | Need sharding strategy, consider reranking |
| **Large app** | 1M | 500 | 500M | Need partition strategy, Compress + Isolate, tiered memory |

### What Stays the Same at Scale

- **Base schema** — `fact` + `structured_data` + `embedding` + `citations` + `is_active` doesn't change
- **Four-function architecture** — `load_baseline()` → `select_memories()` → `generate_response()` → `write_memories()` still works
- **Hybrid search pipeline** — `$rankFusion` with `$vectorSearch` + `$search` is the same pipeline
- **Pre-filters** — `user_id` + `is_active` scopes every query to a small partition regardless of total collection size
- **TTL expiration** — works the same at any scale, MongoDB handles it

### What Changes at 10K Users / 2M Memories

**Index sizing:**
- Vector index (1024 dims, cosine) grows with document count. At 2M documents, the HNSW graph is larger but still fast with pre-filters narrowing candidates.
- Pre-filter is the key — `user_id` + `is_active` means each search only scores ~100-200 memories, not 2M.
- Text index scales well — standard Atlas Search indexing handles millions of documents.

**Reranking:**
- At 50+ memories per user, `$rankFusion` might return top-5 that aren't the ideal top-5.
- Add Voyage AI reranking as a post-processing step: take top-10 from `$rankFusion`, rerank with Voyage, return top-5.
- ~10-20ms additional latency. Still dwarfed by LLM generation.

**Memory hygiene:**
- Over-remembering becomes more costly — 500 low-quality memories per user degrades search precision.
- Need stricter extraction criteria or a periodic memory consolidation job.
- Consolidation: merge multiple related memories into a summary memory, deactivate originals. This is the Compress operation from context engineering.

### What Changes at 1M Users / 500M Memories

**Partition strategy:**
- Shard by `user_id` — all of a user's memories on the same shard.
- Each shard handles search for its users independently.
- MongoDB Atlas handles this with built-in sharding.

**Tiered memory:**
- Not all memories are equal. Preferences (permanent, high value) vs. flags (temporary, lower value) vs. old snapshots (historical, rarely accessed).
- Hot tier: current preferences + latest snapshot + active flags. Indexed, fast.
- Cold tier: historical snapshots, expired flags (kept for audit). Archived, not indexed for search.
- This is the Isolate operation — separating memory tiers so search only hits the hot tier.

**Compress at scale:**
- A user with 500 memories from 2 years of interaction has a lot of redundancy.
- Periodic consolidation: "User has mentioned dining positively 47 times across 23 sessions" → one consolidated preference memory with high confidence.
- Original memories kept in cold tier for provenance, consolidated memory in hot tier for search.

**Multi-agent memory sharing:**
- Different agents (finance coach, travel planner, health advisor) sharing a common user memory layer.
- Shared preferences collection, agent-specific flags collections.
- Requires access control: which agent can read/write which collections.
- Out of scope for this talk — covered in the SF .local talk on multi-agent systems.

### Latency at Scale

| Operation | Demo (5 memories) | 10K users (200/user) | 1M users (500/user) |
|---|---|---|---|
| Voyage embed (query) | ~20ms | ~20ms | ~20ms |
| $rankFusion search | ~5ms | ~15ms | ~25ms (with pre-filter) |
| Voyage rerank (top-10) | N/A | ~15ms | ~15ms |
| Claude generation | ~800ms | ~800ms | ~1000ms (larger context) |
| Voyage embed (write) | ~20ms | ~20ms | ~20ms |
| MongoDB insert | ~5ms | ~5ms | ~10ms |
| **Total** | **~850ms** | **~875ms** | **~1090ms** |

**The LLM call dominates at every scale.** Search latency is noise. This is why optimizing the database is rarely the bottleneck — optimizing what goes *into* the context window (memory quality) matters more than optimizing how fast you get it there.

### Q&A Responses

- *"Does this scale?"* → "The pre-filter is the key. Every search is scoped to one user's active memories before any vector math happens. At 200 memories per user, you're searching a small set regardless of whether you have 10K or 1M total users. The LLM call is 50x slower than the search — the database is never the bottleneck."

- *"When do you need reranking?"* → "When a user has 50+ memories and the top-5 from $rankFusion isn't precise enough. Add Voyage reranking as a post-processing step on the top-10. Maybe 15ms extra latency. You'll know you need it when the agent starts referencing memories that feel off-topic."

- *"How do you handle memory bloat?"* → "Two mechanisms. First, TTL auto-expires working memory — flags clean themselves up. Second, at scale you add a consolidation job that merges related memories into summaries. That's the Compress operation we mentioned — it matters at hundreds of memories per user, not at five."