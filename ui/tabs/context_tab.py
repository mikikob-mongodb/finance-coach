"""Context tab - Assembled prompt + with/without toggle.

Shows the <user_context> block that was injected into the system prompt.
"""

import streamlit as st

from src.agent.memory_formatter import format_memories
from src.prompts.system import build_system_prompt


def estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars per token average)."""
    return len(text) // 4


def render_context_tab(memories: list[dict]):
    """Render the Context tab content.

    Args:
        memories: The memories used in the last response
    """
    st.subheader("📝 Context Window")

    # Add word wrap for code blocks
    st.markdown(
        """
        <style>
        .stCodeBlock pre {
            white-space: pre-wrap !important;
            word-wrap: break-word !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if not memories:
        st.info("No memories in context yet")
        return

    # Format memories
    formatted = format_memories(memories)
    full_prompt = build_system_prompt(formatted)
    empty_prompt = build_system_prompt("")

    # Token counts
    with_tokens = estimate_tokens(full_prompt)
    without_tokens = estimate_tokens(empty_prompt)
    context_tokens = estimate_tokens(formatted)

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Memories", len(memories))
    with col2:
        st.metric("Context Tokens", f"~{context_tokens}")
    with col3:
        st.metric("Total Prompt", f"~{with_tokens}")

    # Toggle between views
    view_mode = st.radio(
        "View mode",
        ["With Memory", "Without Memory", "Context Only"],
        horizontal=True,
        key="context_view_mode",
    )

    st.markdown("---")

    if view_mode == "With Memory":
        st.markdown("**Full System Prompt (with memory context)**")
        st.code(full_prompt, language="markdown")

    elif view_mode == "Without Memory":
        st.markdown("**System Prompt (no memory - cold start)**")
        st.code(empty_prompt, language="markdown")

    else:  # Context Only
        st.markdown("**Formatted Memory Context**")
        st.code(formatted, language="markdown")

    # Memory breakdown
    with st.expander("Memory breakdown", expanded=False):
        prefs = [m for m in memories if m.get("_collection") == "preferences"]
        snaps = [m for m in memories if m.get("_collection") == "snapshots"]
        flags = [m for m in memories if m.get("_collection") == "flags"]

        st.markdown(f"- 🟢 **Preferences:** {len(prefs)}")
        st.markdown(f"- 🔵 **Snapshots:** {len(snaps)}")
        st.markdown(f"- 🟡 **Flags:** {len(flags)}")
