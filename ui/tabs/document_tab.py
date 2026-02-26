"""Document tab - Full memory JSON view.

Shows the complete JSON of the selected memory with syntax highlighting.
"""

import json

import streamlit as st

from ui.components.raw_query_toggle import render_mongodb_command


def render_document_tab(selected_memory: dict | None):
    """Render the Document tab content.

    Args:
        selected_memory: The currently selected memory document
    """
    if selected_memory is None:
        st.info("Select a memory from the list to view its full document")
        return

    collection = selected_memory.get("_collection", "unknown")
    mem_id = selected_memory.get("_id")

    st.subheader(f"📋 {selected_memory.get('subject', 'Memory Document')}")

    # Show collection badge
    st.caption(f"Collection: `{collection}`")

    # Format for display (exclude embedding for readability)
    display_doc = {k: v for k, v in selected_memory.items() if k != "embedding"}
    if "embedding" in selected_memory:
        embedding = selected_memory["embedding"]
        display_doc["embedding"] = f"[{len(embedding)} dimensions]"

    # Pretty print JSON
    st.code(json.dumps(display_doc, indent=2, default=str), language="json")

    # Raw query toggle
    if mem_id:
        query = {"_id": {"$oid": str(mem_id)}}
        render_mongodb_command(
            collection=collection,
            operation="findOne",
            query=query,
            key="doc_query",
        )
