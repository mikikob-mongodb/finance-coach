"""Single memory display component (colored by type).

Color coding:
- 🟢 preferences (semantic memory)
- 🔵 snapshots (episodic memory)
- 🟡 flags (working memory)
"""

from datetime import datetime, timezone

import streamlit as st

# Color and icon mapping by collection type
MEMORY_STYLES = {
    "preferences": {"icon": "🟢", "color": "#22c55e", "label": "Preference"},
    "snapshots": {"icon": "🔵", "color": "#3b82f6", "label": "Snapshot"},
    "flags": {"icon": "🟡", "color": "#eab308", "label": "Flag"},
}


def format_relative_time(dt: datetime) -> str:
    """Format a datetime as relative time (e.g., '2 hours ago')."""
    if dt is None:
        return "unknown"

    # Ensure timezone aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 0:
        # Future time (for expires_at)
        seconds = abs(seconds)
        if seconds < 60:
            return f"in {int(seconds)}s"
        elif seconds < 3600:
            return f"in {int(seconds / 60)}m"
        elif seconds < 86400:
            return f"in {int(seconds / 3600)}h"
        else:
            return f"in {int(seconds / 86400)}d"
    else:
        if seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h ago"
        else:
            return f"{int(seconds / 86400)}d ago"


def render_memory_card(
    memory: dict,
    selected: bool = False,
    on_click_key: str | None = None,
) -> bool:
    """Render a single memory card.

    Args:
        memory: The memory document with _collection field
        selected: Whether this memory is currently selected
        on_click_key: Unique key for the click button

    Returns:
        True if this card was clicked
    """
    collection = memory.get("_collection", "unknown")
    style = MEMORY_STYLES.get(collection, {"icon": "⚪", "color": "#888", "label": "Unknown"})

    subject = memory.get("subject", "Untitled")
    fact = memory.get("fact", "")
    created_at = memory.get("created_at")
    expires_at = memory.get("expires_at")

    # Container styling
    border_color = style["color"] if selected else "#333"
    bg_color = f"{style['color']}15" if selected else "transparent"

    # Build card
    with st.container():
        # Use custom CSS for card appearance
        card_style = f"""
        <div style="
            border: 2px solid {border_color};
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 8px;
            background-color: {bg_color};
        ">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span style="font-size: 1.2em;">{style['icon']}</span>
                <span style="font-weight: 600; color: {style['color']};">{style['label']}</span>
                <span style="color: #888; font-size: 0.8em; margin-left: auto;">
                    {format_relative_time(created_at)}
                </span>
            </div>
            <div style="font-weight: 500; margin-bottom: 4px;">{subject}</div>
            <div style="color: #aaa; font-size: 0.85em; line-height: 1.4;">
                {fact[:150]}{'...' if len(fact) > 150 else ''}
            </div>
        """

        # Add expires_at for flags
        if collection == "flags" and expires_at:
            card_style += f"""
            <div style="color: #eab308; font-size: 0.8em; margin-top: 8px;">
                ⏰ Expires {format_relative_time(expires_at)}
            </div>
            """

        card_style += "</div>"
        st.markdown(card_style, unsafe_allow_html=True)

        # Click button
        if on_click_key:
            clicked = st.button(
                "Select" if not selected else "Selected ✓",
                key=on_click_key,
                use_container_width=True,
                type="primary" if selected else "secondary",
            )
            return clicked

    return False


def render_memory_list(memories: list[dict], selected_id: str | None = None) -> str | None:
    """Render a list of memory cards.

    Args:
        memories: List of memory documents
        selected_id: ID of the currently selected memory (as string)

    Returns:
        ID of newly selected memory (as string), or None
    """
    if not memories:
        st.info("No memories yet")
        return None

    newly_selected = None

    for i, mem in enumerate(memories):
        mem_id = str(mem.get("_id", i))
        is_selected = mem_id == selected_id

        clicked = render_memory_card(
            mem,
            selected=is_selected,
            on_click_key=f"mem_card_{mem_id}",
        )

        if clicked:
            newly_selected = mem_id

    return newly_selected
