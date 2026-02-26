"""Search tab - Pipeline + scores + 'Run search only' button.

Shows the $rankFusion pipeline that was executed and per-result scores.
"""

import json

import streamlit as st

from src.agent.select_memories import select_all_memories
from src.config import HYBRID_SEARCH_LIMIT, VECTOR_NUM_CANDIDATES
from src.db import get_database
from src.embeddings import embed_query
from ui.components.raw_query_toggle import render_raw_query_toggle


def get_hybrid_search_pipeline(query_embedding: list[float], user_query: str, user_id: str) -> list:
    """Build the $rankFusion hybrid search pipeline for display."""
    return [
        {
            "$rankFusion": {
                "input": {
                    "pipelines": {
                        "vector": [
                            {
                                "$vectorSearch": {
                                    "index": "memory_vector_index",
                                    "path": "embedding",
                                    "queryVector": f"[{len(query_embedding)} dimensions]",
                                    "numCandidates": VECTOR_NUM_CANDIDATES,
                                    "limit": HYBRID_SEARCH_LIMIT,
                                    "filter": {
                                        "user_id": user_id,
                                        "is_active": True,
                                    },
                                }
                            }
                        ],
                        "text": [
                            {
                                "$search": {
                                    "index": "memory_text_index",
                                    "text": {
                                        "query": user_query,
                                        "path": ["subject", "fact"],
                                    },
                                }
                            },
                            {
                                "$match": {
                                    "user_id": user_id,
                                    "is_active": True,
                                }
                            },
                            {"$limit": HYBRID_SEARCH_LIMIT},
                        ],
                    }
                }
            }
        }
    ]


def render_search_tab(
    last_query: str | None,
    last_memories: list[dict],
    user_id: str,
    baseline: list[dict],
):
    """Render the Search tab content.

    Args:
        last_query: The last user query
        last_memories: Memories returned from last search
        user_id: Current user ID
        baseline: Baseline memories
    """
    st.subheader("🔍 Memory Search")

    if not last_query:
        st.info("Send a message to see search results")
        return

    st.markdown(f"**Last query:** {last_query}")

    # Results summary
    baseline_count = len(baseline)
    search_count = len(last_memories) - baseline_count
    st.markdown(f"**Results:** {len(last_memories)} total ({baseline_count} baseline + {search_count} from search)")

    # Show results with collection badges
    if last_memories:
        st.markdown("---")
        for i, mem in enumerate(last_memories):
            coll = mem.get("_collection", "unknown")
            icon = {"preferences": "🟢", "snapshots": "🔵", "flags": "🟡"}.get(coll, "⚪")
            subject = mem.get("subject", "N/A")
            source = "baseline" if i < baseline_count else "search"
            st.markdown(f"{icon} **{subject}** `{coll}` _{source}_")

    # Run search only button
    st.markdown("---")
    st.markdown("**Test Search**")

    test_query = st.text_input("Enter a test query:", key="search_test_query")

    if st.button("🔎 Run Search Only", key="run_search_only"):
        if test_query:
            with st.spinner("Searching..."):
                try:
                    db = get_database()
                    query_emb = embed_query(test_query)
                    results = select_all_memories(db, query_emb, test_query, user_id, baseline)

                    st.success(f"Found {len(results)} memories")
                    for mem in results:
                        coll = mem.get("_collection", "unknown")
                        icon = {"preferences": "🟢", "snapshots": "🔵", "flags": "🟡"}.get(coll, "⚪")
                        st.markdown(f"{icon} {mem.get('subject', 'N/A')}")

                except Exception as e:
                    st.error(f"Search failed: {e}")
        else:
            st.warning("Enter a query first")

    # Show pipeline
    st.markdown("---")
    if last_query:
        try:
            query_emb = embed_query(last_query)
            pipeline = get_hybrid_search_pipeline(query_emb, last_query, user_id)
            render_raw_query_toggle(
                pipeline,
                label="View $rankFusion pipeline",
                key="search_pipeline",
            )
        except Exception:
            st.caption("Pipeline preview unavailable")
