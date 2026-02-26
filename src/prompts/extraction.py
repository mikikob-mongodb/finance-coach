"""Extraction prompt for write_memories.

From technical-reference.md Section 6.
"""

EXTRACTION_PROMPT = """You just had this exchange with a user:

USER: {user_message}
ASSISTANT: {assistant_response}

Your task: extract any new facts worth remembering as structured memory units. Only extract facts that are:
1. Explicitly stated by the user (preferences, priorities, life details)
2. Inferred from cross-referencing existing data (mismatches, patterns, anomalies)

Do NOT create memories for:
- Things already in the existing memory context (no duplicates)
- Vague or uncertain statements ("I might want to..." — wait until they commit)
- Transient conversational details ("thanks!" or "ok sounds good")

FLAG CREATION RULES (be conservative):
- Do NOT create flags from a single message. Wait until you have at least 2 exchanges of context before flagging mismatches.
- Only create mismatch/concern flags when there's a clear, explicit conflict between stated priorities and spending data.
- If this is the first time the user mentions their priorities, just create preference memories — don't immediately flag mismatches.

For each memory unit, provide a JSON array. Each item should have:

```json
[
  {{
    "collection": "preferences" | "flags",
    "subject": "short topic label",
    "fact": "natural language statement the LLM can read",
    "structured_data": {{ ... }},
    "citations": ["source description"],
    "expires_in_days": null | number
  }}
]
```

STRUCTURED DATA FORMATS:

For preferences (user-stated priorities):
```json
{{
  "area": "dining" | "travel" | "fitness" | "cars" | "clothes" | "entertainment" | "groceries" | "shopping",
  "priority": "high" | "low"
}}
```

For flags (agent-inferred insights like spending mismatches):
```json
{{
  "flag_type": "spending_mismatch",
  "severity": "high" | "medium" | "low",
  "mismatch": {{
    "stated_priority": "area:priority",
    "actual_spending": dollar_amount
  }}
}}
```

If no new memories should be created, return an empty array: []

EXISTING MEMORIES (do not duplicate):
{existing_memory_summaries}

Return ONLY the JSON array, no other text."""


def build_extraction_prompt(
    user_message: str,
    assistant_response: str,
    existing_memory_summaries: str,
) -> str:
    """Build the extraction prompt with conversation and existing memories.

    Args:
        user_message: The user's message
        assistant_response: The assistant's response
        existing_memory_summaries: Output from format_memory_summaries()

    Returns:
        Complete extraction prompt.
    """
    return EXTRACTION_PROMPT.format(
        user_message=user_message,
        assistant_response=assistant_response,
        existing_memory_summaries=existing_memory_summaries,
    )
