# Engineering Context Quality by Architecting Agent Memory

**O'Reilly AI Superstream: Context Engineering**
*Mikiko Bazeley | Staff Developer Advocate, MongoDB*
*30 minutes*

**Companion docs:**
- `oreilly-talk-concepts.md` — definitions, positioning, error modes, eval framework, four-pipeline architecture
- `oreilly-talk-app-spec.md` — schemas, diagrams, prompts, UI spec, scaling notes

---

## The 5 Things the Audience Walks Away With

1. **Memory engineering makes context engineering compound over time.** Without memory, every session starts from zero. With it, the agent learns. Same LLM, same data, completely different output — because of 5 structured memory units in the context window.

2. **Agent memory is a data modeling problem.** You need to design a schema for what the agent remembers — not just dump chat logs. Each memory is a **memory unit**: a structured container with a `fact` field (natural language the LLM reads) and `structured_data` (typed fields your app reads), plus provenance and expiration metadata.

3. **Hybrid search is how you select the right memories.** Vector search for semantic queries ("where am I wasting money?"). Keyword search for specific queries ("what's my dining budget?"). MongoDB `$rankFusion` combines both in one query.

4. **Voyage AI embeddings power the semantic layer.** Embed the `fact` field with `voyage-3-large` (1024 dims). Asymmetric `input_type`: `"document"` for storage, `"query"` for retrieval.

5. **Agent memory is not just retrieval — it's a read-write system with a lifecycle.** Most teams stop at reference knowledge retrieval (RAG). Agent memory goes further: the agent writes its own structured knowledge from reasoning, updates it (`supersedes` + `is_active`), and expires it (MongoDB TTL on `expires_at`). The `store_memory` tool call is the fundamental difference — your agent doesn't just search, it learns.

---

## The 3 Moves We Demonstrate

| Move | What the Audience Sees | Teaching Point |
|------|----------------------|----------------|
| **Write** | User tells the agent what they care about → agent writes a structured memory unit to MongoDB | Memory is a data modeling problem, not a chat log |
| **Select** | User asks a question → agent searches memories via hybrid search → sidebar shows the pipeline and scores | Hybrid search handles both specific and semantic queries |
| **Inject** | Selected memories get formatted and injected into the LLM prompt → sidebar shows with/without toggle | The right ~300 tokens of structured memory beats 12,000 tokens of raw history |

That's the complete demo arc. Three moves, one story.

---

## The Demo Story (simplified)

**App name:** Personal Finance Coach

**One sentence:** A personal finance coaching app that remembers what you care about and uses that to give you personalized advice instead of generic advice.

The domain context the audience needs to understand is:

- Users tell the app what they value (e.g., "I love dining out, I don't care about clothes")
- The app tracks their spending
- When the user asks "how am I doing?", the app gives advice based on *their values*, not generic "spend less" advice

That's it. The domain is intuitive — everyone has spending priorities. Zero domain jargon to explain.

---

## Where Agent Memory Fits: The Data Hierarchy

Before diving into the demo, the audience needs to understand where agent memory sits relative to the data types they already know. This is the conceptual bridge from RAG to memory engineering.

### The Four Data Layers

```
 DATA SOURCES              AGENT MEMORY                         CONTEXT WINDOW
 (Layer 1)                 (Layer 2)                            (Layer 3)
 where info comes from     structured, searchable,              what the LLM sees
                           agent-managed                        right now

┌──────────────┐           ┌──────────────┐
│ transactions │─AGGREGATE▶│  snapshots   │──┐
│ (time series)│           │  (episodic)  │  │  SELECT              ┌──────────────────┐
└──────────────┘           └──────────────┘  │  (deterministic:     │  CONTEXT WINDOW   │
                                             ├── session start,     │                  │
┌──────────────┐           ┌──────────────┐  │   no search)         │  system prompt    │
│  user chat   │─EXTRACT──▶│ preferences  │──┤                      │  + baseline       │
│  messages    │           │  (semantic)  │  │  SELECT              │    memories       │
└──────────────┘           └──────────────┘  │  (query-driven:      │  + selected       │
                                             ├── hybrid search      │    memories       │
                           ┌──────────────┐  │   per request)       │  + retrieved docs │
              INFER───────▶│    flags     │──┘                      │  + user query     │
              (from        │  (working)   │                         │                  │
              preferences  └──────────────┘                         │  ~300 tokens of   │
              × snapshots)       ▲                                  │  the RIGHT context│
                                 │                                  └────────┬─────────┘
                                 │                                           │
                                 │              WRITE (Move 1)               │
                                 └───────────────────────────────────────────┘
                                  LLM reasons over memories and
                                  creates new memory units
                                  (the continuous learning cycle)


┌──────────────┐
│  reference   │─────────────────────────────────────────────────▶ (also feeds into
│  knowledge   │  semantic search                                   context window)
│  (Layer 4)   │
│              │  Policies, guides, documentation.
│  indexed by  │  Shared across all users. Most teams
│  humans      │  build this first — agent memory
│              │  builds on top of it.
└──────────────┘  Not used in this demo.
```

**Key distinctions to make on stage:**

| Layer | What it is | Who writes it | How it's accessed | Lifecycle |
|-------|-----------|-------------|-------------------|-----------|
| **Reference Knowledge** | Domain expertise — docs, policies, guides | Humans or agents index it | Semantic search (vector) | Relatively static; re-indexed periodically or on change |
| **Operational Data** | Transactional records — events, purchases, logs | App writes it | Direct queries, aggregation, time series | Append-only or CRUD |
| **Agent Memory** | What the agent knows *about this user* | The agent writes it from reasoning | Hybrid search (vector + text) | Write, select, update, expire |
| **Context Window** | What the LLM sees right now | Assembled per-request | Passed directly to LLM | Ephemeral — rebuilt every call |

The critical distinction: **reference knowledge** is about the domain (how things work, shared across users). **Agent memory** is about the user (what they care about, what happened, what the agent inferred). RAG is a *retrieval pattern* that can access either — it's not a data type.

### Data-to-Memory Transformation

Raw data doesn't start as memory. It goes through a transformation — from passive information to active, retrievable, structured memory units. The diagram above shows this flow. Key points to make on stage:

**The critical transition point:** Data becomes memory when it is aggregated, encoded (embedded + metadata), and stored as a structured memory unit with provenance. Before this point, it's passive information. After, it's active memory — persistent, contextually aware, adaptive, and retrievable.

