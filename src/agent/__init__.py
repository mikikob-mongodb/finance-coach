"""Agent module - The four functions that make up the memory-enabled agent.

Session Start → load_baseline(user_id)
                     │
                     ▼ (per message)
               select_memories() → generate_response() → write_memories()
"""

from src.agent.generate_response import generate_response
from src.agent.load_baseline import load_baseline
from src.agent.memory_formatter import format_memories, format_memory_summaries
from src.agent.select_memories import (
    select_all_memories,
    select_memories,
    select_memories_vector_only,
)
from src.agent.write_memories import write_memories

__all__ = [
    "load_baseline",
    "select_memories",
    "select_memories_vector_only",
    "select_all_memories",
    "generate_response",
    "write_memories",
    "format_memories",
    "format_memory_summaries",
]
