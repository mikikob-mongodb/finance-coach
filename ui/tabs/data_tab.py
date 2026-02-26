"""Data tab - Raw transactions + 'View aggregation' button.

Shows raw transaction data with filtering and the aggregation pipeline
that produces snapshots.
"""

import json
from datetime import datetime

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import DEMO_USER_ID
from src.db import get_database
from ui.components.raw_query_toggle import render_mongodb_command, render_raw_query_toggle


def render_spending_donut_chart(db, user_id: str):
    """Render donut chart showing spending by category."""
    pipeline = [
        {"$match": {"metadata.user_id": user_id}},
        {"$group": {"_id": "$metadata.category", "total": {"$sum": "$amount"}}},
        {"$sort": {"total": -1}},
    ]

    try:
        results = list(db.transactions.aggregate(pipeline))
        if not results:
            return

        categories = [r["_id"] for r in results]
        amounts = [r["total"] for r in results]
        total_spend = sum(amounts)

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=categories,
                    values=amounts,
                    hole=0.5,
                    textinfo="label+percent",
                    textposition="outside",
                    marker=dict(
                        colors=px.colors.qualitative.Set2[: len(categories)]
                    ),
                )
            ]
        )

        fig.update_layout(
            template="plotly_dark",
            height=300,
            margin=dict(t=30, b=30, l=20, r=20),
            showlegend=False,
            annotations=[
                dict(
                    text=f"${total_spend:,.0f}",
                    x=0.5,
                    y=0.5,
                    font_size=18,
                    showarrow=False,
                )
            ],
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Failed to load spending chart: {e}")


def render_priorities_vs_spending_chart(db, user_id: str):
    """Render horizontal bar chart comparing priorities vs spending."""
    # Get user preferences
    try:
        preferences = list(
            db.preferences.find({"user_id": user_id, "is_active": True})
        )
    except Exception:
        preferences = []

    if not preferences:
        st.caption("No priorities set yet — send a message to create some!")
        return

    # Build priority lookup
    priority_map = {}
    for pref in preferences:
        area = pref.get("structured_data", {}).get("area")
        priority = pref.get("structured_data", {}).get("priority", "medium")
        if area:
            priority_map[area.lower()] = priority

    # Get spending by category from snapshot
    try:
        snapshot = db.snapshots.find_one(
            {"user_id": user_id, "is_active": True},
            sort=[("created_at", -1)],
        )
    except Exception:
        snapshot = None

    if not snapshot:
        st.caption("No spending snapshot available")
        return

    top_categories = snapshot.get("structured_data", {}).get("top_categories", {})
    if not top_categories:
        st.caption("No spending data in snapshot")
        return

    # Build chart data - top_categories is a dict like {"rent": 2800, "dining_out": 890}
    categories = []
    amounts = []
    colors = []

    color_map = {"high": "#2ecc71", "medium": "#f1c40f", "low": "#e74c3c"}

    # Normalize category names for matching (e.g., "car_payment" -> "cars", "dining_out" -> "dining")
    category_normalize = {
        "car_payment": "cars",
        "dining_out": "dining",
        "other_fixed": "other",
    }

    for cat_name, amount in top_categories.items():
        # Normalize for priority matching
        normalized = category_normalize.get(cat_name, cat_name).lower()
        priority = priority_map.get(normalized, "low")

        # Format display name
        display_name = cat_name.replace("_", " ").title()

        categories.append(display_name)
        amounts.append(amount)
        colors.append(color_map.get(priority, "#95a5a6"))

    fig = go.Figure(
        data=[
            go.Bar(
                y=categories,
                x=amounts,
                orientation="h",
                marker_color=colors,
                text=[f"${a:,.0f}" for a in amounts],
                textposition="outside",
            )
        ]
    )

    fig.update_layout(
        template="plotly_dark",
        height=250,
        margin=dict(t=10, b=30, l=80, r=40),
        xaxis_title="Spending ($)",
        yaxis=dict(autorange="reversed"),
        showlegend=False,
    )

    # Add legend manually
    st.markdown(
        "🟢 High priority &nbsp;&nbsp; 🟡 Medium &nbsp;&nbsp; 🔴 Low priority",
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, use_container_width=True)


def get_snapshot_aggregation_pipeline(user_id: str) -> list:
    """Get the aggregation pipeline that produces snapshots."""
    return [
        {"$match": {"metadata.user_id": user_id}},
        {
            "$group": {
                "_id": "$metadata.category",
                "total": {"$sum": "$amount"},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"total": -1}},
    ]


def render_data_tab(user_id: str):
    """Render the Data tab content.

    Args:
        user_id: Current user ID
    """
    st.subheader("💾 Transaction Data")

    db = get_database()

    # Charts section (above transaction table)
    st.markdown("**Spending by Category**")
    render_spending_donut_chart(db, user_id)

    st.markdown("**Priorities vs Spending**")
    render_priorities_vs_spending_chart(db, user_id)

    st.markdown("---")

    # Get available months and categories
    try:
        # Get distinct categories
        categories = db.transactions.distinct("metadata.category", {"metadata.user_id": user_id})
        categories = sorted(categories) if categories else []
    except Exception:
        categories = []

    # Filters
    col1, col2 = st.columns(2)

    with col1:
        selected_month = st.selectbox(
            "Month",
            options=["All", "2026-02"],
            index=1,
            key="data_month_filter",
        )

    with col2:
        selected_category = st.selectbox(
            "Category",
            options=["All"] + categories,
            index=0,
            key="data_category_filter",
        )

    # Build query
    query = {"metadata.user_id": user_id}

    if selected_month != "All":
        year, month = selected_month.split("-")
        start = datetime(int(year), int(month), 1)
        if int(month) == 12:
            end = datetime(int(year) + 1, 1, 1)
        else:
            end = datetime(int(year), int(month) + 1, 1)
        query["transaction_date"] = {"$gte": start, "$lt": end}

    if selected_category != "All":
        query["metadata.category"] = selected_category

    # Fetch transactions
    try:
        transactions = list(
            db.transactions.find(query, sort=[("transaction_date", 1)])
        )
    except Exception as e:
        st.error(f"Failed to fetch transactions: {e}")
        transactions = []

    # Summary
    total_amount = sum(t.get("amount", 0) for t in transactions)
    st.markdown(f"**{len(transactions)} transactions** | Total: **\\${total_amount:,.2f}**")

    # Transaction table
    if transactions:
        # Format for display
        display_data = []
        for t in transactions:
            display_data.append({
                "Date": t.get("transaction_date", "").strftime("%Y-%m-%d") if isinstance(t.get("transaction_date"), datetime) else str(t.get("transaction_date", ""))[:10],
                "Category": t.get("metadata", {}).get("category", "N/A"),
                "Merchant": t.get("merchant", "N/A"),
                "Amount": f"${t.get('amount', 0):,.2f}",
                "Description": t.get("description", ""),
            })

        st.dataframe(display_data, use_container_width=True, hide_index=True)
    else:
        st.info("No transactions found")

    # View aggregation button
    st.markdown("---")
    st.markdown("**Snapshot Aggregation**")

    if st.button("📊 View Aggregation Pipeline", key="view_aggregation"):
        pipeline = get_snapshot_aggregation_pipeline(user_id)

        st.markdown("This pipeline computes category totals for snapshots:")
        st.code(json.dumps(pipeline, indent=2), language="json")

        # Run the aggregation
        try:
            results = list(db.transactions.aggregate(pipeline))
            st.markdown("**Results:**")
            for r in results:
                st.markdown(f"- **{r['_id']}**: \\${r['total']:,.2f} ({r['count']} txns)")
        except Exception as e:
            st.error(f"Aggregation failed: {e}")

    # Raw query toggle
    render_mongodb_command(
        collection="transactions",
        operation="find",
        query=query,
        key="data_query",
    )
