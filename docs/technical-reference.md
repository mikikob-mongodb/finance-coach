# Technical Reference — Finance Coach

Code-ready specs for implementation. No prose — just schemas, queries, prompts, and constants.

Source of truth: `oreilly-talk-app-spec.md` and `oreilly-talk-concepts.md`.

---

## 1. Constants

```python
# Database
DATABASE_NAME = "finance_coach_db"
DEMO_USER_ID = "alex_demo"
APP_NAME = "devrel-presentation-python-financial-coach-oreilly"

# Collections
COLLECTION_PREFERENCES = "preferences"
COLLECTION_SNAPSHOTS = "snapshots"
COLLECTION_FLAGS = "flags"
COLLECTION_TRANSACTIONS = "transactions"

# Voyage AI
VOYAGE_MODEL = "voyage-3-large"
VOYAGE_DIMENSIONS = 1024

# Claude
CLAUDE_MODEL = "claude-sonnet-4-5-20250514"

# Search
HYBRID_SEARCH_LIMIT = 5
VECTOR_NUM_CANDIDATES = 50
BASELINE_PREFERENCES_LIMIT = 5

# Memory
FLAG_DEFAULT_EXPIRY_DAYS = 30
```

---

## 2. Schemas

### Base Memory Unit (shared fields)

All memory collections share these fields:

```python
base_memory_unit = {
    "_id": ObjectId,
    "user_id": str,                # partition key
    "subject": str,                # short label, text-indexed
    "fact": str,                   # natural language, text-indexed + embedded
    "embedding": list[float],      # 1024 floats from Voyage voyage-3-large
    "citations": list,             # provenance chain
    "is_active": bool,             # pre-filter: True = current, False = superseded/deactivated
    "created_at": datetime,        # UTC
}
```

### preferences (Semantic Memory)

```python
{
    **base_memory_unit,
    "structured_data": {
        "area": str,               # "dining", "travel", "fitness", "cars", "clothes"
        "priority": str,           # "high" | "low"
    },
}
# No expires_at (permanent until contradicted)
# No supersedes (deactivate old + write new if priority changes)
# Origin: extracted from user conversation
```

### snapshots (Episodic Memory)

```python
{
    **base_memory_unit,
    "structured_data": {
        "as_of_date": str,         # "2026-02"
        "income": float,
        "fixed_expenses": float,
        "discretionary": float,
        "investments": float,
        "top_categories": dict,    # {"car_payments": 1245, "dining": 890, "groceries": 650}
    },
    "supersedes": ObjectId | None, # pointer to previous snapshot version
}
# No expires_at (historical records kept)
# supersedes chain: new month → old gets is_active: false
# Origin: computed from transactions via aggregation pipeline
```

### flags (Working Memory)

```python
{
    **base_memory_unit,
    "structured_data": {
        "flag_type": str,          # "spending_mismatch"
        "severity": str,           # "high" | "medium" | "low"
        "mismatch": {
            "stated_priority": str,    # "cars:low", "fitness:high"
            "actual_spending": float,  # dollar amount
        },
    },
    "expires_at": datetime,        # MongoDB TTL auto-deletes
}
# No supersedes (flags don't version — they expire)
# Origin: agent-inferred from cross-referencing preferences × snapshots
```

### transactions (Time Series — Operational Data)

```python
{
    "_id": ObjectId,
    "transaction_date": datetime,  # time field for time series collection
    "metadata": {
        "user_id": str,            # metadata field for time series collection
        "category": str,           # "rent", "car_payment", "dining_out", etc.
    },
    "amount": float,
    "merchant": str,
    "description": str,
}
# Time series collection with:
#   timeField: "transaction_date"
#   metaField: "metadata"
# Never searched by the agent — provides provenance for snapshots
# Queried directly by the Data tab in the sidebar
```

---

## 3. Index Definitions

### Vector Indexes

One per memory collection. Create via Atlas UI or Atlas Admin API.

```json
// Index name: "memory_vector_index"
// Apply to: preferences, snapshots, flags
{
  "type": "vectorSearch",
  "definition": {
    "fields": [
      {
        "type": "vector",
        "path": "embedding",
        "numDimensions": 1024,
        "similarity": "cosine"
      },
      {
        "type": "filter",
        "path": "user_id"
      },
      {
        "type": "filter",
        "path": "is_active"
      }
    ]
  }
}
```

### Text Indexes

One per memory collection. Create via Atlas UI or Atlas Search.

```json
// Index name: "memory_text_index"
// Apply to: preferences, snapshots, flags
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "subject": { "type": "string" },
      "fact": { "type": "string" },
      "user_id": { "type": "token" },
      "is_active": { "type": "boolean" }
    }
  }
}
```

### TTL Index

Flags collection only. Create via PyMongo.

```python
db.flags.create_index("expires_at", expireAfterSeconds=0)
```

---

## 4. Queries

### load_baseline() — Deterministic SELECT

