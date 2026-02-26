# Engineering Context Quality by Architecting Agent Memory

## Concepts, Definitions & Positioning

**Talk:** O'Reilly AI Superstream, 30 min
**Speaker:** Mikiko Bazeley, Staff Developer Advocate, MongoDB
**Companion doc:** `oreilly-talk-app-spec.md` — schemas, diagrams, prompts, sample data, scaling

### Contents

**Foundations**

| # | Section | What It Covers |
|---|---------|---------------|
| 0 | Where Does an Agent Live | The agent as a reasoning layer between users and infrastructure |

**Core Framework**

| # | Section | What It Covers |
|---|---------|---------------|
| 1 | The Core Argument | Why memory engineering matters — the 95% AI pilot failure rate |
| 2 | Context Engineering vs. Memory Engineering | Scope, operations, relationship between the two disciplines |
| 3 | Reference Knowledge vs. Agent Memory | Two data layers RAG can access — and why the distinction matters |
| 4 | The Data Hierarchy | Four layers from raw data to context window |
| 5 | Three Moves | Write, Select, Inject — the agent's memory operations |
| 6 | The Memory Lifecycle | Write → Select → Inject → Update → Expire |

**Production Depth**

| # | Section | What It Covers |
|---|---------|---------------|
| 7 | Error Modes and Edge Cases | Five failure modes of agent-authored memory |
| 8 | Eval Framework | Three dimensions: retrieval quality, write quality, coverage |
| 9 | Four-Pipeline Architecture | Ingestion → Retrieval → Learning → Maintenance, with Moves-to-Pipelines mapping |

**Landscape & Positioning**

| # | Section | What It Covers |
|---|---------|---------------|
| 10 | Academic Grounding | Hu et al. survey taxonomy + Jiang et al. empirical findings |
| 11 | Frameworks vs. MongoDB Primitives | Mem0/Zep/Letta vs. native MongoDB — what you gain and lose |
| 12 | Positioning: GraphRAG vs. Agent Memory | Conceptual comparison — complementary approaches, not competing |

**Talk Logistics**

| # | Section | What It Covers |
|---|---------|---------------|
| 13 | Five Takeaways | What the audience walks away with |
| 14 | References | Papers, blogs, resources for the "Go Deeper" slide |
| 15 | In Scope vs. Out of Scope | What we demonstrate, what we mention, what we cut |

---

## 0. Where Does an Agent Live

### The General Case

An agent is the reasoning layer between the user and the application's infrastructure. It's not the UI. It's not the database. It's not the LLM. It's the orchestration code that decides what to do with each user interaction.

```
┌─────────────────────────────────────────────────────────────┐
│                         APPLICATION                          │
│                                                             │
│  ┌──────────┐                              ┌─────────────┐ │
│  │          │    ┌──────────────────────┐   │             │ │
│  │   USER   │◄──►│       AGENT          │◄──►│ INFRASTRUCTURE│
│  │INTERFACE │    │                      │   │             │ │
│  │          │    │  • Receives input     │   │ • Database  │ │
│  │ (UI/API) │    │  • Reasons over it    │   │ • APIs      │ │
│  │          │    │  • Decides actions    │   │ • LLM calls │ │
│  │          │    │  • Returns output     │   │ • Embeddings│ │
│  └──────────┘    └──────────────────────┘   └─────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

In a traditional app, the application logic layer does the same thing — receives requests, processes them, talks to databases and services, returns responses. An agent is that layer, but with an LLM doing the reasoning instead of hardcoded business logic.

**What makes it an "agent" and not just an "LLM call":**
- It makes decisions about what to do (not just what to say)
- It can take actions — read from a database, write to a database, call external services
- It can reason over multiple sources of information to produce a response
- In a memory-enabled agent: it decides what to remember and what to recall

### When You Don't Need an Agent

Not every feature in an application needs an agent. An agent adds a reasoning layer — which means LLM calls, latency, cost, and complexity. If the task doesn't require reasoning, skip the agent and query the database directly.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            APPLICATION                                   │
│                                                                         │
│  ┌──────────┐     ┌──────────────────┐     ┌─────────────────────────┐ │
│  │          │     │    AGENT         │     │     INFRASTRUCTURE      │ │
│  │   USER   │◄───►│  (reasoning)     │◄───►│                         │ │
│  │INTERFACE │     │                  │     │  ┌───────────────────┐  │ │
│  │          │     └──────────────────┘     │  │    MongoDB Atlas  │  │ │
│  │          │                              │  │                   │  │ │
│  │          │◄────────────────────────────►│  │  • full-text      │  │ │
│  │          │     direct query             │  │  • vector search  │  │ │
│  │          │     (no agent needed)        │  │  • hybrid search  │  │ │
│  │          │                              │  │  • aggregation    │  │ │
│  └──────────┘                              │  └───────────────────┘  │ │
│                                            └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

**Use the agent when the task requires reasoning:**
- "Where am I wasting money?" → needs to cross-reference priorities against spending patterns, weigh trade-offs, generate personalized advice
- "What should I focus on this month?" → needs to synthesize snapshot data, active flags, and preferences into a coherent recommendation
- Extracting a new preference from conversation → needs to decide if something is worth remembering, structure it, check for contradictions

**Query MongoDB directly when the task is retrieval:**
- "Show me my February transactions" → `db.transactions.find({ user_id, month: "2025-02" })` — no reasoning needed, just a filter
- "What are my active memories?" → `db.memories.find({ user_id, is_active: true })` — display what's stored
- "Find memories about dining" → `$search` on the `fact` field, or `$vectorSearch` with an embedded query — retrieval, not reasoning
- Dashboard views, spending charts, memory inspection panels → all direct queries

**The principle:** MongoDB's search capabilities (full-text, vector, hybrid via `$rankFusion`, aggregation pipelines) are powerful enough to serve many features without an LLM in the loop. The agent should only be invoked when the user needs *reasoning over* the data, not just *access to* the data. Every unnecessary agent call is wasted latency, cost, and complexity.

**In our demo:** The sidebar makes this distinction visible. Each tab serves double duty — it shows what the agent sees AND lets the audience bypass the agent to query MongoDB directly:

- **Memory tab** — displays the user's active memories. A "View raw query" toggle reveals the underlying `db.memories.find({ user_id, is_active: true })` command and raw JSON response. The point: "This is just a MongoDB query. No agent involved."
- **Search tab** — displays hybrid search results after each message. A "Run search only" button executes the same `$rankFusion` pipeline but skips agent reasoning — showing ranked results without interpretation. The audience sees what retrieval looks like without the reasoning layer.
- **Data tab** — displays raw transactions via `db.transactions.find()`. This is Layer 1 data that the agent never searches directly. The audience sees the raw material that gets aggregated into snapshots. This is the "before" to the snapshot's "after."
- **Context tab** — displays the assembled context window. No direct-query equivalent — this tab exists only because the agent exists.

The chat interface routes through the agent. The sidebar tabs can show the same data without the agent. Same database, same collections, two access patterns. The audience sees the difference live.

### Without Memory

Most agents today are stateless. They receive a request, assemble a context window from whatever's available right now, call the LLM, return a response, and forget everything. The next request starts from zero.

```
User message → Agent assembles context → LLM generates → Response → (nothing persists)
```

This works for single-turn tasks. It fails for anything that requires continuity — ongoing relationships, personalization, learning from past interactions.

### With Memory

A memory-enabled agent adds two capabilities to the basic loop:

1. **It reads from persistent memory** — before and during each interaction, it loads relevant knowledge from past interactions (deterministic SELECT at session start, query-driven SELECT per message)
2. **It writes to persistent memory** — after each interaction, it decides what's worth remembering and stores it as structured memory units

```
                    ┌─────────────────────────────┐
                    │        MEMORY STORE          │
                    │  (persistent, searchable)    │
                    └──────┬──────────────┬────────┘
                     reads │              │ writes
                    ┌──────▼──────────────▼────────┐
User message ──────►│          AGENT               │──────► Response
                    │                              │
                    │  1. SELECT from memory        │
                    │  2. Assemble context window   │
                    │  3. LLM generates response    │
                    │  4. WRITE new memories         │
                    └──────────────────────────────┘
