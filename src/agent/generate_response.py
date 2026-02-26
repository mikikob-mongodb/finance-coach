"""INJECT + LLM - Generate response with memory context.

Format memories as structured context block, assemble prompt,
call Claude. Returns response text.

From technical-reference.md Section 6.
"""

import logging

import anthropic

from src.agent.memory_formatter import format_memories
from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from src.prompts.system import build_system_prompt

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


def generate_response(
    memories: list[dict],
    user_message: str,
    chat_history: list[dict],
    max_tokens: int = 1024,
) -> str:
    """Generate a response using Claude with memory context.

    This is the INJECT step: memories are formatted and injected into
    the system prompt, then Claude generates a contextual response.

    Args:
        memories: List of memory documents (from select_all_memories)
        user_message: The current user message
        chat_history: Previous messages in the conversation
        max_tokens: Maximum tokens in the response

    Returns:
        The assistant's response text.

    Raises:
        anthropic.APIError: If the API call fails
        ValueError: If ANTHROPIC_API_KEY is not set
    """
    client = _get_client()

    # Format memories and build system prompt
    formatted = format_memories(memories)
    system_prompt = build_system_prompt(formatted)

    # Build messages array
    messages = []

    # Add chat history (alternating user/assistant)
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    logger.debug(
        "Generating response with %d memories, %d history messages",
        len(memories),
        len(chat_history),
    )

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )

        # Extract text content
        result = response.content[0].text
        logger.debug("Generated response: %d chars", len(result))

        return result

    except Exception as e:
        logger.error("Failed to generate response: %s", e)
        raise