**The continuous learning cycle:** Memory feeds LLM reasoning, and LLM reasoning creates new memory units. This is the read-write loop that distinguishes agent memory from reference knowledge retrieval. In our demo:
- Transactions (operational data) → AGGREGATE → snapshots (episodic memory)
- User messages (raw input) → EXTRACT → preferences (semantic memory)
- Preferences × snapshots (existing memories) → INFER → flags (working memory)
- Flags (new memory) → available for future SELECT → influences next response

### MongoDB Collections (4 collections, 1 database)

Each memory type gets its own collection with optimized indexes. Transactions use a time series collection.

```
finance_coach_db
├── preferences          # Semantic Memory — vector + text indexes
├── snapshots            # Episodic Memory — vector + text indexes
├── flags                # Working Memory — vector + text + TTL indexes
└── transactions         # Time Series — columnar storage, auto-bucketed
```

**`preferences`** — Long-term semantic memory. User-stated values and priorities. No TTL.
**`snapshots`** — Long-term episodic memory. Computed summaries of events (e.g., monthly spending). `supersedes` chain for versioning.
**`flags`** — Short-term working memory. Agent-inferred insights. `expires_at` + TTL index for auto-deletion.
**`transactions`** — Operational data. Time series collection with `user_id` as metadata, `transaction_date` as time field. Never queried live by the agent — exists so snapshots have grounded provenance.

---

## Talk Structure (30 minutes)

### Section 1: The Hook (3 min) — SLIDE

**What I say first (before showing the slide):**
- "You've heard a lot today about making context windows work better — selecting the right information, compressing what's too long, avoiding context rot. All of that matters. But all of it is about making *retrieval* better — searching through knowledge that someone indexed ahead of time."
- "What if the agent could *write its own context*? Not retrieve documents someone indexed last week — create structured knowledge from its own reasoning, in real time, and use that knowledge to get smarter over time. That's what memory engineering is. And that's what we're building in the next 25 minutes."
- "Here's the demo: a personal finance coaching app. The user tells it what they care about. The app tracks their spending. And when they ask 'how am I doing?', the agent gives advice based on *their priorities*, not generic advice. Simple concept. The hard part is making the agent actually remember. Let me show you the difference."

**On screen:** Two agent responses to the same question, side by side.

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

**What I say:**
- "Same LLM. Same transaction data. Same user. Completely different output."
- "The difference? Five structured memory units — about 300 tokens — that the agent wrote itself. Not retrieved from a document store. Written by the agent from conversations and its own reasoning."
- "If you saw the earlier talks on memory types — semantic, episodic, working memory — we're implementing those. The difference is we're doing it in MongoDB with collections you can create tonight. Plain Python, PyMongo, Voyage AI, Claude. No proprietary memory system, no knowledge graph, no special framework."
- "Three moves: write memories, select them with hybrid search, inject them into the prompt. Let's build it."

### Section 2: What Is a Memory Unit? (5 min) — DEMO

**What happens:** I open the Streamlit app. The sidebar shows one pre-loaded memory (a spending snapshot). I type one message:

> "I love dining out and traveling. I don't care about clothes or cars."

The agent responds conversationally AND creates 2–3 memory units. They appear in the sidebar. I click one to show the full document.

**On screen (sidebar — Document tab):**

```json
{
  "user_id": "alex_demo",
  "subject": "Dining Out",
  "fact": "User loves dining out. This is a top spending
           priority — never suggest cutting restaurant budget.",
  "structured_data": {
    "area": "dining",
    "priority": "high"
  },
  "citations": ["msg_001"],
  "is_active": true,
  "created_at": "2026-02-25T10:15:00Z",
  "embedding": [0.023, -0.118, ...]
}
```

**What I say:**
- "The agent decided this was worth remembering and wrote a structured **memory unit** to MongoDB. This is the moment that goes beyond retrieval — the agent is *writing*, not just reading. With reference knowledge retrieval, you index documents ahead of time and search them. Here, the agent creates its own knowledge in real time."
- "Two fields matter most: `fact` is natural language — that's what the LLM reads when this memory gets retrieved. `structured_data` has typed fields — that's what your app logic can filter and compute on. Two consumers, one memory unit."
- "And `citations` — this traces back to the message I just typed. Every memory unit has provenance."
- "This is a **semantic memory** — a fact about the user's preferences, stored for long-term reuse. You've heard about these memory types earlier today. We're implementing them."
- *(Click the pre-loaded spending snapshot)* "Here's a different kind of memory — a spending snapshot the agent computed from transaction data. Same base schema, different collection. This one is an **episodic memory** — a record of a specific event. Each memory type gets its own collection with optimized indexes — preferences, snapshots, flags — but they share the same base fields for search and injection."
- "And notice: this snapshot has `supersedes` pointing to last month's version. When the agent computes a new snapshot, the old one gets `is_active: false`. That's the lifecycle — memories aren't static. They get created, they get superseded, they expire. The flag memory we'll see later has an `expires_at` date — MongoDB's native TTL index automatically deletes it when that date passes. No application code needed for cleanup."

**Takeaway landed:** #1 (memory makes agents personal) and #2 (memory is a data modeling problem).

### Section 3: How Do You Get Memories Back? (7 min) — DEMO

This is the core technical section. Two queries, same hybrid search pipeline — showing it handles both specific and abstract questions.

**Query A — I type:** "What's my dining priority?"

Sidebar switches to **Search tab** showing:

```
Pipeline: $rankFusion (hybrid search)
├── $vectorSearch (semantic similarity)
└── $search (full-text on "subject" and "fact" fields)

Results:
  #  Memory                    Vector   Text    Combined
  1  Dining Out (high)          0.85    0.95     0.92  ← text boost
  2  Travel (high)              0.81    0.00     0.80
  3  Spending snapshot          0.79    0.00     0.77
```

**What I say:**
- "Every query runs the same hybrid search pipeline — `$rankFusion` combining vector search and full-text search in one database call. No routing logic, no decision step. One pipeline handles everything."
- "Look at the scores. Dining got a 0.95 text score because the word 'dining' appears in the `fact` field. That boosted it to the top. Without the keyword pipeline, it would've been second behind Travel."

**Query B — I type:** "Where am I wasting money?"

Sidebar shows:

```
Pipeline: $rankFusion (hybrid search)
├── $vectorSearch (semantic similarity)
└── $search (full-text — no keyword matches)

Results:
  #  Memory                              Vector   Text   Combined
  1  Spending snapshot                    0.88    0.00     0.87
  2  Cars/Clothing (low priority)         0.84    0.00     0.83
  3  Dining Out (high)                    0.82    0.00     0.81
```

