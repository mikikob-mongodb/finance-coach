"""Query-driven SELECT - Hybrid search for relevant memories.

Embed query (Voyage), run $rankFusion hybrid search (MongoDB),
merge with baseline (dedup). Returns top-k memories.

From technical-reference.md Section 4.

Note: This requires Atlas Search indexes (vector + text) to be created.
If indexes aren't ready, falls back to returning just the baseline.
"""

import logging

from pymongo.database import Database

from src.config import (
    COLLECTION_FLAGS,
    COLLECTION_PREFERENCES,
    COLLECTION_SNAPSHOTS,
    HYBRID_SEARCH_LIMIT,
    VECTOR_NUM_CANDIDATES,
)

logger = logging.getLogger(__name__)

# Memory collections to search
MEMORY_COLLECTIONS = [COLLECTION_PREFERENCES, COLLECTION_SNAPSHOTS, COLLECTION_FLAGS]


def select_memories(
    db: Database,
    collection_name: str,
    query_embedding: list[float],
    user_query: str,
    user_id: str,
) -> list[dict]:
    """Run $rankFusion hybrid search on a single collection.

    Combines vector search (semantic similarity) with text search (keyword matching)
    using MongoDB's $rankFusion aggregation stage.

    Args:
        db: PyMongo database handle
        collection_name: Name of the collection to search
        query_embedding: 1024-dim embedding of the user query
        user_query: The raw user query text
        user_id: The user's ID for pre-filtering

    Returns:
        List of matching memory documents, each tagged with _collection field.
    """
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
                                        "is_active": True,
                                    },
                                }
                            }
                        ],
                        "text": [
                            {
                                "$search": {
                                    "index": "memory_text_index",
                                    "text": {
                                        "query": user_query,
                                        "path": ["subject", "fact"],
                                    },
                                }
                            },
                            {
                                "$match": {
                                    "user_id": user_id,
                                    "is_active": True,
                                }
                            },
                            {"$limit": HYBRID_SEARCH_LIMIT},
                        ],
                    }
                }
            }
        }
    ]

    try:
        results = list(db[collection_name].aggregate(pipeline))
        for r in results:
            r["_collection"] = collection_name
        logger.debug(
            "Hybrid search on %s returned %d results", collection_name, len(results)
        )
        return results
    except Exception as e:
        # If indexes don't exist yet, log and return empty
        logger.warning("Hybrid search failed on %s: %s", collection_name, e)
        return []


def select_memories_vector_only(
    db: Database,
    collection_name: str,
    query_embedding: list[float],
    user_id: str,
) -> list[dict]:
    """Fallback: Vector-only search when hybrid search indexes aren't ready.

    Uses $vectorSearch without $rankFusion.
    """
    pipeline = [
        {
            "$vectorSearch": {
                "index": "memory_vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": VECTOR_NUM_CANDIDATES,
                "limit": HYBRID_SEARCH_LIMIT,
                "filter": {
                    "user_id": user_id,
                    "is_active": True,
                },
            }
        }
    ]

    try:
        results = list(db[collection_name].aggregate(pipeline))
        for r in results:
            r["_collection"] = collection_name
        logger.debug(
            "Vector search on %s returned %d results", collection_name, len(results)
        )
        return results
    except Exception as e:
        logger.warning("Vector search failed on %s: %s", collection_name, e)
        return []


def select_all_memories(
    db: Database,
    query_embedding: list[float],
    user_query: str,
    user_id: str,
    baseline: list[dict],
    use_hybrid: bool = True,
) -> list[dict]:
    """Search all memory collections, merge with baseline, dedup.

    Args:
        db: PyMongo database handle
        query_embedding: 1024-dim embedding of the user query
        user_query: The raw user query text
        user_id: The user's ID for pre-filtering
        baseline: Baseline memories from load_baseline()
        use_hybrid: If True, use $rankFusion. If False, vector-only.

    Returns:
        Combined list of baseline + search results, deduplicated.
    """
    all_results = []

    for coll in MEMORY_COLLECTIONS:
        if use_hybrid:
            results = select_memories(db, coll, query_embedding, user_query, user_id)
        else:
            results = select_memories_vector_only(db, coll, query_embedding, user_id)
        all_results.extend(results)

    # Dedup: skip memories already in baseline
    baseline_ids = {m["_id"] for m in baseline}
    new_results = [r for r in all_results if r["_id"] not in baseline_ids]

    combined = baseline + new_results
    logger.info(
        "Selected %d memories (%d baseline + %d from search)",
        len(combined),
        len(baseline),
        len(new_results),
    )

    return combined
