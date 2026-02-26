"""Main chat interface component.

Handles:
- Displaying chat history with st.chat_message
- Processing new user messages through the agent pipeline
- Updating session state after each message
"""

import logging

import streamlit as st

from src.agent.generate_response import generate_response
from src.agent.load_baseline import load_baseline
from src.agent.select_memories import select_all_memories
from src.agent.write_memories import write_memories
from src.db import get_database
from src.embeddings import embed_query

logger = logging.getLogger(__name__)


def escape_dollars(text: str) -> str:
    """Escape dollar signs for Streamlit markdown display.

    Streamlit's markdown renderer interprets $ as LaTeX math delimiters.
    This escapes them so dollar amounts like $890 display correctly.
    """
    return text.replace("$", "\\$")


def display_chat_history():
    """Display all messages in the chat history."""
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            # Escape dollars in display to prevent LaTeX interpretation
            display_text = escape_dollars(message["content"])
            st.markdown(display_text)


def process_user_message(user_message: str):
    """Process a user message through the full agent pipeline.

    Pipeline: SELECT → GENERATE → WRITE

    Args:
        user_message: The user's input message
    """
    db = get_database()
    user_id = st.session_state.user_id
    baseline = st.session_state.baseline

    # Display user message immediately
    with st.chat_message("user"):
        st.markdown(user_message)

    # Add to history
    st.session_state.chat_history.append({"role": "user", "content": user_message})

    # SELECT: Query-driven memory selection
    with st.spinner("Thinking..."):
        try:
            query_embedding = embed_query(user_message)
            memories = select_all_memories(
                db, query_embedding, user_message, user_id, baseline
            )
            st.session_state.last_selected_memories = memories
            logger.info("Selected %d memories for response", len(memories))
        except Exception as e:
            logger.error("Failed to select memories: %s", e)
            memories = baseline

        # GENERATE: Get response from Claude
        try:
            response = generate_response(
                memories, user_message, st.session_state.chat_history[:-1]
            )
        except Exception as e:
            logger.error("Failed to generate response: %s", e)
            response = f"I encountered an error: {e}"

    # Display assistant response (escape dollars for display only)
    with st.chat_message("assistant"):
        st.markdown(escape_dollars(response))

    # Add to history
    st.session_state.chat_history.append({"role": "assistant", "content": response})

    # WRITE: Extract and store new memories
    try:
        new_memories = write_memories(
            user_message, response, user_id, memories, db
        )
        if new_memories:
            logger.info("Created %d new memories", len(new_memories))
            # Reload baseline to include new memories
            st.session_state.baseline = load_baseline(db, user_id)
            st.session_state.all_memories = get_all_active_memories(db, user_id)
    except Exception as e:
        logger.error("Failed to write memories: %s", e)


def get_all_active_memories(db, user_id: str) -> list[dict]:
    """Get all active memories for a user across all collections."""
    memories = []
    for coll_name in ["preferences", "snapshots", "flags"]:
        docs = list(
            db[coll_name].find(
                {"user_id": user_id, "is_active": True},
                sort=[("created_at", -1)],
            )
        )
        for d in docs:
            d["_collection"] = coll_name
        memories.extend(docs)
    return memories


def initialize_user_session(user_id: str):
    """Initialize or reset session state for a user.

    Called on app start and when switching users.
    """
    db = get_database()

    st.session_state.user_id = user_id
    st.session_state.chat_history = []
    st.session_state.baseline = load_baseline(db, user_id)
    st.session_state.all_memories = get_all_active_memories(db, user_id)
    st.session_state.last_selected_memories = []

    logger.info(
        "Initialized session for user %s with %d baseline memories",
        user_id,
        len(st.session_state.baseline),
    )


def render_chat_interface():
    """Render the main chat interface."""
    # Display existing chat history
    display_chat_history()

    # Chat input
    if prompt := st.chat_input("Ask about your finances..."):
        process_user_message(prompt)
        st.rerun()