**What I say:**
- "Same pipeline, completely different kind of query. No memory contains the word 'wasting.' The text pipeline returns nothing — and that's fine. The vector side understands that spending on things you don't value *is* waste."
- "The spending snapshot surfaces first — it has the actual numbers. The 'low priority' memory for cars is second — the agent knows you don't care about cars, so spending there is waste."
- "This is the power of hybrid search. You don't need to decide in advance whether a query is semantic or keyword-based. Run both, let `$rankFusion` score the results. When keywords match, they boost. When they don't, vector search carries it. One pipeline, one round trip."
- "And if you're thinking 'isn't running two pipelines slower?' — they run in parallel, not sequentially. The pre-filter scopes both pipelines to just this user's active memories before either search starts. At this scale, the difference is single-digit milliseconds — and your LLM call is going to be 50 to 100x slower than your search anyway. The real cost of *not* doing hybrid search is building a routing layer that decides 'is this query semantic or keyword?' per request. That router is its own source of errors and latency. One pipeline that handles both is simpler and more robust."
- *(Point to pre-filter)* "And notice: `filter: { user_id, is_active: true }` inside `$vectorSearch`. MongoDB applies this *before* vector search. You're scoping to this user's memories at the index level — that's how it scales to thousands of users."

**What I say about Voyage AI (30 seconds):**
- "The embeddings are from Voyage AI — `voyage-3-large`, 1024 dimensions. We embed the `fact` field specifically — that's where the semantic meaning lives. And Voyage uses asymmetric input types: `input_type='document'` when you store, `input_type='query'` when you search. That asymmetry improves retrieval quality."

**Takeaway landed:** #3 (hybrid search) and #4 (Voyage AI embeddings).

### Section 4: The Payoff — Context Injection (7 min) — DEMO

**I type:** "How am I doing this month?"

The agent generates the personalized response (the one from the hook). While it generates, I switch to the **Search tab** and then the **Context tab**.

**Search tab shows:**

```
Pipeline: $rankFusion (hybrid search)
├── $vectorSearch (semantic similarity)
└── $search (full-text on "subject" and "fact" fields)

Results:
  #  Memory                    Vector   Text    Combined
  1  Spending snapshot          0.88    0.91     0.90
  2  Dining Out (high)          0.82    0.72     0.80
  3  Travel (high)              0.79    0.00     0.77
  4  Cars/Clothes (low)         0.77    0.00     0.75
```

**Context tab shows (toggle):**

**With memory (~650 tokens):**
```
System: You are a personal finance coach. You help users
understand their spending patterns, align their spending
with their stated priorities, and make informed financial
decisions.

<user_context>
Stated Preferences:
- Dining: high priority (user-stated)
- Travel: high priority (user-stated)
- Cars: low priority (user-stated)

Spending Snapshots:
- 2026-02-01: Income $12,500, Fixed $6,870,
  Discretionary $1,000. Top spending: car payments:
  $1,245, dining: $890, groceries: $650
</user_context>

User: How am I doing this month?
```

**Without memory (~30 tokens):**
```
System: You are a financial assistant.

User: How am I doing this month?
```

**What I say:**
- "Here's what the LLM actually received. On the left: coaching rules, four structured memories, the user's question. About 650 tokens. On the right: a generic prompt and the same question. 30 tokens."
- "Same model. The difference is 300 tokens of *the right* structured context. That's what turned 'consider reducing expenses' into 'your cars are crowding out what you care about.'"
- "And notice — the agent also just created a new memory." *(Point to sidebar — a flag/insight memory appeared)* "It detected a mismatch between stated priorities and actual spending, and stored it with `expires_at` set 30 days from now. MongoDB's native TTL index will auto-delete this if the user doesn't address it. Next time the user asks, the agent already knows about this issue."
- "This is **working memory** — temporary, task-relevant context the agent inferred from cross-referencing its own semantic and episodic memories. It's not a permanent fact. It's an active insight with a lifespan."
- "This is what makes agent memory fundamentally different from reference knowledge retrieval. With retrieval, you search documents that were indexed ahead of time. This agent just *reasoned over its own memories* and created new knowledge. The citations on this new memory point to other memories — not to external documents. It's citing its own knowledge store. That's a read-write memory system."

**Takeaway landed:** #1 again (the payoff) and #5 (read-write system with lifecycle).

### Section 5: Recap + Resources (8 min) — SLIDES

**Slide: "Three Moves"**

```
1. WRITE     Agent writes structured memory units to MongoDB
             fact (LLM reads) + structured_data (app reads)
             One collection, one schema, many memory types
             ← This is what makes it NOT just RAG

2. SELECT    Hybrid search selects the right memories
             $vectorSearch (semantic) + $search (keyword)
             $rankFusion combines both in one query
             Pre-filters scope to this user before searching

3. INJECT    Selected memories → context window
             ~300 tokens of the RIGHT context
             beats 12,000 tokens of raw chat history

And the lifecycle that connects them:

  WRITE  → memory units are born (user-stated, computed, or inferred)
  SELECT → hybrid search finds the right ones
  UPDATE → new version supersedes old (supersedes + is_active)
  EXPIRE → MongoDB native TTL index auto-deletes (expires_at field)

These map to the established context engineering operations:
Write, Select, Compress, Isolate. We demonstrate Write,
Select, and what good selection enables (Inject).
Compress and Isolate matter at scale — see references.
```

**Slide: "Reference Knowledge Retrieval vs. Agent Memory"**

```
REFERENCE KNOWLEDGE RETRIEVAL          AGENT MEMORY
(what most people call "RAG")          ────────────

About the domain                       About this user
Indexed by humans or agents            Written by the agent from reasoning
Shared across all users                Per-user, per-session
Relatively static                      Dynamic — write, update, expire
Citations → external documents         Citations → other memories + raw data
Retrieves what was indexed             Learns from interactions

RAG is a retrieval pattern, not a data type.
You can use RAG to access either layer.
The difference is what the data represents
and who creates it.
```

**Slide: "The Schema That Makes It Work"**

```
BASE MEMORY UNIT (shared by all memory collections):
  user_id, subject, fact, embedding, citations,
  is_active, created_at

+ TYPE-SPECIFIC FIELDS:

  preferences (Semantic Memory)
    structured_data: { area, priority }
    No expiration. Permanent user values.

  snapshots (Episodic Memory)
    structured_data: { as_of_date, income, expenses... }
    supersedes → previous version ID

  flags (Working Memory)
    structured_data: { flag_type, severity, mismatch... }
    expires_at → MongoDB TTL auto-deletes

  transactions (Operational Data — Time Series)
    transaction_date, metadata: { user_id, category }
    amount, merchant, description
```

