"""WRITE - Memory extraction from conversation.

Ask Claude to extract memory-worthy units, embed each fact field (Voyage),
insert to MongoDB. Handle supersedes if contradicting existing memory.

From technical-reference.md Section 6.
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone

import anthropic
from pymongo.database import Database

from src.agent.memory_formatter import format_memory_summaries
from src.config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    COLLECTION_FLAGS,
    COLLECTION_PREFERENCES,
    FLAG_DEFAULT_EXPIRY_DAYS,
)
from src.embeddings import embed_document
from src.prompts.extraction import build_extraction_prompt

logger = logging.getLogger(__name__)

# Initialize client
_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    """Get or create the Anthropic client."""
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _parse_extraction_response(response_text: str) -> list[dict]:
    """Parse the JSON array from Claude's extraction response.

    Handles various response formats including markdown code blocks.
    """
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response_text)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        json_str = response_text.strip()

    # Handle empty array responses
    if json_str in ("[]", ""):
        return []

    try:
        result = json.loads(json_str)
        if isinstance(result, list):
            return result
        logger.warning("Extraction returned non-list: %s", type(result))
        return []
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse extraction JSON: %s", e)
        logger.debug("Raw response: %s", response_text[:500])
        return []


def _deactivate_conflicting_preferences(
    db: Database, user_id: str, area: str
) -> int:
    """Deactivate existing preferences for the same area.

    Called when a new preference might contradict an existing one.
    Returns count of deactivated preferences.
    """
    result = db[COLLECTION_PREFERENCES].update_many(
        {"user_id": user_id, "structured_data.area": area, "is_active": True},
        {"$set": {"is_active": False}},
    )
    if result.modified_count > 0:
        logger.info(
            "Deactivated %d existing preference(s) for area '%s'",
            result.modified_count,
            area,
        )
    return result.modified_count


def write_memories(
    user_message: str,
    assistant_response: str,
    user_id: str,
    existing_memories: list[dict],
    db: Database,
) -> list[dict]:
    """Extract and write new memories from the conversation.

    This is the WRITE step: ask Claude to identify memory-worthy facts,
    embed them via Voyage, and store in MongoDB.

    Args:
        user_message: The user's message
        assistant_response: The assistant's response
        user_id: The user's ID
        existing_memories: Current memories (to avoid duplicates)
        db: PyMongo database handle

    Returns:
        List of newly created memory documents.
    """
    client = _get_client()

    # Build extraction prompt
    summaries = format_memory_summaries(existing_memories)
    prompt = build_extraction_prompt(user_message, assistant_response, summaries)

    logger.debug("Calling Claude for memory extraction")

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = response.content[0].text

    except Exception as e:
        logger.error("Failed to call Claude for extraction: %s", e)
        return []

    # Parse extraction results
    extractions = _parse_extraction_response(response_text)
    if not extractions:
        logger.debug("No memories to extract")
        return []

    logger.info("Extracted %d potential memories", len(extractions))

    # Process each extraction
    new_memories = []
    now = datetime.now(timezone.utc)

    for ext in extractions:
        collection = ext.get("collection")
        if collection not in (COLLECTION_PREFERENCES, COLLECTION_FLAGS):
            logger.warning("Invalid collection '%s', skipping", collection)
            continue

        fact = ext.get("fact", "")
        if not fact:
            logger.warning("Empty fact, skipping")
            continue

        # Embed the fact
        try:
            embedding = embed_document(fact)
        except Exception as e:
            logger.error("Failed to embed fact: %s", e)
            continue

        # Build the memory document
        memory_doc = {
            "user_id": user_id,
            "subject": ext.get("subject", ""),
            "fact": fact,
            "embedding": embedding,
            "structured_data": ext.get("structured_data", {}),
            "citations": ext.get("citations", []),
            "is_active": True,
            "created_at": now,
        }

        # Handle collection-specific fields
        if collection == COLLECTION_PREFERENCES:
            # Deactivate conflicting preferences for the same area
            area = memory_doc["structured_data"].get("area")
            if area:
                _deactivate_conflicting_preferences(db, user_id, area)

        elif collection == COLLECTION_FLAGS:
            # Set expiration
            expires_in_days = ext.get("expires_in_days") or FLAG_DEFAULT_EXPIRY_DAYS
            memory_doc["expires_at"] = now + timedelta(days=expires_in_days)

        # Insert to database
        try:
            result = db[collection].insert_one(memory_doc)
            memory_doc["_id"] = result.inserted_id
            memory_doc["_collection"] = collection
            new_memories.append(memory_doc)
            logger.info(
                "Created %s memory: %s", collection, memory_doc.get("subject")
            )
        except Exception as e:
            logger.error("Failed to insert memory: %s", e)
            continue

    logger.info("Wrote %d new memories", len(new_memories))
    return new_memories
