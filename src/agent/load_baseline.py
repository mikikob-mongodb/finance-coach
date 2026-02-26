"""Deterministic SELECT - Fetch core memories at session start.

No search, no embedding - just direct MongoDB queries.
Returns latest snapshot + top preferences. Empty list for new users.

From technical-reference.md Section 4.
"""

import logging

from pymongo.database import Database

from src.config import (
    BASELINE_PREFERENCES_LIMIT,
    COLLECTION_PREFERENCES,
    COLLECTION_SNAPSHOTS,
)

logger = logging.getLogger(__name__)


def load_baseline(db: Database, user_id: str) -> list[dict]:
    """Fetch core memories at session start. No search, no embedding.

    This is the deterministic SELECT that runs once per session.
    For returning users (warm start), returns the latest snapshot + preferences.
    For new users (cold start), returns an empty list.

    Args:
        db: PyMongo database handle
        user_id: The user's ID

    Returns:
        List of memory documents, each tagged with _collection field.
        Empty list for new users.
    """
    baseline = []

    # Latest snapshot (episodic memory)
    snapshot = db[COLLECTION_SNAPSHOTS].find_one(
        {"user_id": user_id, "is_active": True},
        sort=[("created_at", -1)],
    )
    if snapshot:
        snapshot["_collection"] = COLLECTION_SNAPSHOTS
        baseline.append(snapshot)
        logger.debug("Loaded snapshot: %s", snapshot.get("subject"))

    # Top preferences by recency (semantic memory)
    prefs = list(
        db[COLLECTION_PREFERENCES].find(
            {"user_id": user_id, "is_active": True},
            sort=[("created_at", -1)],
            limit=BASELINE_PREFERENCES_LIMIT,
        )
    )
    for p in prefs:
        p["_collection"] = COLLECTION_PREFERENCES
    baseline.extend(prefs)
    logger.debug("Loaded %d preferences", len(prefs))

    logger.info(
        "Loaded baseline for user %s: %d memories (%s)",
        user_id,
        len(baseline),
        "warm start" if baseline else "cold start",
    )

    return baseline