**Slide: "Start Building Tonight"**

- MongoDB Atlas free tier → memory collections + vector & text indexes
- Voyage AI → `voyage-3-large` for embeddings
- *When your memory collections grow, add Voyage reranking after hybrid search to refine top results before injection — one API call.*
- Claude API → response generation + memory extraction
- Plain Python → four functions: `load_baseline()`, `select_memories()`, `generate_response()`, `write_memories()`
- Repo link: notebook + Streamlit app + this presentation
- *For production orchestration (checkpointing, human-in-the-loop, multi-agent), see the MongoDB LangGraph integration: mongodb.com/docs/atlas/ai-integrations/langgraph*

**Slide: "Go Deeper"**

- "What Is Agent Memory?" — MongoDB's guide to memory types, memory units, and application modes. mongodb.com/resources/basics/artificial-intelligence/agent-memory
- "Memory in the Age of AI Agents" (Hu et al., Dec 2025) — the comprehensive survey. Covers forms, functions, and dynamics of agent memory. arxiv.org/abs/2512.13564
- "Context Engineering" — write/select/compress/isolate framework. blog.langchain.com/context-engineering-for-agents
- "Effective Context Engineering for AI Agents" — Anthropic's guide to treating context as a finite resource. anthropic.com/engineering/effective-context-engineering-for-ai-agents
- MongoDB's video search blog — the same hybrid search pattern with multi-modal. mongodb.com/company/blog/technical/build-agentic-video-search-system-voyage-ai-mongodb-anthropic
- MongoDB LangGraph Integration — when you need production orchestration (checkpointing, human-in-the-loop, long-term memory store). mongodb.com/docs/atlas/ai-integrations/langgraph

**What I say:**
- "Three moves. One base schema, three tailored collections. That's memory engineering."
- "You've heard the concepts today — context rot, failure modes, memory types, knowledge graphs. This was the implementation talk. Plain Python, PyMongo, Voyage AI, Claude. No proprietary system. You can build this tonight with tools you already have."
- "Memory engineering sits within a broader discipline that's emerging called agent engineering — the iterative process of building, shipping, observing, and refining non-deterministic systems. What we showed today is the *build* phase. The real work starts when you ship and observe: are the right memories being selected? Is the agent writing useful memory units or noise? That's your eval loop — and that's where the next iteration begins."
- "The established context engineering framework has four operations: Write, Select, Compress, Isolate. We demonstrated Write and Select, plus Inject — what good selection enables. The fourth — Compress — matters when your agent runs hundreds of turns. Isolate matters when you split work across sub-agents. Both are covered in the references."
- "The memory types — semantic, episodic, working — are the same ones you heard about earlier today. The implementation detail is that each gets its own MongoDB collection with tailored schemas and indexes. Preferences don't need TTL. Snapshots need version chains. Flags need auto-expiration. One base schema for the search pipeline, type-specific fields for the application logic."
- "The key reframe: this goes beyond retrieval. Most teams stop at indexing reference knowledge and searching it — that's valuable, but it's read-only. What you just saw is an agent that writes its own memories, selects them with hybrid search, reasons over them, and creates new memories from what it learns. That's a read-write memory system."
- "If you want to go deeper, the 'Memory in the Age of AI Agents' survey from December 2025 is the best overview of the field right now. Anthropic's context engineering guide is excellent for the practical side. And the write/select/compress/isolate framework in the references maps directly to what we just built."
- "For hybrid search and multi-modal retrieval specifically, check out the MongoDB video search blog on the developer site — same `$rankFusion` pattern applied to video segments with Voyage AI."
- "You can build this tonight. MongoDB Atlas free tier, Voyage AI API key, Claude API. The repo has the notebook and the Streamlit app."

---

## Demo App: What to Build

### UI Layout

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
│                                               │  (detail view for selected tab —           │
│                                               │   see sections below)                      │
│                                               │                                           │
│  ┌─────────────────────────────────────────┐  │                                           │
│  │ 💬 Message...                           │  │                                           │
│  └─────────────────────────────────────────┘  │                                           │
└───────────────────────────────────────────────┴───────────────────────────────────────────┘