```

The agent is still the reasoning layer. Memory is what makes it a *learning* reasoning layer. Each interaction makes the next one better.

### In Our Demo

The agent is the Python orchestration code — roughly four functions:

| Function | What it does | When it runs |
|---|---|---|
| `load_baseline()` | Deterministic SELECT — fetches latest snapshot + top preferences | Once per session |
| `select_memories()` | Query-driven SELECT — hybrid search for relevant memories | Every user message |
| `generate_response()` | INJECT + LLM call — assembles context window, calls Claude | Every user message |
| `write_memories()` | WRITE — extracts new memories from the conversation turn | Every user message (can be async) |

The infrastructure around it:
- **MongoDB Atlas** — the memory store (and data source for transactions)
- **Voyage AI** — embedding service for vector search
- **Claude Sonnet 4.5** — the LLM that reasons and generates
- **Streamlit** — the web framework serving the UI

The agent is not MongoDB. The agent is not Claude. The agent is the ~200 lines of Python that decide *when* to call each service and *what* to do with the results. Memory engineering is about making that agent smarter over time by giving it a persistent, structured, searchable knowledge base that it reads from and writes to.

The sidebar tabs make this concrete — the Memory, Search, and Data tabs show what MongoDB can do on its own (direct queries, full-text search, vector search, hybrid search, aggregation). The chat shows what happens when you add an agent on top. Same data, different access patterns, different outcomes.

---

## 1. The Core Argument

Most GenAI systems fail because they're stateless. Every request starts from zero. MIT research shows 95% of AI pilots get zero return — the core barrier isn't infrastructure, regulation, or talent. It's learning. Most GenAI systems do not retain feedback, adapt to context, or improve over time.

Context engineering is the discipline of controlling what the LLM sees at inference time. It's powerful — but without persistence, it's Groundhog Day. Every session starts from scratch. Every context window is assembled from nothing.

**Memory engineering is the persistence layer that makes context engineering compound over time.**

Without memory engineering, context engineering is per-request optimization. With it, the agent accumulates knowledge that makes each subsequent context window better. The agent learns.

---

## 2. Context Engineering vs. Memory Engineering

### Context Engineering (the broader discipline)

Controls everything the LLM sees at inference time: system prompts, tool results, conversation history, retrieved documents, memory — all of it.

**Scope:** Per-request. "What should the model see right now to do this task well?"

**Operations:**
- **Write** — create content that could enter the context window
- **Select** — choose which content to include (retrieval, filtering, ranking)
- **Compress** — reduce token count while preserving meaning
- **Isolate** — separate concerns across sub-agents or tool calls

You can do excellent context engineering with zero memory — just well-crafted prompts and good retrieval from static docs. But every session starts from scratch.

### Memory Engineering (the persistence subset)

Deals specifically with persistent, agent-managed knowledge that survives across requests.

**Scope:** Across-requests. "What should the agent know long-term, and how does that knowledge evolve?"

**Operations unique to memory engineering:**
- **Creation** — agent decides what's worth remembering (not everything is)
- **Structuring** — memory is stored as a structured unit with `fact` + `structured_data` + provenance, not a raw text dump
- **Versioning** — new knowledge supersedes old (`supersedes` field + `is_active` flag)
- **Expiration** — temporary knowledge auto-deletes (TTL indexes on `expires_at`)
- **Inference** — agent creates new memories by reasoning over existing memories (read-write, not just read)

**The overlap:** Select (both deterministic and query-driven modes) and Inject are context engineering operations that memory engineering relies on. But context engineering doesn't necessarily involve persistence, agent authorship, or lifecycle management.

### The Relationship

```
Context Engineering (per-request)
├── Prompt design
├── Tool result formatting
├── Conversation history management
├── Retrieval from reference knowledge (static docs)
└── Memory Engineering (across-requests)          ◀── THIS TALK
    ├── Agent writes structured memory units
    ├── Hybrid search selects relevant memories
    ├── Selected memories injected into context
    ├── Agent updates/versions existing memories
    └── Memories expire via TTL
```

**The one-liner:** Context engineering without memory is optimization. Context engineering with memory is learning.

---

## 3. Reference Knowledge Retrieval vs. Agent Memory

These are two different data layers that retrieval (RAG) can access. They're not competing — they serve different purposes.

### Reference Knowledge

- **About:** The domain — how things work, policies, documentation
- **Written by:** Humans (or agents) index it
- **Scope:** Shared across all users
- **Lifecycle:** Relatively static — updated by humans on a schedule
- **Citations:** External documents
- **Pattern:** Read-only retrieval
- **Example:** "What's our refund policy?" → retrieve from policy docs

### Agent Memory

- **About:** This user — what they care about, what happened, what the agent inferred
- **Written by:** The agent, from its own reasoning
- **Scope:** Per-user, per-session
- **Lifecycle:** Dynamic — write, update (supersede), expire (TTL)
- **Citations:** Other memories + raw data sources
- **Pattern:** Read-write learning
- **Example:** "User prioritizes dining and travel over cars" → agent wrote this from conversation

### RAG is a Retrieval Pattern, Not a Data Type

RAG can access either layer. The difference is what the data represents and who creates it. Most teams stop at reference knowledge retrieval and call it "RAG." That's valuable but read-only. Agent memory adds the write side — the `store_memory` tool call is the fundamental difference.

---

## 4. The Data Hierarchy

Four layers, from raw sources to what the LLM actually sees:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              LAYER 3: CONTEXT WINDOW                                     │
│                              (what the LLM sees right now)                               │
│                                                                                         │
│  system prompt + baseline memories + selected memories + retrieved docs + user query      │
│  ~300 tokens of the RIGHT context, assembled per-request, ephemeral                      │
└──────────┬─────────────────────┬────────────────────┬──────────────────────┬─────────────┘
           │                     │                    │                      │
           │ ▲ SELECT            │ ▲ INJECT (Move 3)  │                      │ ▲
           │ │ (deterministic)   │ │ format + insert   │                      │ │ semantic
           │ │ session start:    │ │ into prompt       │ WRITE (Move 1)      │ │ search
           │ │ fetch core        │ │                   │ LLM reasons over    │ │ retrieves
           │ │ memories (latest  │ │ ▲ SELECT (Move 2) │ memories and creates│ │ docs
           │ │ snapshot, top     │ │ │ (query-driven)  │ new memories        │ │
           │ │ preferences)      │ │ │ hybrid search   │                     │ │
           │ │                   │ │ │ retrieves top-k ▼                     │ │
┌──────────┴─┴───────────────────┴─┴─┴────────────────────────────┐  ┌─────┴─┴────────────┐
│                LAYER 2: AGENT MEMORY                             │  │  LAYER 4: REFERENCE │
│                (structured, searchable, agent-managed)            │  │  KNOWLEDGE          │
│                                                                  │  │  (not in this demo) │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │  │                     │
│  │🟢 preferences │ │🔵 snapshots  │ │ 🟡 flags     │            │  │  Policies, guides,  │
│  │  (semantic)   │ │  (episodic)  │ │  (working)   │            │  │  documentation      │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘            │  │                     │
│         │                │                │                      │  │  Indexed by humans, │
│  Written by the agent from reasoning                             │  │  shared across users│
│  Accessed via hybrid search (vector + text)                      │  │  Accessed via       │
│  ★ CORE OF THIS TALK                                            │  │  semantic search    │
└─────────┼────────────────┼────────────────┼─────────────────────┘  └─────────────────────┘
          │ ▲              │ ▲              │ ▲
          │ │ EXTRACT      │ │ AGGREGATE    │ │ INFER
          │ │ (from chat)  │ │ (from txns)  │ │ (from other
          │ │              │ │              │ │  memories)
┌─────────┴─┴──────────────┴─┴──────────────┴─┴──────────────────────────────────────────┐
│                              LAYER 1: DATA SOURCES                                      │
│                              (where info comes from)                                    │
│                                                                                         │
│  ⚪ transactions       ⚪ chat messages       ⚪ events / logs                           │
│                                                                                         │
│  Written by the application, not the agent                                              │
│  Accessed via direct queries, aggregation pipelines                                     │
│  NOT searched by the agent — provides provenance                                        │
└─────────────────────────────────────────────────────────────────────────────────────────┘


CONTEXT ASSEMBLY — TWO PHASES (both are SELECT + INJECT):

  Phase 1: SELECT in deterministic mode (session start)
  ─────────────────────────────────────────────────────
  No user query yet — no search involved.
  Fetch the user's latest snapshot and top preferences by recency/priority.
  This is the baseline context the agent has before the user says anything.
  For a new user, this returns nothing — the agent starts cold.
  Runs once per session.

  Phase 2: SELECT in query-driven mode (per request)
  ──────────────────────────────────────────────────
  Hybrid search triggered by the user's message.
  Retrieves top-k memories relevant to the current query.
  Merged with baseline context, formatted, and injected into the prompt.
  Runs on every user message.


THE CONCRETE NUMBERS (from our demo):

  Layer 1 (raw)              Layer 2 (memory)            Layer 3 (context)
  ─────────────              ────────────────            ─────────────────
  47 transactions ─AGGREGATE─▶ 1 snapshot      ─SELECT─▶ ~80 tokens (baseline, deterministic)
  "I love dining" ─EXTRACT──▶ 1 preference    ─SELECT─▶ ~40 tokens (per-request, query-driven)
  preferences ×   ─INFER───▶ 1 flag          ─SELECT─▶ ~60 tokens (per-request, query-driven)
    snapshot
                                               Total:    ~300 tokens
                                               (vs. ~12,000 tokens if you
                                                stuffed raw data in context)

  Passive info             Active memory              What the LLM reads
  (can't be searched)      (searchable, versioned,    (ephemeral, rebuilt
                            expires)                   every request)

◄──────────────────── THE LEARNING LOOP ────────────────────▶
The LLM reasons over Layer 2 memories and WRITES new memories
back to Layer 2 (Move 1). This is the only downward arrow in
the diagram — and it's what makes this a learning system.
```

### Layer 1: Data Sources (where info comes from)
- Transactions, chat messages, events, logs
- Written by the application, not the agent
- Accessed via direct queries, aggregation pipelines
- **Not searched by the agent** — provides provenance

### Layer 2: Agent Memory (structured, searchable, agent-managed)
- Preferences, snapshots, flags
- Written by the agent from reasoning over Layer 1 and other memories
- Accessed via hybrid search (vector + text)
- **The core of this talk**

