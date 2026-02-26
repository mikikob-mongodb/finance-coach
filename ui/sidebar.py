"""Memory list + sidebar tabs.

The "Memory Engineering" panel with:
- Memory count summary
- Color-coded memory cards with click-to-select
- Four tabs: 📋 Document, 🔍 Search, 📝 Context, 💾 Data
"""

import streamlit as st

from ui.components.memory_card import MEMORY_STYLES, render_memory_card
from ui.tabs.context_tab import render_context_tab
from ui.tabs.data_tab import render_data_tab
from ui.tabs.document_tab import render_document_tab
from ui.tabs.search_tab import render_search_tab


def get_selected_memory(memories: list[dict], selected_id: str | None) -> dict | None:
    """Get the memory document for the selected ID."""
    if not selected_id or not memories:
        return None

    for mem in memories:
        if str(mem.get("_id")) == selected_id:
            return mem
    return None


def render_memory_summary(memories: list[dict]):
    """Render memory count summary with color badges."""
    prefs = [m for m in memories if m.get("_collection") == "preferences"]
    snaps = [m for m in memories if m.get("_collection") == "snapshots"]
    flags = [m for m in memories if m.get("_collection") == "flags"]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🟢 Prefs", len(prefs))
    with col2:
        st.metric("🔵 Snaps", len(snaps))
    with col3:
        st.metric("🟡 Flags", len(flags))


def render_memory_list(memories: list[dict]):
    """Render the clickable memory list."""
    if not memories:
        st.info("No memories yet. Send a message to create some!")
        return

    # Get current selection
    selected_id = st.session_state.get("selected_memory_id")

    # Render each memory card
    for mem in memories:
        mem_id = str(mem.get("_id"))
        is_selected = mem_id == selected_id
        collection = mem.get("_collection", "unknown")
        style = MEMORY_STYLES.get(collection, {"icon": "⚪", "label": "Unknown"})

        # Compact card display
        with st.container():
            col1, col2 = st.columns([0.85, 0.15])

            with col1:
                subject = mem.get("subject", "Untitled")
                st.markdown(f"{style['icon']} **{subject}**")

            with col2:
                if st.button("👁" if not is_selected else "✓", key=f"sel_{mem_id}"):
                    st.session_state.selected_memory_id = mem_id
                    st.rerun()


def render_sidebar_tabs():
    """Render the four sidebar tabs."""
    # Get session state
    memories = st.session_state.get("all_memories", [])
    selected_id = st.session_state.get("selected_memory_id")
    selected_memory = get_selected_memory(memories, selected_id)
    user_id = st.session_state.get("user_id", "alex_demo")
    baseline = st.session_state.get("baseline", [])
    last_memories = st.session_state.get("last_selected_memories", [])

    # Get last query from chat history
    chat_history = st.session_state.get("chat_history", [])
    last_query = None
    for msg in reversed(chat_history):
        if msg["role"] == "user":
            last_query = msg["content"]
            break

    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Doc", "🔍 Search", "📝 Context", "💾 Data"])

    with tab1:
        render_document_tab(selected_memory)

    with tab2:
        render_search_tab(last_query, last_memories, user_id, baseline)

    with tab3:
        render_context_tab(last_memories)

    with tab4:
        render_data_tab(user_id)


def render_sidebar():
    """Render the memory engineering panel (in main area, not sidebar)."""
    st.header("Memory Engineering")

    # Memory summary
    memories = st.session_state.get("all_memories", [])
    render_memory_summary(memories)

    # Baseline status
    baseline = st.session_state.get("baseline", [])
    if baseline:
        st.success(f"Warm start: {len(baseline)} baseline")
    else:
        st.warning("Cold start: No baseline")

    st.markdown("---")

    # Memory list (compact)
    with st.expander(f"Memories ({len(memories)})", expanded=True):
        render_memory_list(memories)

    st.markdown("---")

    # Tabs
    render_sidebar_tabs()