Pre-loaded state: 🔵 snapshot only (1 memory, ~80 tokens)
After Message 1:  + 🟢🟢🟢 preferences (4 memories, ~240 tokens)
After Message 4:  + 🟡 flag (5 memories, ~300 tokens)
```

### Sidebar Tabs (4 tabs)

**📋 Document** — Click a memory in the list → shows full JSON with annotations. "View raw query" toggle reveals the `find()` command.
**🔍 Search** — After a query → shows pipeline JSON, results with scores from each sub-pipeline. "Run search only" button executes `$rankFusion` without agent reasoning.
**📝 Context** — After a query → shows the assembled prompt. Toggle: with memory / without memory.
**💾 Data** — Raw Layer 1 data: transactions filterable by month/category. "View aggregation" button shows the pipeline that produces snapshots from transactions.

### Memory Unit Schemas

All memory units share a base set of fields — the "memory unit interface" that the search and injection pipeline depends on. Each collection then adds type-specific fields.

**Base fields (shared by all memory collections):**

```python
base_memory_unit = {
    "user_id": str,           # always "alex_demo" for demo
    "subject": str,           # short display label
    "fact": str,              # natural language — what the LLM reads
    "embedding": list,        # Voyage AI voyage-3-large, 1024 dims
    "citations": list,        # provenance: where this came from
    "is_active": bool,        # true = current version
    "created_at": datetime,
}
```

**`preferences` collection (Semantic Memory):**

```python
{
    **base_memory_unit,
    "structured_data": {
        "area": str,          # e.g., "dining", "travel", "clothing"
        "priority": str,      # "high" | "low"
    },
}
# No supersedes (overwrite in place via is_active)
# No expires_at (permanent — user values don't auto-delete)
```

**`snapshots` collection (Episodic Memory):**

```python
{
    **base_memory_unit,
    "structured_data": {
        "as_of_date": str,             # e.g., "2026-02-01"
        "income": float,
        "fixed_expenses": float,
        "discretionary": float,
        "investments": float,
        "top_categories": dict,        # {"car_payments": 1245, "dining": 890, "groceries": 650}
    },
    "supersedes": ObjectId | None,     # pointer to previous snapshot version
}
# No expires_at (historical records are kept)
# supersedes chain enables versioning: new month → old gets is_active: false
```

**Why `supersedes`?** This implements a lightweight version of MongoDB's
[Document Versioning Pattern](https://www.mongodb.com/blog/post/building-with-patterns-the-document-versioning-pattern).
When the agent computes a new monthly snapshot, it:
1. Sets the old snapshot's `is_active: false`
2. Writes the new snapshot with `supersedes` pointing to the old one's `_id`

The search pre-filter (`is_active: true`) ensures only the current version
is selected. But the full history is preserved — you can walk the
`supersedes` chain to see how spending evolved month over month.

Only snapshots need this. Preferences don't version (if your dining priority
changes, the old one is just wrong — deactivate and write new). Flags don't
version (they're temporary insights that expire via TTL, not revisions of
the same observation).

**`flags` collection (Working Memory):**

```python
{
    **base_memory_unit,
    "structured_data": {
        "flag_type": str,              # e.g., "spending_mismatch"
        "severity": str,               # "high" | "medium" | "low"
        "mismatch": {
            "stated_priority": str,    # what the user said they care about
            "actual_spending": float,   # what the spending data shows
        },
    },
    "expires_at": datetime,            # BSON Date — MongoDB TTL auto-deletes
}
# No supersedes (flags don't version — they expire)
# TTL index on expires_at handles cleanup automatically
```

Three collections, tailored schemas, one shared interface for search and injection.

### Pre-loaded Data

The demo user is **Alex** (`user_id: "alex_demo"`) — a 30-something professional in the Bay Area earning ~$120K. The data tells a story: Alex has strong opinions about what matters (dining, travel, fitness) but their spending doesn't match (car payments dominate, fitness is $0). This mismatch is what the agent should surface.

#### Snapshot Collection (1 pre-loaded memory)

```json
{
  "_id": ObjectId("67c1a2b3d4e5f6a7b8c9d001"),
  "user_id": "alex_demo",
  "subject": "February 2026 Spending Summary",
  "fact": "February 2026: Monthly income $12,500. Fixed costs at $6,870 (55% — target is 50-60%). Biggest driver: car payments at $1,245/month (8% interest, 48 months remaining). Dining out: $890 across 18 transactions. Groceries: $650. Fitness spending: $0 despite gym membership cancellation in January. Travel: $0 this month. Investments: $1,023 (8.2% of income), on track for annual goal.",
  "embedding": [/* 1024 floats from Voyage voyage-3-large, input_type="document" */],
  "structured_data": {
    "as_of_date": "2026-02-01",
    "income": 12500,
    "fixed_expenses": 6870,
    "discretionary": 1000,
    "investments": 1023,
    "top_categories": {
      "rent": 2800,
      "car_payments": 1245,
      "dining": 890,
      "groceries": 650,
      "student_loans": 650
    }
  },
  "citations": [{"type": "computed", "source": "transactions", "query": "2026-02", "count": 47}],
  "is_active": true,
  "created_at": ISODate("2026-03-01T00:00:00Z"),
  "supersedes": null
}
```

**Design notes on the snapshot:**
- `fact` is a dense natural-language paragraph — this is what gets embedded and what the LLM reads.
- `structured_data` has the full financial picture with nested breakdowns — this is what the app logic reads for formatting, charts, or validation.
- In a production system, the snapshot computation could also identify anomalies and trigger `write_memories()` to create flag documents automatically. In the demo, we let the agent discover the mismatch during conversation instead — this is more dramatic and shows the inference capability live.
- `citations` point to the transaction collection with the query parameters used. This is the provenance chain.
- `supersedes: null` because this is the first snapshot. Next month's snapshot would have `supersedes: ObjectId("67c1a2b3d4e5f6a7b8c9d001")`.

#### Transactions Collection (~47 pre-loaded documents)

Time series collection. These are never queried by the agent — they exist so the snapshot has grounded provenance and so the demo data feels real.

```python
# Collection creation
db.create_collection("transactions", timeseries={
    "timeField": "transaction_date",
    "metaField": "metadata",
    "granularity": "hours"
})
```

**Full transaction dataset:**

```json
[
  // === RENT ===
  {"transaction_date": "2026-02-01T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "rent"}, "amount": 2800.00, "merchant": "Bay Ridge Apartments", "description": "February rent"},

  // === CAR PAYMENTS & INSURANCE ===
  {"transaction_date": "2026-02-01T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "car_payment"}, "amount": 1245.00, "merchant": "Toyota Financial", "description": "Monthly car payment - 2024 RAV4"},
  {"transaction_date": "2026-02-15T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "car_insurance"}, "amount": 285.00, "merchant": "GEICO", "description": "Monthly auto insurance"},

  // === STUDENT LOANS ===
  {"transaction_date": "2026-02-05T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "student_loans"}, "amount": 650.00, "merchant": "Nelnet", "description": "Student loan payment"},

  // === UTILITIES & FIXED ===
  {"transaction_date": "2026-02-01T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "utilities"}, "amount": 185.00, "merchant": "PG&E", "description": "Electric and gas"},
  {"transaction_date": "2026-02-01T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "utilities"}, "amount": 95.00, "merchant": "EBMUD", "description": "Water"},
  {"transaction_date": "2026-02-01T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "utilities"}, "amount": 70.00, "merchant": "Comcast", "description": "Internet"},
  {"transaction_date": "2026-02-03T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "phone"}, "amount": 110.00, "merchant": "T-Mobile", "description": "Phone plan"},
  {"transaction_date": "2026-02-01T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "subscriptions"}, "amount": 15.99, "merchant": "Netflix", "description": "Streaming"},
  {"transaction_date": "2026-02-01T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "subscriptions"}, "amount": 10.99, "merchant": "Spotify", "description": "Music"},
  {"transaction_date": "2026-02-01T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "subscriptions"}, "amount": 22.99, "merchant": "NYT", "description": "News subscription"},
  {"transaction_date": "2026-02-01T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "subscriptions"}, "amount": 24.99, "merchant": "Adobe", "description": "Creative Cloud"},
  {"transaction_date": "2026-02-01T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "health_insurance"}, "amount": 245.00, "merchant": "Kaiser Permanente", "description": "Health insurance premium"},
  {"transaction_date": "2026-02-10T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "other_fixed"}, "amount": 1000.00, "merchant": "Various", "description": "Miscellaneous fixed (laundry, parking, pet care)"},

  // === INVESTMENTS ===
  {"transaction_date": "2026-02-01T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "investments"}, "amount": 500.00, "merchant": "Vanguard", "description": "401k contribution"},
  {"transaction_date": "2026-02-01T00:00:00Z", "metadata": {"user_id": "alex_demo", "category": "investments"}, "amount": 523.00, "merchant": "Wealthfront", "description": "Automated investment"},

  // === DINING OUT (18 transactions, $890 total) ===
  // The volume of dining transactions tells a story: Alex eats out a lot and at decent places
  {"transaction_date": "2026-02-01T12:30:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 22.50, "merchant": "Tartine Bakery", "description": "Lunch"},
  {"transaction_date": "2026-02-02T19:00:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 68.00, "merchant": "Burma Superstar", "description": "Dinner with friends"},
  {"transaction_date": "2026-02-04T12:15:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 18.75, "merchant": "Souvla", "description": "Quick lunch"},
  {"transaction_date": "2026-02-06T19:30:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 47.50, "merchant": "Nopa", "description": "Dinner"},
  {"transaction_date": "2026-02-07T20:00:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 82.00, "merchant": "State Bird Provisions", "description": "Date night"},
  {"transaction_date": "2026-02-09T13:00:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 35.00, "merchant": "Prubechu", "description": "Brunch"},
  {"transaction_date": "2026-02-10T12:00:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 16.50, "merchant": "Marufuku Ramen", "description": "Lunch"},
  {"transaction_date": "2026-02-12T19:00:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 55.00, "merchant": "Che Fico", "description": "Dinner"},
  {"transaction_date": "2026-02-14T20:30:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 120.00, "merchant": "Lazy Bear", "description": "Valentine's dinner"},
  {"transaction_date": "2026-02-15T12:30:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 24.00, "merchant": "El Farolito", "description": "Lunch"},
  {"transaction_date": "2026-02-17T19:00:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 42.00, "merchant": "Dumpling Home", "description": "Dinner with coworkers"},
  {"transaction_date": "2026-02-18T12:00:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 19.50, "merchant": "Deli Board", "description": "Lunch"},
  {"transaction_date": "2026-02-20T19:30:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 58.00, "merchant": "Nopalito", "description": "Dinner"},
  {"transaction_date": "2026-02-21T11:00:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 38.00, "merchant": "Zazie", "description": "Weekend brunch"},
  {"transaction_date": "2026-02-23T19:00:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 65.00, "merchant": "Rich Table", "description": "Dinner"},
  {"transaction_date": "2026-02-24T12:30:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 52.00, "merchant": "Mister Jiu's", "description": "Business lunch"},
  {"transaction_date": "2026-02-25T18:00:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 78.25, "merchant": "Foreign Cinema", "description": "Dinner with friends"},
  {"transaction_date": "2026-02-27T12:00:00Z", "metadata": {"user_id": "alex_demo", "category": "dining_out"}, "amount": 48.00, "merchant": "b. patisserie", "description": "Brunch"},

  // === GROCERIES (8 transactions, $650 total) ===
  {"transaction_date": "2026-02-02T10:00:00Z", "metadata": {"user_id": "alex_demo", "category": "groceries"}, "amount": 95.00, "merchant": "Trader Joe's", "description": "Weekly groceries"},
  {"transaction_date": "2026-02-05T17:00:00Z", "metadata": {"user_id": "alex_demo", "category": "groceries"}, "amount": 42.00, "merchant": "Rainbow Grocery", "description": "Specialty items"},
  {"transaction_date": "2026-02-09T10:30:00Z", "metadata": {"user_id": "alex_demo", "category": "groceries"}, "amount": 88.00, "merchant": "Trader Joe's", "description": "Weekly groceries"},
  {"transaction_date": "2026-02-12T18:00:00Z", "metadata": {"user_id": "alex_demo", "category": "groceries"}, "amount": 35.00, "merchant": "Bi-Rite Market", "description": "Quick stop"},
  {"transaction_date": "2026-02-16T10:00:00Z", "metadata": {"user_id": "alex_demo", "category": "groceries"}, "amount": 110.00, "merchant": "Whole Foods", "description": "Weekly groceries"},
  {"transaction_date": "2026-02-20T17:30:00Z", "metadata": {"user_id": "alex_demo", "category": "groceries"}, "amount": 78.00, "merchant": "Trader Joe's", "description": "Weekly groceries"},
  {"transaction_date": "2026-02-23T10:00:00Z", "metadata": {"user_id": "alex_demo", "category": "groceries"}, "amount": 92.00, "merchant": "Trader Joe's", "description": "Weekly groceries"},
  {"transaction_date": "2026-02-27T17:00:00Z", "metadata": {"user_id": "alex_demo", "category": "groceries"}, "amount": 110.00, "merchant": "Whole Foods", "description": "Weekly groceries + hosting"},

  // === ENTERTAINMENT (4 transactions, $164 total) ===
  {"transaction_date": "2026-02-08T20:00:00Z", "metadata": {"user_id": "alex_demo", "category": "entertainment"}, "amount": 32.00, "merchant": "AMC Metreon", "description": "Movie tickets x2"},
  {"transaction_date": "2026-02-15T15:00:00Z", "metadata": {"user_id": "alex_demo", "category": "entertainment"}, "amount": 45.00, "merchant": "The Chapel", "description": "Live music"},
  {"transaction_date": "2026-02-22T14:00:00Z", "metadata": {"user_id": "alex_demo", "category": "entertainment"}, "amount": 62.00, "merchant": "Chase Center", "description": "Warriors game ticket"},
  {"transaction_date": "2026-02-26T19:00:00Z", "metadata": {"user_id": "alex_demo", "category": "entertainment"}, "amount": 25.00, "merchant": "Alamo Drafthouse", "description": "Movie + snacks"},

  // === SHOPPING (3 transactions, $125 total) ===
  {"transaction_date": "2026-02-11T14:00:00Z", "metadata": {"user_id": "alex_demo", "category": "shopping"}, "amount": 45.00, "merchant": "Target", "description": "Household items"},
  {"transaction_date": "2026-02-19T12:00:00Z", "metadata": {"user_id": "alex_demo", "category": "shopping"}, "amount": 35.00, "merchant": "Amazon", "description": "Kitchen supplies"},
  {"transaction_date": "2026-02-25T16:00:00Z", "metadata": {"user_id": "alex_demo", "category": "shopping"}, "amount": 45.00, "merchant": "REI", "description": "Water bottle + socks"},

  // === TRANSPORTATION (2 transactions, $75 total) ===
  {"transaction_date": "2026-02-08T22:00:00Z", "metadata": {"user_id": "alex_demo", "category": "transportation"}, "amount": 35.00, "merchant": "Uber", "description": "Ride home from concert"},
  {"transaction_date": "2026-02-14T22:30:00Z", "metadata": {"user_id": "alex_demo", "category": "transportation"}, "amount": 40.00, "merchant": "Uber", "description": "Ride home from dinner"},

  // === FITNESS: $0 ===
  // Notably absent. Alex cancelled gym membership in January. Zero fitness spending.
  // This absence IS the story — the mismatch the agent should discover.

  // === TRAVEL: $0 ===
  // Nothing this month. Alex says they love travel but hasn't spent on it.
]
```

**Transaction Summary (for verification):**

| Category | # Txns | Total | Notes |
|---|---|---|---|
| Rent | 1 | $2,800 | Fixed |
| Car payment | 1 | $1,245 | Fixed, 8% interest |
| Car insurance | 1 | $285 | Fixed |
| Student loans | 1 | $650 | Fixed |
| Utilities | 3 | $350 | PG&E + EBMUD + Comcast |
| Phone | 1 | $110 | Fixed |
| Subscriptions | 4 | $74.96 | Netflix, Spotify, NYT, Adobe |
| Health insurance | 1 | $245 | Fixed |
| Other fixed | 1 | $1,000 | Misc |
| Investments | 2 | $1,023 | 401k + Wealthfront |
| **Dining out** | **18** | **$890** | High frequency, good restaurants |
| Groceries | 8 | $650 | Weekly pattern |
| Entertainment | 4 | $164 | Movies, music, sports |
| Shopping | 3 | $125 | Household, not luxury |
| Transportation | 2 | $75 | Uber rides only |
| Fitness | 0 | $0 | **Conspicuous absence** |
| Travel | 0 | $0 | **Conspicuous absence** |
| **Total** | **47** | **$9,687** | Remaining $70 is rounding/buffer |

**Why this specific data:**

- **18 dining transactions at SF restaurants** — this is a person who genuinely prioritizes dining. When they say "I love dining out," the data backs it up. The agent should recognize the alignment.
- **$1,245 car payment at 8% interest** — this is the elephant in the room. It's the single largest discretionary-adjacent expense and the user says they don't care about cars. The mismatch is obvious once you have both the preference and the snapshot.
- **$0 fitness, $0 travel** — these are conspicuous absences. If Alex says fitness and travel matter, the zero spend creates another mismatch. The agent should flag this.
- **Investments on track** — not everything is a problem. The agent should acknowledge what's working.
- **47 transactions** — small enough to fit in a single context window (defeating the "just use long context" argument by design — the point isn't that you can't fit the data, it's that raw transactions don't contain "user prioritizes dining over cars").

#### Preferences Collection (empty at start)

The agent creates these during the demo. Here's what Message 1 should produce:

```json
// Created by write_memories() after: "I love dining out and traveling.
// I don't care about clothes or cars."

[
  {
    "_id": ObjectId("67c1a2b3d4e5f6a7b8c9d010"),
    "user_id": "alex_demo",
    "subject": "dining priority",
    "fact": "User considers dining out a high priority and enjoys it as a lifestyle activity.",
    "embedding": [/* 1024 floats, input_type="document" */],
    "structured_data": {
      "area": "dining",
      "priority": "high"
    },
    "citations": [{"type": "user_stated", "message_id": "msg_001", "turn": 1}],
    "is_active": true,
    "created_at": ISODate("2026-02-25T10:00:00Z")
  },
  {
    "_id": ObjectId("67c1a2b3d4e5f6a7b8c9d011"),
    "user_id": "alex_demo",
    "subject": "travel priority",
    "fact": "User considers traveling a high priority.",
    "embedding": [/* 1024 floats, input_type="document" */],
    "structured_data": {
      "area": "travel",
      "priority": "high"
    },
    "citations": [{"type": "user_stated", "message_id": "msg_001", "turn": 1}],
    "is_active": true,
    "created_at": ISODate("2026-02-25T10:00:01Z")
  },
  {
    "_id": ObjectId("67c1a2b3d4e5f6a7b8c9d012"),
    "user_id": "alex_demo",
    "subject": "cars priority",
    "fact": "User does not care about cars or car-related spending. Low priority.",
    "embedding": [/* 1024 floats, input_type="document" */],
    "structured_data": {
      "area": "cars",
      "priority": "low"
    },
    "citations": [{"type": "user_stated", "message_id": "msg_001", "turn": 1}],
    "is_active": true,
    "created_at": ISODate("2026-02-25T10:00:02Z")
  }
]
```

#### Flags Collection (empty at start)

The agent creates this during Message 4 of the demo. Here's what it should produce:

```json
// Created by write_memories() after agent cross-references preferences
// against snapshot and discovers the mismatch

{
  "_id": ObjectId("67c1a2b3d4e5f6a7b8c9d020"),
  "user_id": "alex_demo",
  "subject": "spending mismatch: cars vs stated priority",
  "fact": "User states cars are low priority but car-related costs (payment $1,245 + insurance $285 = $1,530/mo) are the largest discretionary expense category. This is 15.7% of take-home pay on something the user explicitly deprioritized. Meanwhile, high-priority areas like fitness ($0) and travel ($0) have zero spend.",
  "embedding": [/* 1024 floats, input_type="document" */],
  "structured_data": {
    "flag_type": "spending_mismatch",
    "severity": "high",
    "mismatch": {
      "stated_priority": "cars:low",
      "actual_spending": 1530
    }
  },
  "citations": [
    {"type": "memory", "ref": ObjectId("67c1a2b3d4e5f6a7b8c9d012"), "collection": "preferences"},
    {"type": "memory", "ref": ObjectId("67c1a2b3d4e5f6a7b8c9d001"), "collection": "snapshots"}
  ],
  "is_active": true,
  "created_at": ISODate("2026-02-25T10:05:00Z"),
  "expires_at": ISODate("2026-03-27T10:05:00Z")
}
```

**Design notes on the flag:**
- `citations` point to other memories (preference + snapshot), not to raw data. This is the provenance chain: flag → preference + snapshot → transactions. Three levels of traceability.
- `expires_at` is 30 days out. MongoDB TTL index will auto-delete this document. No app code needed.
- `severity: "high"` because the dollar amount is significant ($1,530/mo on a deprioritized category).

#### Memory State at Each Demo Step

| After | preferences | snapshots | flags | Total memories | Est. tokens |
|---|---|---|---|---|---|
| **Start** | 0 | 1 (Feb snapshot) | 0 | 1 | ~80 |
| **Message 1** ("I love dining...") | 3 (dining ↑, travel ↑, cars ↓) | 1 | 0 | 4 | ~240 |
| **Message 2** ("dining priority?") | 3 | 1 | 0 | 4 (no change) | ~240 |
| **Message 3** ("wasting money?") | 3 | 1 | 0 | 4 (no change) | ~240 |
| **Message 4** ("how am I doing?") | 3 | 1 | 1 (car mismatch) | 5 | ~300 |
| **Message 5** ("car payments?") | 3 | 1 | 1 | 5 (no change) | ~300 |

**Search indexes** (pre-created on each memory collection):

Each memory collection (`preferences`, `snapshots`, `flags`) gets its own vector and text indexes:

- Vector index: on `embedding` field, 1024 dims, cosine, pre-filters on `user_id` and `is_active`
- Text index: on `subject` and `fact` fields, with `user_id` (token) and `is_active` (boolean) for compound filtering

Additionally, `flags` gets a TTL index on `expires_at`.

### Agent Architecture (4 functions, plain Python)

No framework needed. The agent is four functions — one at session start, three per message:

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

```
Session Start
     │
     ▼
┌─────────────┐
│  load_       │
│  baseline()  │
│              │
│ • Direct     │
│   query      │
│   (PyMongo)  │
│ • No embed   │
│ • No search  │
└──────┬──────┘
       │ baseline memories (or [] for new users)
       ▼
Per Message
     │
     ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  select_     │───▶│  generate_  │───▶│  write_      │
│  memories()  │    │  response() │    │  memories()  │
│              │    │              │    │              │
│ • Embed query│    │ • Format    │    │ • Claude     │
│   (Voyage)   │    │   memories  │    │   extracts   │
│ • $rankFusion│    │   as context│    │   values     │
│   or $vector │    │ • Merge w/  │    │ • Embed fact │
│   Search     │    │   baseline  │    │   (Voyage)   │
│   (PyMongo)  │    │ • Claude    │    │ • Insert to  │
│              │    │   Sonnet    │    │   MongoDB    │
│              │    │   4.5       │    │   (PyMongo)  │
│              │    │   (Anthropic│    │              │
│              │    │    SDK)     │    │              │
└─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
   Search tab        Context tab         Document tab
   (sidebar)         (sidebar)           (sidebar)
```

**Why plain Python, not a framework?** The demo is about memory engineering — the data modeling, the search pipelines, the schema design. A framework would abstract away exactly the parts we want to teach. The audience should see the `$rankFusion` pipeline in 15 lines of PyMongo, not a `store.search()` call that hides it. This code works with any orchestration framework — LangGraph, CrewAI, or whatever they're already using.

### Demo Script (5 messages total)

| # | Section | User Types | What Happens |
|---|---------|-----------|-------------|
| 1 | §2 | "I love dining out and traveling. I don't care about clothes or cars." | Agent creates 2–3 preference memories. Show in Document tab. |
| 2 | §3 | "What's my dining priority?" | Hybrid search. Show $rankFusion pipeline + scores in Search tab. |
| 3 | §3 | "Where am I wasting money?" | Vector search. Show $vectorSearch pipeline + scores in Search tab. |
| 4 | §4 | "How am I doing this month?" | Full pipeline: select → inject → generate. Show Context tab (with/without toggle). Agent writes a flag memory. |
| 5 | §4 | *(optional, if time)* "What should I do about the car payments?" | Agent uses the flag memory it just created to give specific advice. |

### Reset Script

```python
# Clear all agent-written memories, keep pre-loaded snapshot
db.preferences.delete_many({"user_id": "alex_demo"})
db.flags.delete_many({"user_id": "alex_demo"})
# snapshots: keep the pre-loaded one
# transactions: never modified
```

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Streamlit |
| Agent | Plain Python (4 functions: `load_baseline`, `select_memories`, `generate_response`, `write_memories`) |
| Direct queries | Sidebar tabs query MongoDB directly (no agent) via `find`, `$search`, `$vectorSearch`, `$rankFusion` |
| LLM | Claude Sonnet 4.5 (Anthropic SDK) |
| Memory DB | MongoDB Atlas (PyMongo) |
| Embeddings | Voyage AI `voyage-3-large` |

---

## What We Cut (and why it's fine)

| From v3 | Cut | Why |
|---------|-----|-----|
| WSCI+D as a 5-operation framework to memorize | → "Write, Select, Inject" using established vocabulary | Three moves, same terms the audience will find in the broader context engineering literature. We note Compress and Isolate matter at scale. |
| Cognitive memory hierarchy as primary framing | → Plain English categories with explicit mapping | Audience hears "preference, snapshot, flag" but sees the mapping to semantic/episodic/working memory on the schema slide. Accessible first, rigorous second. |
| "Memory has a lifecycle" as a standalone takeaway | → Folded into takeaway #5 | Lifecycle (supersedes, TTL, is_active) is now part of "read-write system with a lifecycle." Demonstrated in schema walkthrough. |
| Agent Trace tab (4th sidebar tab) | → Dropped, replaced with Data tab | Search tab + Context tab cover agent internals. Data tab shows raw Layer 1 data and direct MongoDB queries — serves the "when you don't need an agent" teaching point. |
| 6 chat messages | → 4–5 messages | Tighter script, more time to explain what's on screen. |
| Confidence field | → Removed from schema entirely | Doesn't contribute to retrieval or demo. Invites questions we can't answer in 30 min. Trust level conveyed by memory origin (user-stated vs. computed vs. inferred). |
| Memory versioning (supersedes chains) | → Mention `is_active` once | Important for production, not for a 30-min talk. |

## What We Added

| New in v4/v5 | Why |
|-----------|-----|
| **"Agent memory goes beyond retrieval" as takeaway #5** | The most common gap in the field. Teams stop at reference knowledge retrieval (RAG) and miss the read-write loop. Multiple research papers and industry blogs draw this distinction. Our demo *shows* it — we just needed to *name* it. |
| **Reference Knowledge vs. Agent Memory comparison slide** | Gives the audience a crisp mental model to take back to their teams. Clarifies that RAG is a retrieval pattern, not a data type. |
| **"Go Deeper" slide with research references** | Positions the talk within the broader research landscape. The survey, Anthropic's guide, LangChain's framework, and the MongoDB video search blog give the audience four paths to continue learning. |
| **`load_baseline()` as 4th function (deterministic SELECT)** | Session-start loading of core memories. Makes the cold start vs. warm start distinction visible. Completes the agent architecture without adding a new Move or Pipeline — it's a mode of SELECT. |
| **Data tab (sidebar) + direct query buttons** | Shows MongoDB's search capabilities without the agent. Makes the "agent vs. direct query" principle tangible. Each tab gets "View raw query" toggle. Search tab gets "Run search only" button. |
| **Cold start → warm start demo arc** | New user (empty memory, generic responses) → pre-loaded Alex (personalized from first message) → return to new user (memories now loaded). Shows the full spectrum of memory's effect on agent quality. |