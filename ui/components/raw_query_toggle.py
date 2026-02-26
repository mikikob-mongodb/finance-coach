"""'View raw query' toggle component.

Reusable collapsible code block for showing MongoDB queries.
"""

import json

import streamlit as st


def render_raw_query_toggle(
    query: dict | list | str,
    label: str = "View raw query",
    key: str = "raw_query",
    language: str = "javascript",
):
    """Render a collapsible raw query display.

    Args:
        query: The MongoDB query/pipeline to display
        label: Label for the toggle
        key: Unique key for the expander
        language: Syntax highlighting language
    """
    with st.expander(f"🔍 {label}", expanded=False):
        if isinstance(query, (dict, list)):
            formatted = json.dumps(query, indent=2, default=str)
        else:
            formatted = str(query)

        st.code(formatted, language=language)


def render_mongodb_command(
    collection: str,
    operation: str,
    query: dict | list,
    key: str = "mongo_cmd",
):
    """Render a MongoDB command in shell format.

    Args:
        collection: Collection name
        operation: Operation type (find, aggregate, etc.)
        query: The query or pipeline
        key: Unique key
    """
    with st.expander(f"🔍 View MongoDB command", expanded=False):
        if isinstance(query, (dict, list)):
            formatted_query = json.dumps(query, indent=2, default=str)
        else:
            formatted_query = str(query)

        command = f"db.{collection}.{operation}({formatted_query})"
        st.code(command, language="javascript")