```python
def load_baseline(db, user_id: str) -> list[dict]:
    """Fetch core memories at session start. No search, no embedding."""
    baseline = []

    # Latest snapshot
    snapshot = db.snapshots.find_one(
        {"user_id": user_id, "is_active": True},
        sort=[("created_at", -1)]
    )
    if snapshot:
        snapshot["_collection"] = "snapshots"
        baseline.append(snapshot)

    # Top preferences by recency
    prefs = list(db.preferences.find(
        {"user_id": user_id, "is_active": True},
        sort=[("created_at", -1)],
        limit=BASELINE_PREFERENCES_LIMIT
    ))
    for p in prefs:
        p["_collection"] = "preferences"
    baseline.extend(prefs)

    return baseline
```

### select_memories() — Query-driven SELECT (Hybrid Search)

```python
def select_memories(db, collection_name: str, query_embedding: list[float],
                    user_query: str, user_id: str) -> list[dict]:
    """Run $rankFusion hybrid search on a single collection."""
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
                                    "numCandidates": VECTOR_NUM_CANDIDATES,
                                    "limit": HYBRID_SEARCH_LIMIT,
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
                                                {"equals": {"path": "user_id", "value": user_id}},
                                                {"equals": {"path": "is_active", "value": True}}
                                            ]
                                        }
                                    }
                                }
                            },
                            {"$limit": HYBRID_SEARCH_LIMIT}
                        ]
                    }
                }
            }
        }
    ]
    results = list(db[collection_name].aggregate(pipeline))
    for r in results:
        r["_collection"] = collection_name
    return results


def select_all_memories(db, query_embedding: list[float],
                        user_query: str, user_id: str,
                        baseline: list[dict]) -> list[dict]:
    """Search all memory collections, merge with baseline, dedup."""
    all_results = []
    for coll in [COLLECTION_PREFERENCES, COLLECTION_SNAPSHOTS, COLLECTION_FLAGS]:
        results = select_memories(db, coll, query_embedding, user_query, user_id)
        all_results.extend(results)

    # Dedup: skip memories already in baseline
    baseline_ids = {m["_id"] for m in baseline}
    new_results = [r for r in all_results if r["_id"] not in baseline_ids]

    return baseline + new_results
```

### Direct queries (sidebar tabs)

```python
# Memory tab — all active memories
def get_active_memories(db, user_id: str) -> list[dict]:
    memories = []
    for coll_name in [COLLECTION_PREFERENCES, COLLECTION_SNAPSHOTS, COLLECTION_FLAGS]:
        docs = list(db[coll_name].find(
            {"user_id": user_id, "is_active": True},
            sort=[("created_at", -1)]
        ))
        for d in docs:
            d["_collection"] = coll_name
        memories.extend(docs)
    return memories


# Data tab — raw transactions
def get_transactions(db, user_id: str, month: str = None, category: str = None) -> list[dict]:
    query = {"metadata.user_id": user_id}
    if month:  # e.g., "2026-02"
        year, mo = month.split("-")
        start = datetime(int(year), int(mo), 1)
        if int(mo) == 12:
            end = datetime(int(year) + 1, 1, 1)
        else:
            end = datetime(int(year), int(mo) + 1, 1)
        query["transaction_date"] = {"$gte": start, "$lt": end}
    if category:
        query["metadata.category"] = category
    return list(db.transactions.find(query, sort=[("transaction_date", 1)]))
```

---

## 5. Embedding

```python
import voyageai

client = voyageai.Client()  # uses VOYAGE_API_KEY env var

def embed_document(text: str) -> list[float]:
    """Embed a memory fact for storage."""
    result = client.embed([text], model=VOYAGE_MODEL, input_type="document")
    return result.embeddings[0]


def embed_query(text: str) -> list[float]:
    """Embed a user query for search."""
    result = client.embed([text], model=VOYAGE_MODEL, input_type="query")
    return result.embeddings[0]
```

---

## 6. Prompts

### System Prompt (generate_response)

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

### Memory Formatting (Python)

```python
def format_memories(memories: list[dict]) -> str:
    """Format selected memories into a structured context block."""
    sections = {"preferences": [], "snapshots": [], "flags": []}

    for mem in memories:
        collection = mem["_collection"]
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

### Example formatted output (~300 tokens)

```
Stated Preferences:
- Dining: high priority (user-stated)
- Travel: high priority (user-stated)
- Cars: low priority (user-stated)

Spending Snapshots:
- 2026-02: Income $9,757, Fixed $6,830, Discretionary $1,904. Top spending: car payments: $1,245, dining: $890, groceries: $650

