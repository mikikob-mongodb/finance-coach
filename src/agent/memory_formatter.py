"""Format memories for context window injection.

From technical-reference.md Section 6.
"""

import logging

logger = logging.getLogger(__name__)


def format_memories(memories: list[dict]) -> str:
    """Format selected memories into a structured context block.

    Organizes memories by type (preferences, snapshots, flags) and
    formats them for injection into the system prompt.

    Args:
        memories: List of memory documents with _collection field

    Returns:
        Formatted string for the <user_context> block.
        Empty string if no memories.
    """
    if not memories:
        return ""

    sections = {"preferences": [], "snapshots": [], "flags": []}

    for mem in memories:
        collection = mem.get("_collection", "")

        if collection == "preferences":
            sd = mem.get("structured_data", {})
            area = sd.get("area", "unknown").title()
            priority = sd.get("priority", "unknown")
            sections["preferences"].append(
                f"- {area}: {priority} priority (user-stated)"
            )

        elif collection == "snapshots":
            sd = mem.get("structured_data", {})
            top_cats = sd.get("top_categories", {})
            top_str = ", ".join(
                f"{k.replace('_', ' ')}: ${v:,.0f}" for k, v in top_cats.items()
            )
            sections["snapshots"].append(
                f"- {sd.get('as_of_date', 'unknown')}: "
                f"Income ${sd.get('income', 0):,.0f}, "
                f"Fixed ${sd.get('fixed_expenses', 0):,.0f}, "
                f"Discretionary ${sd.get('discretionary', 0):,.0f}. "
                f"Top spending: {top_str}"
            )

        elif collection == "flags":
            sd = mem.get("structured_data", {})
            flag_type = sd.get("flag_type", "unknown").replace("_", " ").title()
            fact = mem.get("fact", "")
            sections["flags"].append(f"- ⚠ {flag_type}: {fact}")

    # Build output
    output_parts = []

    if sections["preferences"]:
        output_parts.append("Stated Preferences:\n" + "\n".join(sections["preferences"]))

    if sections["snapshots"]:
        output_parts.append("Spending Snapshots:\n" + "\n".join(sections["snapshots"]))

    if sections["flags"]:
        output_parts.append("Active Flags:\n" + "\n".join(sections["flags"]))

    result = "\n\n".join(output_parts)
    logger.debug("Formatted %d memories into %d chars", len(memories), len(result))

    return result


def format_memory_summaries(memories: list[dict]) -> str:
    """Format memories as brief summaries for the extraction prompt.

    Used to show existing memories so Claude doesn't create duplicates.

    Args:
        memories: List of memory documents

    Returns:
        Brief summary string of existing memories.
    """
    if not memories:
        return "(none)"

    summaries = []
    for mem in memories:
        collection = mem.get("_collection", "unknown")
        subject = mem.get("subject", "unknown")
        summaries.append(f"- [{collection}] {subject}")

    return "\n".join(summaries)