### Layer 3: Context Window (what the LLM sees right now)
- System prompt + baseline memories + selected memories + retrieved docs + user query
- Assembled in two phases (both are SELECT + INJECT):
  - **Deterministic SELECT** (session start) — fetch core memories (latest snapshot, top preferences) without search. Runs once. Returns nothing for new users.
  - **Query-driven SELECT** (per request) — hybrid search retrieves memories relevant to the current query, merges with baseline, formats, and injects into prompt. Runs every message.
- ~300 tokens of the right memory beats 12,000 tokens of raw history

### Layer 4: Reference Knowledge (parallel path — not in this demo)
- Policies, guides, documentation
- Indexed by humans, shared across all users
- Accessed via semantic search, feeds into the context window alongside agent memory
- Most teams build this first — agent memory builds on top of it

### The Critical Transition: Data → Memory

Data becomes memory when it is:
1. **Aggregated** — raw transactions → monthly spending snapshot
2. **Encoded** — embedded (Voyage AI) + metadata (structured_data, citations)
3. **Stored** — as a structured memory unit with provenance

Before that point, it's passive information. After, it's active memory — persistent, contextually aware, and retrievable.

---

## 5. Three Moves

The agent does three things with memory: Write, Select, Inject.

### Move 1: WRITE — Agent creates structured memory units

The agent decides what's worth remembering and writes it to MongoDB as a structured memory unit.

**Two fields, two consumers:**
- `fact` — natural language the LLM reads ("User prioritizes dining and travel, deprioritizes cars and clothes")
- `structured_data` — typed fields the app reads (`{ area: "dining", priority: "high" }`)

**Three origins:**
- **User-stated** — extracted from conversation ("I love dining out") → highest trust
- **Computed** — derived from data (monthly spending snapshot from transactions) → grounded in source data
- **Inferred** — reasoned from other memories (spending mismatch flag) → trust varies, citations provide traceability

**This is what makes it NOT just RAG.** The agent is an author, not just a reader.

### Move 2: SELECT — Find the right memories

Select operates in two modes:

**Mode A: Deterministic (session start)**

Before the user sends a message, the agent loads baseline context — the user's latest snapshot and top preferences, fetched by recency and priority. No embedding, no search — just a direct query. This gives the agent a "warm" starting point for returning users. For new users, this returns nothing.

```
Session Start
    │
    └── Direct query ──→ Latest snapshot + top-k preferences by recency
                         Pre-filter: { user_id, is_active: true }
                         Sort: { updated_at: -1 }
```

**Mode B: Query-driven (per request)**

Every user message triggers hybrid search via `$rankFusion`:

```
User Query
    │
    ├── Voyage AI embed ──→ $vectorSearch (semantic similarity)  ──┐
    │   (query)                                                     │
    │                                                               ├──→ $rankFusion ──→ Top memories
    └── raw text ─────────→ $search (full-text on fact + subject) ──┘

Pre-filter on BOTH pipelines: { user_id, is_active: true }
```