Active Flags:
- ⚠ Spending Mismatch: User states fitness is high priority but spending is $0. Car payments ($1,245/mo) consuming budget.
```

### Extraction Prompt (write_memories)

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

**Notes:**
- Only `preferences` and `flags` are writable by the agent
- `snapshots` are computed from transactions, not extracted from conversation
- `expires_in_days` → convert to `expires_at` datetime for flags (default: 30 days)
- Empty array `[]` is the expected response for most turns

---

## 7. Structured Data Templates

### Preference structured_data

```json
{
  "area": "dining",
  "priority": "high"
}
```

Valid areas: `"dining"`, `"travel"`, `"fitness"`, `"cars"`, `"clothes"`, `"entertainment"`, `"groceries"`, `"shopping"`
Valid priorities: `"high"`, `"low"`

### Snapshot structured_data

```json
{
  "as_of_date": "2026-02",
  "income": 9757,
  "fixed_expenses": 6830,
  "discretionary": 1904,
  "investments": 1023,
  "top_categories": {
    "rent": 2800,
    "car_payments": 1245,
    "dining": 890,
    "groceries": 650,
    "student_loans": 650
  }
}
```

### Flag structured_data

```json
{
  "flag_type": "spending_mismatch",
  "severity": "high",
  "mismatch": {
    "stated_priority": "cars:low",
    "actual_spending": 1530
  }
}
```

Valid flag_types: `"spending_mismatch"`
Valid severities: `"high"`, `"medium"`, `"low"`

### Transaction document

```json
{
  "transaction_date": "2026-02-01T12:30:00Z",
  "metadata": {
    "user_id": "alex_demo",
    "category": "dining_out"
  },
  "amount": 22.50,
  "merchant": "Tartine Bakery",
  "description": "Lunch"
}
```

Valid categories: `"rent"`, `"car_payment"`, `"car_insurance"`, `"utilities"`, `"student_loans"`, `"phone"`, `"subscriptions"`, `"health_insurance"`, `"other_fixed"`, `"investments"`, `"dining_out"`, `"groceries"`, `"entertainment"`, `"shopping"`, `"transportation"`

---

## 8. Pydantic Models

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from bson import ObjectId


class PreferenceData(BaseModel):
    area: str
    priority: str  # "high" | "low"


class SnapshotData(BaseModel):
    as_of_date: str
    income: float
    fixed_expenses: float
    discretionary: float
    investments: float
    top_categories: dict[str, float]


class MismatchData(BaseModel):
    stated_priority: str
    actual_spending: float


class FlagData(BaseModel):
    flag_type: str
    severity: str  # "high" | "medium" | "low"
    mismatch: MismatchData


class MemoryUnit(BaseModel):
    """Base memory unit — shared fields across all collections."""
    user_id: str
    subject: str
    fact: str
    embedding: list[float] = Field(default_factory=list)
    citations: list = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Preference(MemoryUnit):
    structured_data: PreferenceData


class Snapshot(MemoryUnit):
    structured_data: SnapshotData
    supersedes: Optional[str] = None  # ObjectId as string


class Flag(MemoryUnit):
    structured_data: FlagData
    expires_at: datetime


class ExtractionResult(BaseModel):
    """What the extraction prompt returns."""
    collection: str  # "preferences" | "flags"
    subject: str
    fact: str
    structured_data: dict
    citations: list[str] = Field(default_factory=list)
    expires_in_days: Optional[int] = None
```

---

## 9. Reset Script

```python
def reset_demo(db, user_id: str = DEMO_USER_ID):
    """Reset to pre-loaded state. Keep snapshot + transactions."""
    db.preferences.delete_many({"user_id": user_id})
    db.flags.delete_many({"user_id": user_id})
    # snapshots: keep the pre-loaded one
    # transactions: never modified
```

---

## 10. Environment Variables

### .env (app uses these)

```
MONGODB_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/
MONGODB_DATABASE=finance_coach_db
VOYAGE_API_KEY=vo-...
ANTHROPIC_API_KEY=sk-ant-...
```

### .envrc (direnv — bridges .env to MCP server)

```bash
dotenv
export MDB_MCP_CONNECTION_STRING="$MONGODB_URI"
```

The app reads `MONGODB_URI`. The MongoDB MCP Server reads `MDB_MCP_CONNECTION_STRING`. The `.envrc` aliases one to the other so both work from a single `.env` file. Run `direnv allow` once after creating.

### .mcp.json (MongoDB MCP Server for Claude Code)

```json
{
  "mcpServers": {
    "MongoDB": {
      "command": "npx",
      "args": [
        "-y",
        "mongodb-mcp-server@latest"
      ]
    }
  }
}
```

No secrets in this file — reads `MDB_MCP_CONNECTION_STRING` from the environment.

---

## 11. appName (DevRel Attribution)

All MongoDB connections must include `appName` for DevRel tracking. Use the driver API, not the connection string parameter — this prevents users from accidentally overriding it when pasting their own Atlas URI.

```python
# In your MongoClient initialization:
from pymongo import MongoClient

client = MongoClient(MONGODB_URI, appname=APP_NAME)
```

**Do NOT use the connection string approach:**
```
# WRONG — user will overwrite when pasting their Atlas URI
mongodb+srv://...?appName=devrel-presentation-python-financial-coach-oreilly
```

**Naming breakdown:**
- `devrel` — DevRel team prefix
- `presentation` — medium (this is a live talk)
- `python` — primary technology
- `financial-coach` — secondary (the demo app)
- `oreilly` — platform/event

If the demo code is also published to GitHub, use a separate appName for the repo:
```python
APP_NAME_GITHUB = "devrel-github-python-financial-coach-oreilly"
```

Track both values in Wrike under "App Name Content" and "App Name GitHub".