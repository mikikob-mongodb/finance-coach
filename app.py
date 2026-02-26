"""Finance Coach - Streamlit Entry Point.

Personal Finance Coach demonstrating agent memory engineering
using MongoDB Atlas, Voyage AI, and Claude.

O'Reilly AI Superstream Demo: Engineering Context Quality by Architecting Agent Memory
"""

import logging

import streamlit as st

from src.config import DEMO_USER_ID
from ui.chat import get_all_active_memories, initialize_user_session, render_chat_interface
from ui.sidebar import render_sidebar

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Page config must be first Streamlit command
st.set_page_config(
    page_title="Personal Finance Coach",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_header():
    """Render the app header."""
    st.title("💰 Personal Finance Coach")
    st.caption("Engineering Context Quality by Architecting Agent Memory")


def render_user_selector():
    """Render the user selector in the sidebar.

    Returns the new user ID if changed, None otherwise.
    """
    st.sidebar.header("User")

    # Available users
    users = {
        DEMO_USER_ID: "Alex (Demo User)",
        "new_user": "New User (Cold Start)",
    }

    # Current user
    current_user = st.session_state.get("user_id", DEMO_USER_ID)

    # User dropdown
    selected_user = st.sidebar.selectbox(
        "Select User",
        options=list(users.keys()),
        format_func=lambda x: users[x],
        index=list(users.keys()).index(current_user) if current_user in users else 0,
        key="user_selector",
    )

    # Check if user changed
    if selected_user != st.session_state.get("user_id"):
        return selected_user

    return None


def render_reset_button():
    """Render reset button in sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.header("Actions")

    if st.sidebar.button("🔄 Reset Demo", use_container_width=True):
        from src.db import get_database

        db = get_database()
        user_id = st.session_state.get("user_id", DEMO_USER_ID)

        # Delete agent-written memories
        db.preferences.delete_many({"user_id": user_id})
        db.flags.delete_many({"user_id": user_id})

        # Reinitialize session
        initialize_user_session(user_id)

        st.sidebar.success("Demo reset complete!")
        st.rerun()


def main():
    """Main entry point for the Streamlit app."""
    render_header()

    # Initialize session state if needed
    if "user_id" not in st.session_state:
        initialize_user_session(DEMO_USER_ID)

    # User selector (in sidebar)
    new_user = render_user_selector()
    if new_user:
        initialize_user_session(new_user)
        st.rerun()

    # Reset button
    render_reset_button()

    # Main layout: chat on left, memory panel on right
    col_chat, col_memory = st.columns([0.6, 0.4])

    with col_chat:
        render_chat_interface()

    with col_memory:
        # Render sidebar content in main area for better visibility
        render_sidebar()


if __name__ == "__main__":
    main()