Results are merged with baseline context (deduped — if a memory was already loaded at session start, it's not added twice).

**Why hybrid, not one or the other:**
- Specific queries ("What's my dining priority?") → text boosts keyword matches, vector confirms
- Abstract queries ("Where am I wasting money?") → vector carries it, text returns nothing (and that's fine)
- One pipeline handles both. No routing layer needed. No "is this semantic or keyword?" decision per request.

**Why parallel execution works:**
- Both pipelines run simultaneously, not sequentially
- Pre-filter scopes to this user's active memories before any vector math
- At demo scale: single-digit ms difference
- LLM generation is 50–100x slower than search anyway
- The real cost of not doing hybrid is building a routing layer — that router is its own source of errors and latency

### Move 3: INJECT — Selected memories enter the context window

Baseline memories (from deterministic SELECT) and per-request memories (from query-driven SELECT) are merged, deduped, formatted as a structured context block, and inserted into the system prompt before the LLM call.

**The payoff:** ~300 tokens of the RIGHT structured context produces dramatically different output than ~30 tokens of raw data summary. Same LLM, same transaction data, same user — completely different response.

**The demonstration:**
- Without memory: "Consider reducing your Uber and dining expenses" (generic)
- With memory: "Your cars are crowding out what you actually care about. Your dining spending is aligned — that's your thing, keep it." (personalized, priority-aware)

### Cold Start vs. Warm Start

The same three moves behave very differently depending on whether memories exist for this user.

**New user (cold start):**
- Deterministic SELECT returns nothing — no memories exist yet
- Context window contains only: system prompt + user query
- Agent response is generic — it doesn't know the user's priorities, spending patterns, or goals
- Every message is a learning opportunity: the agent extracts preferences from conversation and computes snapshots from transaction data
- The first few turns are the Write move doing heavy lifting — the agent is building its understanding from scratch

**Returning user (warm start):**
- Deterministic SELECT returns baseline context — latest snapshot, top preferences, active flags
- Before the user says a word, the agent already knows: spending patterns, stated priorities, behavioral mismatches
- First message is already personalized — the agent doesn't need to "warm up" or ask discovery questions
- Query-driven SELECT adds specificity on top of the baseline — retrieving memories relevant to whatever the user asks about

**Why this matters for agent quality:**
- Without deterministic SELECT, even a returning user's first message relies entirely on query-driven hybrid search. If the user says "hey, how am I doing?" — that's a vague query. Hybrid search on "how am I doing" might not retrieve the spending snapshot or priority preferences with high confidence.
- With deterministic SELECT, the baseline is already there. The vague query still works because the snapshot and preferences are already in the context window. Query-driven SELECT only needs to find *additional* relevant memories.
- The difference: "the agent always knows the basics about you" vs. "the agent only knows what the search query happens to retrieve."

**The demo arc shows this contrast directly:**
1. Create a new user → cold start, generic responses, watch memories form in real time
2. Switch to pre-loaded Alex profile → warm start, personalized from the first message
3. Return to the new user → the memories created in step 1 are now loaded, the agent "remembers"

This three-step arc is the clearest possible demonstration that memory makes the agent better over time.

---

## 6. The Memory Lifecycle

Memories aren't static. They're born, selected, updated, and expired.

```
WRITE ──→ SELECT ──→ INJECT ──→ UPDATE ──→ EXPIRE
  │                               │           │
  │  Agent creates memory         │           │
  │  from conversation,           │           │
  │  computation, or inference    │           │
  │                               │           │
  │                    New version supersedes  │
  │                    old (supersedes field   │
  │                    + is_active: false)     │
  │                                           │
  │                              MongoDB TTL index
  │                              auto-deletes when
  │                              expires_at passes
  │
  └──────────────── Agent reasons over memories
                    and creates NEW memories
                    (continuous learning cycle)
```

**Maps to context engineering operations:**
- Write → Write
- Select → Select
- Inject → (application of Select)
- Update → Write (new version) + Compress (old version deactivated)
- Expire → Isolate (expired knowledge removed from searchable pool)

This talk demonstrates Write, Select, and Inject. Compress and Isolate matter at scale — when the agent runs hundreds of turns or splits work across sub-agents.

---

## 7. Error Modes and Edge Cases

What can go wrong with agent-authored memory, and how to handle it. These are real failure modes, not theoretical — the "Anatomy of Agentic Memory" paper documents several of them.

### Error Mode 1: Over-Remembering

**What happens:** The agent creates a memory unit for every conversational turn. "User said hello" becomes a preference. "User asked about dining" becomes a preference. Memory count explodes, search quality degrades because there's too much noise.

**Root cause:** The extraction prompt doesn't have clear enough criteria for what's worth remembering.

**Defenses:**
- Extraction prompt explicitly lists what NOT to remember (vague statements, transient details, greetings)
- Extraction prompt includes existing memories so the LLM can avoid duplicates
- `structured_data` schema acts as a constraint — if the LLM can't fill in `area` and `priority` for a preference, it probably isn't one
- **Production defense:** rate-limit memory writes per session (e.g., max 3 new memories per conversation turn)

**Demo voiceover opportunity (Message 1):** "Notice the agent created two or three preference memories from that message, not ten. The extraction prompt tells it to only remember explicitly stated priorities — not every noun in the sentence."

### Error Mode 2: Contradictory Memories

**What happens:** User says "I love sushi" in January. User says "I've gone off sushi" in March. Both memories are active. Agent retrieves both and gives confused advice.

**Root cause:** No deduplication or conflict detection between new and existing memories.

**Defenses:**
- Extraction prompt includes existing memories — LLM is instructed to check for contradictions before writing
- If contradiction detected: new memory gets written with `supersedes` pointing to old memory's `_id`. Old memory gets `is_active: false`. Only one version is active.
- `is_active` pre-filter on all searches ensures only current memories are retrieved
- **Production defense:** before writing, run a similarity search for the new `fact` against existing memories in the same collection. If cosine similarity > 0.85, flag for dedup review (LLM decides: update, supersede, or skip)

**Demo voiceover opportunity:** Not demonstrated in the 5-message script, but excellent Q&A material. "If the user changed their mind about dining, the new preference would supersede the old one. The old memory isn't deleted — it's marked `is_active: false`. You keep the history, but search only returns the current version."

### Error Mode 3: Hallucinated Memory Content

**What happens:** The agent writes a memory with incorrect `fact` or `structured_data`. Example: user says "I spend too much on dining" and the agent creates a preference with `priority: low` for dining — misinterpreting "I spend too much" as "I don't want to spend on dining" when the user actually loves dining and is just noting the cost.

**Root cause:** LLM misinterprets nuance during extraction. The "silent failure" problem — the agent chats fluently while writing bad memories.

**Defenses:**
- `citations` field traces every memory back to its source. If the citation doesn't support the fact, it's detectable.
- `structured_data` can be schema-validated at the MongoDB level (e.g., `priority` must be `"high"` or `"low"`, `area` must be one of a known set)
- **Production defense:** periodic audit loop — sample memories, check `fact` against `citations`, measure accuracy. This is the eval framework (Section 8).
- **Demo-level defense:** the extraction prompt is explicit about only extracting "explicitly stated" preferences, not inferred sentiment

**Q&A response:** "The paper calls this 'silent failure' — the agent sounds great but its memory is corrupted. That's why `citations` matter. Every memory points back to its source. If you can't verify the memory against its citation, you've found a bad write."

### Error Mode 4: Stale Memories That Should Have Expired

**What happens:** A flag memory is created with `expires_at` 30 days out, but the underlying situation changes in 3 days (user pays off car). The flag is still active and the agent keeps referencing an outdated mismatch.

**Root cause:** TTL is a time-based heuristic, not event-driven. The memory system doesn't know the situation changed.

**Defenses:**
- `expires_at` is conservative — flags expire, they just might expire later than ideal
- New snapshots trigger a re-evaluation: when a new snapshot is computed, `write_memories()` can check if any active flags are invalidated by the new data
- **Production defense:** event-driven invalidation — when key data changes (e.g., new snapshot computed), run a sweep of active flags and deactivate any that are no longer valid
- The "worst case" is giving slightly outdated advice for a few days/weeks, not permanently wrong advice

### Error Mode 5: Missing Memories (Under-Remembering)

**What happens:** The user states a clear preference but the agent doesn't extract it. The preference never enters the memory system.

**Root cause:** Extraction prompt too conservative, or the LLM didn't recognize the statement as a preference.

**Defenses:**
- Less dangerous than over-remembering or hallucination — the agent just doesn't personalize as well
- If the user restates the preference, the agent gets another chance to extract it
- **Production defense:** coverage eval (Section 8) — compare what the user said vs. what got extracted, measure recall

### Error Summary Table

| Error Mode | Severity | Detection | Prevention |
|---|---|---|---|
| Over-remembering | Medium | Memory count growth rate | Extraction prompt criteria, schema constraints, rate limits |
| Contradictions | High | Duplicate active memories for same subject | Similarity check before write, `supersedes` + `is_active` |
| Hallucinated content | High | Citation verification fails | Schema validation, audit loop, explicit extraction rules |
| Stale memories | Low-Medium | Active flags contradicted by new data | TTL expiration, event-driven invalidation |
| Under-remembering | Low | Coverage eval shows missed preferences | Prompt tuning, repeated extraction opportunities |

---

## 8. Eval Framework for Agent Memory

Out of scope for the demo, but essential for production and strong Q&A material. Three dimensions of evaluation.

### Dimension 1: Retrieval Quality — "Did we select the right memories?"

**What to measure:** Given a user query, did `select_memories()` return the memories that would produce the best response?

**Metrics:**
- **Precision@k** — of the top-k memories returned, how many were relevant to the query?
- **Recall@k** — of all relevant memories for this query, how many appeared in the top-k?
- **Mean Reciprocal Rank (MRR)** — was the most relevant memory ranked first?

**How to eval:**
1. Create a test set: 20-30 (query, relevant_memories) pairs
2. Run `select_memories()` on each query
3. Compare returned memories to ground truth
4. Calculate precision, recall, MRR

**What this catches:** Bad index configuration, wrong pre-filters, embedding quality issues, cases where text search should carry but doesn't (or vice versa).

**Tuning levers:** Number of candidates in `$vectorSearch`, `$limit` on text pipeline, embedding model choice, whether to add reranking.

### Dimension 2: Write Quality — "Did the agent create correct memories?"

**What to measure:** When `write_memories()` creates a new memory unit, is the `fact` accurate? Is the `structured_data` correct? Are the `citations` valid?

**Metrics:**
- **Fact accuracy** — does the `fact` field correctly represent what the user said or what the data shows?
- **Schema validity** — does `structured_data` conform to expected types and values? (e.g., `priority` is "high" or "low", not "very high" or "medium")
- **Citation validity** — do the `citations` actually support the `fact`? Can you trace the memory back to its source?
- **Duplication rate** — how often does the agent create a memory that duplicates an existing one?

**How to eval:**
1. Collect all memories written during a test session (or a sample from production)
2. For each memory:
   a. Retrieve the cited source(s)
   b. LLM-as-judge: "Does this fact accurately represent the cited source?" (yes/no + explanation)
   c. Schema validation: check `structured_data` against expected types
   d. Dedup check: cosine similarity against existing memories — any > 0.9?
3. Calculate accuracy rate, schema violation rate, duplication rate

**What this catches:** Hallucinated memories, misinterpreted user statements, schema drift, extraction prompt failures. This is the "silent failure" detector.

**Tuning levers:** Extraction prompt wording, `existing_memory_summaries` content, schema validation rules, similarity threshold for dedup.

### Dimension 3: Coverage — "Did we remember everything worth remembering?"

**What to measure:** When the user states a preference, shares a life detail, or asks something that implies a priority — did the agent extract it?

**Metrics:**
- **Extraction recall** — of all "memory-worthy" statements in a conversation, what percentage got extracted?
- **Latency to memory** — how many turns after the user states something does it become a memory? (Ideally: same turn)

**How to eval:**
1. Take a test conversation transcript
2. Human annotator (or LLM-as-judge) identifies all "memory-worthy" statements
3. Compare against what `write_memories()` actually extracted
4. Calculate recall

**What this catches:** Under-remembering — the extraction prompt is too conservative, or the LLM misses implicit preferences.

**Tuning levers:** Extraction prompt criteria (loosen to improve recall, tighten to improve precision — classic tradeoff).

### Evaluation Pipeline (Lightweight)

For production, run this periodically (weekly or per-release):

```
1. RETRIEVAL EVAL
   Test set: 30 (query, expected_memories) pairs
   Run select_memories() on each
   → Precision@5, Recall@5, MRR

2. WRITE EVAL  
   Sample: 50 most recent memories from production
   For each: verify fact vs citations, validate schema, check dedup
   → Accuracy rate, schema violation rate, duplication rate

3. COVERAGE EVAL
   Sample: 10 recent conversation transcripts
   Annotate memory-worthy statements
   Compare vs actual extractions
   → Extraction recall

4. END-TO-END EVAL
   Sample: 20 conversations with known user profiles
   Run full pipeline: select → generate → write
   LLM-as-judge: "Is this response appropriately personalized given the user's memories?"
   → Personalization score (1-5)
```

### The Eval Hierarchy

```
                    ┌─────────────────────┐
                    │ End-to-End Quality  │  ← "Is the agent giving good advice?"
                    │ (Personalization)   │
                    └─────────┬───────────┘
                              │ depends on
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │  Retrieval   │ │    Write     │ │   Coverage   │
    │  Quality     │ │   Quality    │ │              │
    │              │ │              │ │              │
    │ "Right       │ │ "Correct     │ │ "Everything  │
    │  memories    │ │  memories    │ │  worth       │
    │  selected?"  │ │  created?"   │ │  remembering │
    │              │ │              │ │  captured?"  │
    └──────────────┘ └──────────────┘ └──────────────┘
```

If end-to-end quality is low, diagnose by checking which dimension is failing. Bad retrieval? Tune search. Bad writes? Tune extraction prompt. Bad coverage? Loosen extraction criteria.

### Q&A Responses

- *"How do you evaluate memory quality?"* → "Three dimensions: retrieval quality — are we selecting the right memories? Write quality — is the agent creating accurate memories? Coverage — are we catching everything worth remembering? You can start with 30 test queries and 50 sampled memories. That's enough to find the big problems."

- *"How do you know the agent isn't writing garbage?"* → "Citation verification. Every memory has a `citations` field pointing to its source. Sample memories, check the citation against the fact. If they don't match, you've found a bad write. At scale, you automate this with LLM-as-judge — 'does this fact accurately represent this source?' — and track the accuracy rate over time."

- *"What's the most common failure mode?"* → "Over-remembering. The agent creates memories for things that aren't worth remembering, which dilutes search quality. The fix is in the extraction prompt — be explicit about what NOT to remember. Second most common: stale memories that should have been invalidated by new data. TTL handles the time-based case; event-driven invalidation handles the rest."

---

## 9. Four-Pipeline Architecture for Agent Memory Systems

A production agent memory system decomposes into four independent pipelines, each with a different cadence, compute profile, and failure mode. This is the systems-level view of memory engineering.

### The Four Pipelines

```
INGESTION              RETRIEVAL              LEARNING               MAINTENANCE
(batch / event)        (real-time, read)      (real-time, write)     (scheduled)

Raw Data               User Query             Conversation Turn      Memory Store
  │                      │                      │                      │
  ▼                      ▼                      ▼                      ▼
Aggregate /            Embed query            Extract new            Version check
Transform              (Voyage, "query")      memory units           (supersedes →
  │                      │                    (Claude)               is_active:false)
  ▼                      ▼                      │                      │
Extract structured     Hybrid search            ▼                      ▼
memory units           ($rankFusion)          Embed facts            Expire stale
  │                      │                    (Voyage, "document")   (TTL + event-
  ▼                      ▼                      │                    driven)
Embed facts            Format context            ▼                      │
(Voyage, "document")   + generate             Validate schema          ▼
  │                    response (Claude)         │                    Consolidate
  ▼                      │                      ▼                    redundant
Validate schema          ▼                    Insert to MongoDB        │
+ store                RESPONSE                 │                      ▼
  │                    (to user)                ▼                    Evaluate
  ▼                                          NEW MEMORIES            quality
MEMORY STORE ◄──────────────────────────────────┘                      │
  ▲                                                                    │
  └────────────────────────────────────────────────────────────────────┘
```

### Pipeline 1: Ingestion — "Raw Data → Structured Memory"

**Cadence:** Batch (nightly, weekly) or event-triggered (new data arrives)
**Compute:** Data processing + embedding generation. No LLM inference required for structured transformations; LLM optional for unstructured extraction.

**What it does:**
- Transforms operational data into agent-readable memory units
- Transactions → aggregation pipeline → spending snapshot (episodic memory)
- External data feeds → normalization → reference updates
- Generates embeddings for new memory units (Voyage AI, `input_type="document"`)
- Schema validation before write
- Deduplication against existing memories

**In our demo:** The pre-loaded February spending snapshot was produced by this pipeline. It ran once: aggregated 47 transactions into a single structured snapshot document with nested `structured_data`, embedded the `fact` field, and inserted to the `snapshots` collection.

**Failure modes:** Bad aggregation logic, schema violations, stale source data, embedding drift.
**Eval:** Compare snapshot `structured_data` against raw transaction totals. Verify `citations` point to valid source records.

### Pipeline 2: Retrieval — "Query → Context → Response"

**Cadence:** Real-time. Two phases: once at session start (deterministic), then per-request (query-driven). Synchronous with the user.
**Compute:** Session start: one MongoDB direct query. Per request: one Voyage embed call + one MongoDB hybrid search + one Claude generation call.

**What it does:**

*Session start (deterministic SELECT):*
- Fetches the user's latest snapshot and top preferences by recency/priority
- Direct query — no embedding, no search. Returns nothing for new users.
- Establishes baseline context before the user sends a message

*Per request (query-driven SELECT + INJECT):*
- Embeds the user query (Voyage AI, `input_type="query"`)
- Runs `$rankFusion` hybrid search (vector + text, pre-filtered to user's active memories)
- Merges results with baseline context (deduped)
- Formats all selected memories into structured context block
- Assembles system prompt + context + user message
- Calls Claude Sonnet 4.5 for response generation
- Returns response to user

**In our demo:** This is `load_baseline()` at session start + `select_memories()` + `generate_response()` per message. The Search tab and Context tab in the sidebar show its internals.

**Failure modes:** Wrong memories retrieved (retrieval precision), irrelevant memories dilute context, context formatting loses information, LLM ignores context, baseline fetch returns stale snapshot.
**Eval:** Retrieval quality — Precision@k, Recall@k, MRR. End-to-end — is the response appropriately personalized?

**This is the read path.** It consumes from the memory store but never writes to it.

### Pipeline 3: Learning — "Conversation → New Knowledge"

**Cadence:** Real-time, per-request. Can be synchronous (blocks before response returns) or asynchronous (fires after response is sent, reducing user-perceived latency).
**Compute:** One Claude call (extraction) + one Voyage embed call per new memory + one MongoDB insert per new memory.

**What it does:**
- Takes the conversation turn (user message + agent response + existing memories)
- Asks Claude to extract any new memory-worthy units
- For each new unit:
  - Validates against extraction criteria (is this worth remembering?)
  - Checks for contradictions with existing memories (similarity search + LLM comparison)
  - If contradiction: supersede old memory (`is_active: false`, new memory gets `supersedes` pointer)
  - Embeds the `fact` field (Voyage AI, `input_type="document"`)
  - Validates schema
  - Inserts to appropriate MongoDB collection
- Most turns produce zero new memories. Some produce one. Rarely more than three.

**In our demo:** This is `write_memories()`. Message 1 triggers it to create 3 preference memories. Message 4 triggers it to create 1 flag memory. Messages 2, 3, and 5 trigger it but it correctly decides nothing is worth remembering.

**Failure modes:** Over-remembering (too many low-value memories), hallucinated content (fact doesn't match what user said), missed extraction (under-remembering), schema violations, contradictions not detected.
**Eval:** Write quality — fact accuracy, schema validity, citation validity, duplication rate. Coverage — extraction recall.

**This is the write path.** It's the pipeline that makes the agent a learning system, not just a retrieval system. Separating it from the Retrieval Pipeline is architecturally important because:
- They have different failure modes (retrieval precision vs. write accuracy)
- They have different eval criteria (retrieval metrics vs. authorship metrics)
- In production, the Learning Pipeline can run asynchronously — return the response to the user first, then extract and store memories in the background
- You can disable the Learning Pipeline entirely (read-only mode) for debugging without affecting response quality

### Pipeline 4: Maintenance — "Memory Layer Hygiene"

**Cadence:** Scheduled (nightly, weekly) or event-triggered (new snapshot arrives, eval threshold breached).
**Compute:** MongoDB queries + optional LLM calls for consolidation and eval.

**What it does:**
- **Versioning:** When a new snapshot arrives from Pipeline 1, find the previous active snapshot for that user and mark it `is_active: false`. The new snapshot's `supersedes` field points to the old one.
- **Event-driven expiration:** When new data arrives that might invalidate existing flags — run a sweep. Example: new March snapshot shows user started a gym membership → find active "fitness_zero_spend" flag → deactivate it. (MongoDB TTL handles time-based expiration automatically; this pipeline handles logic-based invalidation.)
- **Consolidation (at scale):** When a user has 200+ memories, merge redundant ones. "User mentioned dining positively across 23 sessions" → one consolidated preference memory with high confidence. Original memories deactivated, consolidated memory in the active set. This is the Compress operation from context engineering.
- **Evaluation:** Sample recent memories, run write quality checks (Section 8), measure retrieval precision, flag degradation. If accuracy drops below threshold, alert.
- **Cleanup:** Purge orphaned citations (memories that reference deleted source data), remove memories with invalid schemas, archive old deactivated memories to cold storage.

**In our demo:** Not demonstrated (30-minute talk). MongoDB TTL auto-deleting the flag after 30 days is the only maintenance operation the audience sees.

**Failure modes:** Stale memories not caught by TTL (logic-based expiration missed), consolidation loses nuance, eval thresholds too loose.
**Eval:** Lifecycle correctness — are versions properly chained? Are expired memories actually gone? Are consolidated memories accurate?

**This pipeline exists because the memory layer is a living data store.** Models don't need hygiene — they're frozen after training. Memory stores do — they're continuously written to by an imperfect author (the agent). Without maintenance, memory quality degrades over time. The Maintenance Pipeline is what keeps the memory layer healthy.

### How Moves and Pipelines Relate

The **Three Moves** (Write, Select, Inject) describe what the agent does on a single user message — they're the demo arc, the per-request behavior. The **Four Pipelines** describe how the full production system is architected — different cadences, different compute profiles, independently scalable.

The Moves happen *inside* the real-time Pipelines. The two offline Pipelines have no corresponding Move — they run without user interaction.

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        PRODUCTION SYSTEM (Four Pipelines)                            │
│                                                                                     │
│  ┌───────────────────┐                                         ┌─────────────────┐  │
│  │ INGESTION PIPELINE │                                         │   MAINTENANCE   │  │
│  │ (batch / event)    │                                         │   PIPELINE      │  │
│  │                    │                                         │   (scheduled)   │  │
│  │ Raw Data           │                                         │                 │  │
│  │   → aggregate      │                                         │ Version check   │  │
│  │   → embed          │                                         │ Expire stale    │  │
│  │   → validate       │                                         │ Consolidate     │  │
│  │   → store          │                                         │ Evaluate quality│  │
│  │                    │                                         │                 │  │
│  │ No user present.   │                                         │ No user present.│  │
│  │ No Move.           │                                         │ No Move.        │  │
│  └────────┬───────────┘                                         └────────┬────────┘  │
│           │                                                              │            │
│           ▼                                                              │            │
│  ┌────────────────────────────────────────────────────────────────────── │ ──────┐    │
│  │                                                                       │       │    │
│  │    ╔══════════════════════════════════════════════════════════════╗    │       │    │
│  │    ║              USER MESSAGE (real-time path)                   ║    │       │    │
│  │    ║                                                              ║    │       │    │
│  │    ║   ┌─────────────────────────────────────────────────────┐   ║    │       │    │
│  │    ║   │           RETRIEVAL PIPELINE (read path)            │   ║    │       │    │
│  │    ║   │                                                     │   ║    │       │    │
│  │    ║   │   ┌─────────┐          ┌─────────┐                 │   ║    │       │    │
│  │    ║   │   │ ★ SELECT│          │★ INJECT │                 │   ║    │       │    │
│  │    ║   │   │         │          │         │                 │   ║    │       │    │
│  │    ║   │   │ Embed   │───────▶  │ Format  │──▶ RESPONSE     │   ║    │       │    │
│  │    ║   │   │ query   │  top-k   │ context │    (to user)    │   ║    │       │    │
│  │    ║   │   │ Hybrid  │ memories │ Call LLM│                 │   ║    │       │    │
│  │    ║   │   │ search  │          │         │                 │   ║    │       │    │
│  │    ║   │   └─────────┘          └─────────┘                 │   ║    │       │    │
│  │    ║   └─────────────────────────────────────────────────────┘   ║    │       │    │
│  │    ║                              │                               ║    │       │    │
│  │    ║                              │ conversation turn             ║    │       │    │
│  │    ║                              ▼                               ║    │       │    │
│  │    ║   ┌─────────────────────────────────────────────────────┐   ║    │       │    │
│  │    ║   │           LEARNING PIPELINE (write path)            │   ║    │       │    │
│  │    ║   │                                                     │   ║    │       │    │
│  │    ║   │   ┌─────────┐                                      │   ║    │       │    │
│  │    ║   │   │ ★ WRITE │                                      │   ║    │       │    │
│  │    ║   │   │         │                                      │   ║    │       │    │
│  │    ║   │   │ Extract │──▶ Embed ──▶ Validate ──▶ Store      │   ║    │       │    │
│  │    ║   │   │ new     │    fact      schema       to MongoDB │   ║    │       │    │
│  │    ║   │   │ memories│                                      │   ║    │       │    │
│  │    ║   │   └─────────┘                                      │   ║    │       │    │
│  │    ║   └──────────────────────────────┬──────────────────────┘   ║    │       │    │
│  │    ║                                  │                          ║    │       │    │
│  │    ╚══════════════════════════════════╪══════════════════════════╝    │       │    │
│  │                                       │                               │       │    │
│  │                  ┌────────────────────┘                               │       │    │
│  │                  ▼                                                    ▼       │    │
│  │    ┌──────────────────────────────────────────────────────────────────────┐   │    │
│  │    │                       MEMORY STORE (MongoDB)                         │   │    │
│  │    │                                                                      │   │    │
│  │    │    🟢 preferences    🔵 snapshots    🟡 flags    ⚪ transactions     │   │    │
│  │    └──────────────────────────────────────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  ★ = Three Moves (demo arc)       ═══ = real-time user interaction                  │
│  All other steps = pipeline infrastructure the audience doesn't see                 │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Reading the diagram:**
- The outer box is the full production system (Four Pipelines).
- The double-bordered box (═══) is what happens on every user message — the real-time path.
- The ★ markers are the Three Moves — what the audience sees in the demo.
- Ingestion (top-left) and Maintenance (top-right) run offline with no user present. They read from and write to the Memory Store but never interact with a user message.
- The Retrieval Pipeline (read path) contains the Select and Inject moves. It's synchronous — the user waits.
- The Learning Pipeline (write path) contains the Write move. It can run asynchronously in production — return the response first, extract memories after.
- Both real-time pipelines flow through the Memory Store. The learning loop is visible: Retrieval reads from the store, Learning writes back to it.

Moves are verbs — what the agent does. Pipelines are infrastructure — how the system runs. The talk teaches Moves. Production teams build Pipelines.

### Pipeline Summary

| Pipeline | Cadence | Direction | Key Operation | Maps to Demo |
|---|---|---|---|---|
| **Ingestion** | Batch / event | Write (from data) | Raw data → structured memory | Pre-loaded snapshot |
| **Retrieval** | Real-time | Read | Deterministic fetch (session start) + hybrid search (per request) → response | Select (both modes) + Inject moves |
| **Learning** | Real-time / async | Write (from reasoning) | Conversation → new knowledge | Write move |
| **Maintenance** | Scheduled | Read + Write | Version, expire, consolidate, eval | TTL auto-delete (flag) |

### Why Four, Not Three

The Retrieval and Learning pipelines both fire on every user message, so you could collapse them into a single "Interaction Pipeline." But separating them is architecturally significant:

1. **The read-write distinction is structural, not just conceptual.** The entire thesis of memory engineering is that the write path is distinct from the read path. Collapsing them into one pipeline undercuts that at the systems level.
2. **Different failure modes require different monitoring.** Retrieval failures (wrong memories selected) and write failures (bad memories created) need different dashboards, different alerts, different debugging workflows.
3. **Different eval frameworks.** Retrieval Pipeline gets retrieval evals (Precision@k, MRR). Learning Pipeline gets authorship evals (write quality, coverage). Combining them makes it harder to diagnose which is failing.
4. **Async decoupling in production.** The Retrieval Pipeline must be synchronous (user is waiting). The Learning Pipeline can be asynchronous (extract and store after the response is returned). This reduces user-perceived latency without losing any learning capability.
5. **Independent scaling.** At high traffic, you might need to rate-limit memory writes (Learning Pipeline) while keeping retrieval fast. Or disable learning entirely during a debug session without affecting responses.

### Q&A Responses

- *"You showed three moves but now you're saying four pipelines — which is it?"* → "Different zoom levels. The three moves — Write, Select, Inject — are what happens on every user message. That's the demo. The four pipelines are how you'd architect the production system. Select and Inject are the Retrieval Pipeline — and Select itself has two modes: a deterministic fetch at session start that loads baseline context, and query-driven hybrid search on every message. Write is the Learning Pipeline. The other two pipelines — Ingestion and Maintenance — run offline and don't show up in the live interaction. Moves are what the agent does. Pipelines are how the system runs."

- *"How do you think about the overall system architecture?"* → "Four pipelines, each with a different cadence. Ingestion turns raw data into structured memories on a batch schedule. Retrieval searches and generates responses in real-time. Learning extracts new knowledge from conversations — this is the write path that makes it a learning system, not just retrieval. Maintenance handles versioning, expiration, and quality monitoring on a schedule. They're independent — you can develop, test, and scale each one separately."

- *"Why separate retrieval and learning? They both run on every message."* → "Different failure modes, different evals, different scaling characteristics. Most importantly, the retrieval pipeline is read-only and must be synchronous — the user is waiting. The learning pipeline writes to the database and can run asynchronously. In production, you return the response immediately and extract memories in the background. That's a meaningful latency win."

- *"What runs in production that you're not showing in the demo?"* → "The Ingestion Pipeline — computing new snapshots from fresh transaction data on a schedule. And the Maintenance Pipeline — versioning old snapshots when new ones arrive, event-driven flag invalidation, and periodic eval sampling. The demo shows Retrieval and Learning, which are the real-time pipelines. The batch pipelines are equally important but not as visually interesting in a 30-minute talk."
## 10. Academic Grounding: "Memory in the Age of AI Agents" Survey

The most comprehensive academic reference for this talk is "Memory in the Age of AI Agents" (Hu et al., Dec 2025, arxiv.org/abs/2512.13564) — a 47-author survey that proposes a unified taxonomy of agent memory across three axes: **Forms**, **Functions**, and **Dynamics**. The paper is a survey, not a systems paper — no runnable code, no implementation. The associated GitHub repo (Shichun-Liu/Agent-Memory-Paper-List) is a curated paper list, not a codebase.

What the paper gives us is **taxonomic vocabulary** that validates our architecture choices and lets us connect to the broader research landscape.

### Their Functions Taxonomy → Our Collections

| Survey term (Functions axis) | Definition | Our collection | Our term |
|---|---|---|---|
| **Factual Memory** | Declarative knowledge, user profiles, environmental states | `preferences` | Semantic Memory |
| **Experiential Memory** | What happened — trajectories, case-based, strategy-based | `snapshots` | Episodic Memory |
| **Working Memory** | Active processing context, task-relevant, temporary | `flags` | Working Memory |

Note: The survey's "Experiential Memory" is broader than our "Episodic Memory" — it includes case-based (raw trajectories), strategy-based (abstracted workflows), and skill-based (executable code). Our snapshots are closest to case-based experiential memory. The survey's "Factual Memory" maps cleanly to our preferences — declarative knowledge about the user.

### Their Dynamics Taxonomy → Our Implementation

| Survey dynamics | Definition | Our implementation |
|---|---|---|
| **Formation** | Extraction, summarization, reflection — how memories are created | `write_memories()` — extract from conversation, compute from data, infer from other memories |
| **Evolution** | Update, consolidation, forgetting — how memories change over time | `supersedes` + `is_active: false` (versioning) + TTL auto-delete on `expires_at` (forgetting) |
| **Retrieval** | Search, selection, injection — how memories are accessed | `load_baseline()` (deterministic, session start) + `select_memories()` via `$rankFusion` hybrid search (per request) + context injection in `generate_response()` |

### Their Forms Taxonomy → Our Architecture Choice

The survey identifies three forms of agent memory:
- **Token-level memory** — explicit, discrete, stored as text/structured data (flat, planar, or hierarchical)
- **Parametric memory** — embedded in model weights (fine-tuning, adapters)
- **Latent memory** — hidden activations, KV caches, learned embeddings

Our architecture is **token-level, flat memory** — the simplest form in their taxonomy. Memory units are stored as structured MongoDB documents with explicit text fields (`fact`, `structured_data`). This is intentional: token-level memory is the most interpretable, debuggable, and practical form for production systems. You can see exactly what the agent remembers, trace provenance via `citations`, and version/expire memories with standard database operations.

The survey notes that token-level memory ranges from flat (linear logs, independent chunks) to planar (single-layer graphs) to hierarchical (multi-level pyramids). Our architecture is flat — each memory unit is independent, linked only through `citations` and `supersedes` fields. This is sufficient for our use case (per-user finance coaching) and avoids the complexity of graph-based memory organization.

### How to Reference in the Talk

We don't show their diagrams or walk through their taxonomy on stage. The survey is a reference, not a teaching tool for this audience. But we can make the connection in talking points:

**Slide 5 or 10 talking point (optional):** "The recent 'Memory in the Age of AI Agents' survey — the most comprehensive overview of the field — proposes three dynamics of memory: formation, evolution, and retrieval. Our three functions — write, select, inject — are a direct implementation of those dynamics. The theory is in the paper. The code is in the repo."

**Slide 14 (Go Deeper):** Already listed as a reference. No change needed.

**Q&A response if asked about academic grounding:** "Our architecture maps directly to the taxonomy in Hu et al. 2025. Preferences are factual memory, snapshots are experiential memory, flags are working memory. The lifecycle — write, update, expire — maps to their dynamics of formation, evolution, and retrieval. The survey describes the theory; we showed you 50 lines of PyMongo that implements it."

### Other Relevant Papers (Not Cited in Talk, But Useful for Q&A)

- **A-Mem: Agentic Memory for LLM Agents** (NeurIPS 2025 poster) — agent dynamically organizes memories using Zettelkasten-style linked notes. Closest published work to our "agent as author" concept. Difference: they use a graph of linked notes; we use typed MongoDB collections with a shared base schema.

- **MemRL: Self-Evolving Agents via Runtime RL on Episodic Memory** (Jan 2026) — decouples frozen LLM from plastic episodic memory, uses RL to score memory utility. Validates our thesis that memory enables learning without retraining. Difference: they use RL for utility scoring; we use hybrid search + structured schemas.

- **Mem-α: Learning Memory Construction via Reinforcement Learning** — comprehensive memory architecture with core, episodic, and semantic components. Maps to our three collection types.

- **"Anatomy of Agentic Memory"** (Feb 2026) — very fresh taxonomy and empirical analysis of evaluation and system limitations. Evidence the field is actively consolidating.

- **ICLR 2026 MemAgents Workshop Proposal** — dedicated workshop on the memory layer for agentic systems. Validates "memory as a first-class primitive" as an established research direction.

### "Anatomy of Agentic Memory" (Jiang et al., Feb 2026) — Empirical Findings

Unlike the Hu et al. survey (which is taxonomic), this paper is empirical — it benchmarks five actual memory systems (LOCOMO, A-Mem, MemoryOS, Nemori, MAGMA) and exposes where they break. Published Feb 22, 2026 (arxiv.org/abs/2602.19320). Key findings relevant to our architecture:

**Their four-category taxonomy of Memory-Augmented Generation (MAG) systems:**

| Category | What it means | Maps to our work? |
|---|---|---|
| **Lightweight Semantic** | Append-only, simple embedding + retrieval | Closest to our `preferences` — flat, semantic search |
| **Entity-Centric & Personalized** | User profiles, entity extraction, personalization | Our `structured_data` fields do this within the memory unit |
| **Episodic & Reflective** | Trajectories, reflection, consolidation | Our `snapshots` + the inference loop in `write_memories()` |
| **Structured & Hierarchical** | Graphs, multi-layer, complex organization | We explicitly don't do this — and the paper explains why that's often fine |

**Finding 1: Backbone sensitivity.** "Backbone model" = the LLM powering the agent (e.g., GPT-4o-mini vs. Qwen-2.5-3B vs. Claude Sonnet 4.5). The paper finds that graph-based and episodic architectures are highly sensitive to backbone model quality. Asking a weaker/smaller model to extract entities, build graph relationships, and deduplicate memory entries produces format errors and corrupted memory state. The model can still chat fluently — it just can't reliably do the structured write operations that maintain memory integrity.

**Why this validates our architecture:** We ask the LLM to produce one structured JSON document per memory unit, not to extract entity-relationship triples and maintain graph consistency. That's a much simpler generation task. `structured_data` is a simple key-value structure (`{ area: "dining", priority: "high" }`), not a graph node with edges. This works reliably across model quality levels and could even be validated at the MongoDB schema level.

**Finding 2: "Silent Failure."** Weaker models converse fluently in the short term while their long-term memory becomes corrupted due to failed write operations. The agent appears to work but its memory degrades silently over time.

**Why this matters for us:** This is directly relevant to `write_memories()`. Memory quality depends on the LLM's ability to extract structured units reliably. This is why `citations` and `structured_data` matter — they give you something auditable. If the agent writes a preference memory with `citations` pointing to the wrong source, or `structured_data` with hallucinated field values, you can detect it. The eval loop starts here: are the memories the agent writes actually correct?

**Finding 3: Benchmark saturation.** Existing benchmarks are often underscaled. Long-context LLMs (128k+ tokens) can sometimes solve benchmark tasks without external memory at all, just by stuffing everything into the context window.

**Why this matters for us:** Our demo needs to show a use case where context windows genuinely can't hold everything — or more precisely, where the *right* 300 tokens outperform 12,000 tokens of raw data. The finance coach demo does this: it's not about volume (50 transactions fit in context), it's about *structured knowledge that the agent built over time* (priorities, spending patterns, inferred mismatches). A context window full of raw transactions doesn't contain "user prioritizes dining over cars" — that knowledge was created by the agent.

**Finding 4: System-level costs.** Retrieval latency, update overhead, and throughput degradation from memory maintenance are frequently overlooked in memory system evaluations.

**Why this matters for us:** Validates our hybrid search performance discussion. Pre-filters scope search to a small user partition. Parallel pipeline execution means latency ≈ slower pipeline, not sum. LLM generation is 50–100x slower than search. The real bottleneck is never the database.

**How to use in Q&A (not on slides):**

- *"Why flat documents instead of a graph?"* → "The 'Anatomy of Agentic Memory' paper from this month benchmarks five memory systems and finds that graph-based architectures are significantly more sensitive to the underlying LLM's capability — format errors increase and memory structures can collapse with weaker models. Flat document models with typed fields are more robust. Start simple, add complexity when you have evidence you need it."

- *"How do you know the agent is writing good memories?"* → "That's the eval loop. The same paper documents 'silent failure' — agents that converse fluently while their memory gets corrupted by bad writes. That's why `citations` and `structured_data` matter — they give you something auditable. If the agent writes a preference with hallucinated structured_data, you can detect that with schema validation."

- *"Do you really need memory if context windows are 128k+ tokens?"* → "Benchmark saturation is real — some tasks don't need memory, just a bigger window. But memory engineering isn't about volume. It's about structured knowledge the agent builds over time. 'User prioritizes dining over cars' doesn't exist in any transaction record. The agent created that knowledge. No context window size gives you that for free."

---

## 11. Memory Frameworks vs. MongoDB Primitives

### The Landscape

The main memory frameworks today: **Mem0**, **Zep**, **Letta** (formerly MemGPT), and to some extent **LangGraph's persistence layer**. Each positions itself as "memory for AI agents." Here's what they actually provide and what MongoDB gives you natively.

### What Frameworks Offer

| Capability | What it does | How frameworks implement it |
|---|---|---|
| **Automatic memory extraction** | Feed in a conversation turn → framework decides what's worth remembering, deduplicates, writes | LLM call under the hood. Mem0 uses GPT-4 or similar to extract "memory-worthy" facts. Same pattern as our `write_memories()` |
| **Conflict resolution / dedup** | "I love sushi" Monday → "I've gone off sushi" Thursday → framework detects contradiction, supersedes old memory | LLM-based comparison of new fact vs. existing memories. Some use embedding similarity threshold to find candidates, then LLM to decide |
| **Out-of-the-box search** | Embed query → retrieve similar memories → optionally rerank | Vector similarity search. Most use a single vector DB backend (Qdrant, Pinecone, pgvector) |
| **Session/user management** | Multi-user isolation, session boundaries, metadata tracking | Application-level partitioning by user_id, session_id |

### What MongoDB Gives You That Frameworks Don't

| Capability | MongoDB | Typical framework |
|---|---|---|
| **Hybrid search** | `$rankFusion` runs vector + text in parallel, natively. One pipeline, one round trip. | Pure vector search only. No keyword/text search alongside vector. If "dining priority" doesn't semantically match, you miss it. |
| **TTL auto-expiration** | `expires_at` + TTL index. Database deletes the document. Zero app code. | Application-level expiration checks (if they exist at all). Most frameworks don't have a concept of working memory that expires. |
| **Typed structured_data** | `structured_data` is a first-class queryable field. Filter by `area: "dining"`, aggregate by `priority`, validate with schema rules. | Memories are opaque text blobs with embeddings. You can search semantically but not query structured fields. |
| **Aggregation pipelines** | Compute snapshots from raw transactions *within the database*. Data → memory transformation happens server-side. | Frameworks don't touch your operational data. The boundary between "data" and "memory" is your problem. |
| **Single platform** | Operational data, memory layer, vector search, text search, TTL — one system. | Separate vector DB + separate operational DB + framework glue. More moving parts, more failure modes. |
| **Full index control** | You define exactly which fields are indexed, which pre-filters apply, what dimensions, what similarity function. | Abstracted away. You get whatever the framework's default embedding + search config gives you. |
| **Auditability** | Every memory is a document you can query, inspect, export, validate. `citations` trace provenance. `structured_data` can be schema-validated. | Memory is managed inside the framework's abstraction. Debugging means reading framework logs, not querying your own data. |

### The Core Insight

**Every memory framework is a thin orchestration layer over the same primitives.** Mem0's storage backend is a vector database. Zep uses Postgres with pgvector. They embed with OpenAI or Voyage, extract with an LLM call, search with vector similarity. The "framework" is 200-300 lines of meaningful logic wrapping those components.

When you use MongoDB + Voyage AI + Claude:
- `write_memories()` = ~50 lines of Python (LLM extraction + embed + insert)
- `select_memories()` = ~30 lines of Python ($rankFusion pipeline)
- `generate_response()` = ~20 lines of Python (format context + LLM call)

**The framework saves you from writing ~100 lines of Python. In exchange, you lose:** hybrid search, TTL expiration, typed structured_data, aggregation pipelines, index control, auditability, and the ability to run your memory layer and operational data on one platform.

### When Frameworks Make Sense

- **Prototyping** — you want memory working in an afternoon, don't care about search quality or production ops
- **Framework lock-in is acceptable** — you're already deep in a specific ecosystem (e.g., LangGraph) and the memory add-on is incremental
- **No existing database** — you're starting from scratch and don't have MongoDB (or any DB) in your stack

### When MongoDB Primitives Win

- **Production systems** — you need to audit, tune, and debug your memory layer
- **Hybrid search matters** — your queries are a mix of specific ("dining priority") and abstract ("where am I wasting money")
- **Memory lifecycle matters** — you need versioning, expiration, or provenance tracking
- **You're already on MongoDB** — your operational data is right there. The memory layer is three collections and three indexes.
- **Multi-modal memory** — you want semantic, episodic, and working memory with different schemas and lifecycles. Frameworks give you one memory type.

### The Talk's Framing (Positive, Not Combative)

We don't say "frameworks are bad." We say: **"Memory engineering is a data modeling problem. If you're already on MongoDB, you have everything you need. The framework is the 50 lines of Python we just showed you."**

The audience takeaway isn't "don't use Mem0." It's "now I understand what Mem0 does under the hood, and I can build it myself with more control."

### Q&A Responses

- *"Why not just use Mem0?"* → "Mem0 is great for prototyping. Under the hood, it's doing the same thing — LLM extraction, vector embed, vector search. The difference is we get hybrid search, TTL expiration, and typed structured_data. Those matter in production. If you're prototyping, use whatever gets you to a demo fastest. If you're building for real users, you want the primitives."

- *"What about Zep / Letta?"* → "Same principle. Zep uses Postgres with pgvector. Letta manages a virtual context window. They're each solving one slice of the memory problem with their own abstraction. MongoDB gives you the building blocks to solve all of it — and you keep full control of your data model, your search pipeline, and your memory lifecycle."

- *"Isn't 100 lines of Python still more work than `pip install mem0`?"* → "It's about 100 lines of code you'll actually understand and can debug at 2 AM when your agent starts writing bad memories. The 'Anatomy of Agentic Memory' paper documents silent failure — agents that chat fluently while their memory degrades. When that happens, do you want to read Mem0's source code, or query your own MongoDB collection?"

---

## 12. Positioning: GraphRAG vs. Agent Memory

The audience may be familiar with GraphRAG — knowledge graphs + graph traversal as a smarter retrieval layer. Our talk occupies different ground. Understanding the distinction helps us answer questions cleanly.

### GraphRAG: Smarter Retrieval of Existing Knowledge

- **Problem it solves:** Information fragmented across silos (docs, emails, notes). Traditional top-k chunk retrieval can't reconstruct connected context.
- **Approach:** Extract entities and relationships from documents into a knowledge graph. Retrieve via graph traversal + community summaries instead of naive top-k.
- **Who writes the knowledge:** Humans or extraction pipelines. The graph is built from existing documents.
- **Agent's role:** Reader — queries the graph, doesn't author it.
- **Core framing:** Memory as a *retrieval architecture* problem.

### Agent Memory: The Agent as Author

- **Problem it solves:** Agents are stateless — they don't learn across sessions.
- **Approach:** Agent writes structured memory units from its own reasoning, versions them, expires them. Retrieved via hybrid search.
- **Who writes the knowledge:** The agent itself, from reasoning over conversations and data.
- **Agent's role:** Author — writes, updates, and expires its own knowledge.
- **Core framing:** Memory as a *read-write learning system*, not just retrieval.

### The Distinction

| | **GraphRAG** | **Agent Memory (this talk)** |
|---|---|---|
| Agent's role | Reader (queries the graph) | **Author** (writes, updates, expires memories) |
| Knowledge source | Human-authored / extraction pipeline | Agent-authored from reasoning |
| Structure | Graph (entities + relationships) | Document model (collections + typed fields) |
| Retrieval | Graph traversal + community summaries | Hybrid search ($rankFusion) |
| What it solves | Fragmented retrieval across silos | Stateless agents that don't learn |

These are **complementary, not competing.** A production system could use both — a reference knowledge layer backed by a knowledge graph AND an agent memory layer backed by document collections. The graph handles "what do we know about this topic across all our documents." The memory layer handles "what does this agent know about this specific user." Different data, different lifecycle, same database.

### How We Position in the Talk

- We don't argue against knowledge graphs or any specific approach.
- The reference knowledge vs. agent memory table (Slide 11) draws the conceptual line cleanly.
- Our talking points — "read-write," "the agent is an author, not just a reader" — establish our territory without comparing against anyone.
- If asked directly, the answer is always: "complementary, not competing."

### Q&A Prep

- *"Why not use a knowledge graph?"* → "Different problem. Knowledge graphs organize existing information from documents into a traversable structure. Agent memory creates new knowledge from reasoning — user preferences, spending patterns, inferred mismatches. If your data lives in scattered documents and you need to connect entities, a graph is great. If your agent needs to learn from conversations and build user-specific knowledge over time, typed memory collections are the right fit. You can use both in the same system."

- *"Why not use an immutable event log for versioning?"* → "Event sourcing is great for audit trails — you can replay history and reconstruct any point-in-time state. We use `supersedes` + `is_active` because it's simpler for retrieval — one pre-filter gives you current state without reconstructing from events. For production at scale, event sourcing is worth considering. For teaching in 30 minutes, the simpler pattern wins."

---

## 13. Five Takeaways

1. **Memory engineering makes context engineering compound over time.** Without memory, every session starts from zero. With it, the agent learns.

2. **Agent memory is a data modeling problem.** Design a schema for what the agent remembers. Each memory is a structured unit: `fact` (LLM reads) + `structured_data` (app reads) + provenance.

3. **Hybrid search selects the right memories.** Vector + keyword via `$rankFusion` in one database call. No routing layer. Pre-filters scope to user partition before search.

4. **Voyage AI embeddings power the semantic layer.** `voyage-3-large`, 1024 dims, asymmetric input types. Embed the `fact` field at storage, embed the query at retrieval.

5. **Agent memory is read-write, not just retrieval.** The agent writes, updates, and expires its own knowledge. The `store_memory` tool call is the fundamental difference between retrieval and learning.

---

## 14. References

- **"What Is Agent Memory?"** — MongoDB's guide to memory types and application modes
  mongodb.com/resources/basics/artificial-intelligence/agent-memory

- **"Memory in the Age of AI Agents"** (Hu et al., Dec 2025) — comprehensive survey of the field
  arxiv.org/abs/2512.13564

- **"Context Engineering for Agents"** — LangChain's write/select/compress/isolate framework
  blog.langchain.com/context-engineering-for-agents

- **"Effective Context Engineering for AI Agents"** — Anthropic's practical guide
  anthropic.com/engineering/effective-context-engineering-for-ai-agents

- **MongoDB's video search blog** — same $rankFusion hybrid search pattern, multi-modal
  mongodb.com/company/blog/technical/build-agentic-video-search-system-voyage-ai-mongodb-anthropic

- **MongoDB LangGraph Integration** — production orchestration with checkpointing
  mongodb.com/docs/atlas/ai-integrations/langgraph

---

## 15. What's In Scope vs. Out of Scope

### In scope for this talk
- Write, Select, Inject as the three moves
- Memory lifecycle: write → select → update → expire
- Base schema with type-specific extensions
- Hybrid search via $rankFusion
- Three-function agent architecture (no framework)
- Reference knowledge vs. agent memory distinction
- Context engineering vs. memory engineering framing

### Out of scope (mentioned but not demonstrated)
- Compress and Isolate operations (matter at scale)
- Confidence scoring (production concern — how to compute and use in ranking)
- Evaluation loop (are the right memories selected? is the agent writing useful units?)
- Multi-agent memory sharing (shared memory type from SF .local talk)
- Procedural memory (templates and workflows — SF .local talk covers this)
- Reranking with Voyage AI (scale-up optimization)
- LangGraph orchestration (production orchestration)

### Explicitly cut
- WSCI+D as a 5-operation framework → simplified to "Write, Select, Inject"
- Cognitive memory hierarchy as primary framing → plain English with mapping
- Agent Trace tab → Search + Context tabs sufficient
- Confidence field → doesn't contribute to retrieval in demo, invites unexplainable questions
- Detailed memory versioning demo → mention `is_active` + `supersedes` once, don't deep-dive
- 6 demo messages → 4–5 for tighter script

---