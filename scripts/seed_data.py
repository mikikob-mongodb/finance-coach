"""
Seed data for Finance Coach demo.

Creates:
- transactions collection (time series, ~47 documents)
- snapshots collection (1 pre-loaded snapshot with embedding)

Idempotent — drops and recreates on each run.

Usage:
    python scripts/seed_data.py
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MONGODB_URI = os.environ["MONGODB_URI"]
DATABASE_NAME = os.environ.get("MONGODB_DATABASE", "finance_coach_db")
APP_NAME = "devrel-presentation-python-financial-coach-oreilly"
USER_ID = "alex_demo"


def utc(date_str: str) -> datetime:
    """Parse ISO date string to UTC datetime."""
    return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Transaction data
# ---------------------------------------------------------------------------

TRANSACTIONS = [
    # === RENT ===
    {"transaction_date": utc("2026-02-01T00:00:00"), "metadata": {"user_id": USER_ID, "category": "rent"}, "amount": 2800.00, "merchant": "Bay Ridge Apartments", "description": "February rent"},

    # === CAR PAYMENTS & INSURANCE ===
    {"transaction_date": utc("2026-02-01T00:00:00"), "metadata": {"user_id": USER_ID, "category": "car_payment"}, "amount": 1245.00, "merchant": "Toyota Financial", "description": "Monthly car payment - 2024 RAV4"},
    {"transaction_date": utc("2026-02-15T00:00:00"), "metadata": {"user_id": USER_ID, "category": "car_insurance"}, "amount": 285.00, "merchant": "GEICO", "description": "Monthly auto insurance"},

    # === STUDENT LOANS ===
    {"transaction_date": utc("2026-02-05T00:00:00"), "metadata": {"user_id": USER_ID, "category": "student_loans"}, "amount": 650.00, "merchant": "Nelnet", "description": "Student loan payment"},

    # === UTILITIES & FIXED ===
    {"transaction_date": utc("2026-02-01T00:00:00"), "metadata": {"user_id": USER_ID, "category": "utilities"}, "amount": 185.00, "merchant": "PG&E", "description": "Electric and gas"},
    {"transaction_date": utc("2026-02-01T00:00:00"), "metadata": {"user_id": USER_ID, "category": "utilities"}, "amount": 95.00, "merchant": "EBMUD", "description": "Water"},
    {"transaction_date": utc("2026-02-01T00:00:00"), "metadata": {"user_id": USER_ID, "category": "utilities"}, "amount": 70.00, "merchant": "Comcast", "description": "Internet"},
    {"transaction_date": utc("2026-02-03T00:00:00"), "metadata": {"user_id": USER_ID, "category": "phone"}, "amount": 110.00, "merchant": "T-Mobile", "description": "Phone plan"},
    {"transaction_date": utc("2026-02-01T00:00:00"), "metadata": {"user_id": USER_ID, "category": "subscriptions"}, "amount": 15.99, "merchant": "Netflix", "description": "Streaming"},
    {"transaction_date": utc("2026-02-01T00:00:00"), "metadata": {"user_id": USER_ID, "category": "subscriptions"}, "amount": 10.99, "merchant": "Spotify", "description": "Music"},
    {"transaction_date": utc("2026-02-01T00:00:00"), "metadata": {"user_id": USER_ID, "category": "subscriptions"}, "amount": 22.99, "merchant": "NYT", "description": "News subscription"},
    {"transaction_date": utc("2026-02-01T00:00:00"), "metadata": {"user_id": USER_ID, "category": "subscriptions"}, "amount": 24.99, "merchant": "Adobe", "description": "Creative Cloud"},
    {"transaction_date": utc("2026-02-01T00:00:00"), "metadata": {"user_id": USER_ID, "category": "health_insurance"}, "amount": 245.00, "merchant": "Kaiser Permanente", "description": "Health insurance premium"},
    {"transaction_date": utc("2026-02-10T00:00:00"), "metadata": {"user_id": USER_ID, "category": "other_fixed"}, "amount": 1000.00, "merchant": "Various", "description": "Miscellaneous fixed (laundry, parking, pet care)"},

    # === INVESTMENTS ===
    {"transaction_date": utc("2026-02-01T00:00:00"), "metadata": {"user_id": USER_ID, "category": "investments"}, "amount": 500.00, "merchant": "Vanguard", "description": "401k contribution"},
    {"transaction_date": utc("2026-02-01T00:00:00"), "metadata": {"user_id": USER_ID, "category": "investments"}, "amount": 523.00, "merchant": "Wealthfront", "description": "Automated investment"},

    # === DINING OUT (18 transactions, ~$890 total) ===
    {"transaction_date": utc("2026-02-01T12:30:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 22.50, "merchant": "Tartine Bakery", "description": "Lunch"},
    {"transaction_date": utc("2026-02-02T19:00:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 68.00, "merchant": "Burma Superstar", "description": "Dinner with friends"},
    {"transaction_date": utc("2026-02-04T12:15:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 18.75, "merchant": "Souvla", "description": "Quick lunch"},
    {"transaction_date": utc("2026-02-06T19:30:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 47.50, "merchant": "Nopa", "description": "Dinner"},
    {"transaction_date": utc("2026-02-07T20:00:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 82.00, "merchant": "State Bird Provisions", "description": "Date night"},
    {"transaction_date": utc("2026-02-09T13:00:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 35.00, "merchant": "Prubechu", "description": "Brunch"},
    {"transaction_date": utc("2026-02-10T12:00:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 16.50, "merchant": "Marufuku Ramen", "description": "Lunch"},
    {"transaction_date": utc("2026-02-12T19:00:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 55.00, "merchant": "Che Fico", "description": "Dinner"},
    {"transaction_date": utc("2026-02-14T20:30:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 120.00, "merchant": "Lazy Bear", "description": "Valentine's dinner"},
    {"transaction_date": utc("2026-02-15T12:30:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 24.00, "merchant": "El Farolito", "description": "Lunch"},
    {"transaction_date": utc("2026-02-17T19:00:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 42.00, "merchant": "Dumpling Home", "description": "Dinner with coworkers"},
    {"transaction_date": utc("2026-02-18T12:00:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 19.50, "merchant": "Deli Board", "description": "Lunch"},
    {"transaction_date": utc("2026-02-20T19:30:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 58.00, "merchant": "Nopalito", "description": "Dinner"},
    {"transaction_date": utc("2026-02-21T11:00:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 38.00, "merchant": "Zazie", "description": "Weekend brunch"},
    {"transaction_date": utc("2026-02-23T19:00:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 65.00, "merchant": "Rich Table", "description": "Dinner"},
    {"transaction_date": utc("2026-02-24T12:30:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 52.00, "merchant": "Mister Jiu's", "description": "Business lunch"},
    {"transaction_date": utc("2026-02-25T18:00:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 78.25, "merchant": "Foreign Cinema", "description": "Dinner with friends"},
    {"transaction_date": utc("2026-02-27T12:00:00"), "metadata": {"user_id": USER_ID, "category": "dining_out"}, "amount": 48.00, "merchant": "b. patisserie", "description": "Brunch"},

    # === GROCERIES (8 transactions, $650 total) ===
    {"transaction_date": utc("2026-02-02T10:00:00"), "metadata": {"user_id": USER_ID, "category": "groceries"}, "amount": 95.00, "merchant": "Trader Joe's", "description": "Weekly groceries"},
    {"transaction_date": utc("2026-02-05T17:00:00"), "metadata": {"user_id": USER_ID, "category": "groceries"}, "amount": 42.00, "merchant": "Rainbow Grocery", "description": "Specialty items"},
    {"transaction_date": utc("2026-02-09T10:30:00"), "metadata": {"user_id": USER_ID, "category": "groceries"}, "amount": 88.00, "merchant": "Trader Joe's", "description": "Weekly groceries"},
    {"transaction_date": utc("2026-02-12T18:00:00"), "metadata": {"user_id": USER_ID, "category": "groceries"}, "amount": 35.00, "merchant": "Bi-Rite Market", "description": "Quick stop"},
    {"transaction_date": utc("2026-02-16T10:00:00"), "metadata": {"user_id": USER_ID, "category": "groceries"}, "amount": 110.00, "merchant": "Whole Foods", "description": "Weekly groceries"},
    {"transaction_date": utc("2026-02-20T17:30:00"), "metadata": {"user_id": USER_ID, "category": "groceries"}, "amount": 78.00, "merchant": "Trader Joe's", "description": "Weekly groceries"},
    {"transaction_date": utc("2026-02-23T10:00:00"), "metadata": {"user_id": USER_ID, "category": "groceries"}, "amount": 92.00, "merchant": "Trader Joe's", "description": "Weekly groceries"},
    {"transaction_date": utc("2026-02-27T17:00:00"), "metadata": {"user_id": USER_ID, "category": "groceries"}, "amount": 110.00, "merchant": "Whole Foods", "description": "Weekly groceries + hosting"},

    # === ENTERTAINMENT (4 transactions, $164 total) ===
    {"transaction_date": utc("2026-02-08T20:00:00"), "metadata": {"user_id": USER_ID, "category": "entertainment"}, "amount": 32.00, "merchant": "AMC Metreon", "description": "Movie tickets x2"},
    {"transaction_date": utc("2026-02-15T15:00:00"), "metadata": {"user_id": USER_ID, "category": "entertainment"}, "amount": 45.00, "merchant": "The Chapel", "description": "Live music"},
    {"transaction_date": utc("2026-02-22T14:00:00"), "metadata": {"user_id": USER_ID, "category": "entertainment"}, "amount": 62.00, "merchant": "Chase Center", "description": "Warriors game ticket"},
    {"transaction_date": utc("2026-02-26T19:00:00"), "metadata": {"user_id": USER_ID, "category": "entertainment"}, "amount": 25.00, "merchant": "Alamo Drafthouse", "description": "Movie + snacks"},

    # === SHOPPING (3 transactions, $125 total) ===
    {"transaction_date": utc("2026-02-11T14:00:00"), "metadata": {"user_id": USER_ID, "category": "shopping"}, "amount": 45.00, "merchant": "Target", "description": "Household items"},
    {"transaction_date": utc("2026-02-19T12:00:00"), "metadata": {"user_id": USER_ID, "category": "shopping"}, "amount": 35.00, "merchant": "Amazon", "description": "Kitchen supplies"},
    {"transaction_date": utc("2026-02-25T16:00:00"), "metadata": {"user_id": USER_ID, "category": "shopping"}, "amount": 45.00, "merchant": "REI", "description": "Water bottle + socks"},

    # === TRANSPORTATION (2 transactions, $75 total) ===
    {"transaction_date": utc("2026-02-08T22:00:00"), "metadata": {"user_id": USER_ID, "category": "transportation"}, "amount": 35.00, "merchant": "Uber", "description": "Ride home from concert"},
    {"transaction_date": utc("2026-02-14T22:30:00"), "metadata": {"user_id": USER_ID, "category": "transportation"}, "amount": 40.00, "merchant": "Uber", "description": "Ride home from dinner"},

    # === FITNESS: $0 — conspicuous absence ===
    # === TRAVEL: $0 — conspicuous absence ===
]


# ---------------------------------------------------------------------------
# Compute snapshot from transactions
# ---------------------------------------------------------------------------

def compute_snapshot(transactions: list[dict]) -> dict:
    """Compute a spending snapshot from raw transactions.

    This mirrors the aggregation pipeline the Data tab would show.
    Returns the snapshot document (without embedding — added later).
    """
    fixed_categories = {
        "rent", "car_payment", "car_insurance", "student_loans",
        "utilities", "phone", "subscriptions", "health_insurance", "other_fixed",
    }
    investment_categories = {"investments"}

    fixed_total = 0.0
    investment_total = 0.0
    discretionary_total = 0.0
    category_totals: dict[str, float] = {}
    tx_count = 0

    for tx in transactions:
        cat = tx["metadata"]["category"]
        amt = tx["amount"]
        tx_count += 1

        category_totals[cat] = category_totals.get(cat, 0) + amt

        if cat in fixed_categories:
            fixed_total += amt
        elif cat in investment_categories:
            investment_total += amt
        else:
            discretionary_total += amt

    # Top categories by spend (top 5)
    sorted_cats = sorted(category_totals.items(), key=lambda x: -x[1])
    top_categories = {k: round(v, 2) for k, v in sorted_cats[:5]}

    # Take-home income (~$120K gross → ~$9,757/mo after tax + benefits)
    income = 9757.0

    fact = (
        f"February 2026: Monthly take-home income ${income:,.0f}. "
        f"Fixed costs at ${fixed_total:,.0f} ({fixed_total/income*100:.0f}% of take-home). "
        f"Biggest driver: car payments at $1,245/month (8% interest, 48 months remaining). "
        f"Dining out: ${category_totals.get('dining_out', 0):,.0f} across "
        f"{sum(1 for t in transactions if t['metadata']['category'] == 'dining_out')} transactions. "
        f"Groceries: ${category_totals.get('groceries', 0):,.0f}. "
        f"Fitness spending: $0 despite gym membership cancellation in January. "
        f"Travel: $0 this month. "
        f"Investments: ${investment_total:,.0f} ({investment_total/income*100:.1f}% of take-home)."
    )

    return {
        "user_id": USER_ID,
        "subject": "February 2026 Spending Summary",
        "fact": fact,
        "embedding": [],  # placeholder — filled by embed_snapshot()
        "structured_data": {
            "as_of_date": "2026-02",
            "income": income,
            "fixed_expenses": round(fixed_total, 2),
            "discretionary": round(discretionary_total, 2),
            "investments": round(investment_total, 2),
            "top_categories": top_categories,
        },
        "citations": [{"type": "computed", "source": "transactions", "query": "2026-02", "count": tx_count}],
        "is_active": True,
        "created_at": utc("2026-03-01T00:00:00"),
        "supersedes": None,
    }


def embed_snapshot(snapshot: dict) -> dict:
    """Add Voyage AI embedding to the snapshot's fact field."""
    import voyageai

    client = voyageai.Client()
    result = client.embed([snapshot["fact"]], model="voyage-3-large", input_type="document")
    snapshot["embedding"] = result.embeddings[0]
    return snapshot


# ---------------------------------------------------------------------------
# Seed script
# ---------------------------------------------------------------------------

def seed(skip_embedding: bool = False):
    """Seed the database. Idempotent — drops and recreates."""
    client = MongoClient(MONGODB_URI, appname=APP_NAME)
    db = client[DATABASE_NAME]

    # --- Transactions (time series) ---
    if "transactions" in db.list_collection_names():
        db.drop_collection("transactions")
        print("Dropped existing transactions collection")

    db.create_collection("transactions", timeseries={
        "timeField": "transaction_date",
        "metaField": "metadata",
        "granularity": "hours",
    })
    db.transactions.insert_many(TRANSACTIONS)
    print(f"Inserted {len(TRANSACTIONS)} transactions")

    # --- Verify totals ---
    pipeline = [
        {"$match": {"metadata.user_id": USER_ID}},
        {"$group": {"_id": "$metadata.category", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        {"$sort": {"total": -1}},
    ]
    print("\nTransaction summary:")
    grand_total = 0.0
    for row in db.transactions.aggregate(pipeline):
        print(f"  {row['_id']:20s}  {row['count']:2d} txns  ${row['total']:>10,.2f}")
        grand_total += row["total"]
    print(f"  {'TOTAL':20s}  {len(TRANSACTIONS):2d} txns  ${grand_total:>10,.2f}")

    # --- Snapshot ---
    db.snapshots.delete_many({"user_id": USER_ID})
    snapshot = compute_snapshot(TRANSACTIONS)

    if not skip_embedding:
        print("\nEmbedding snapshot fact via Voyage AI...")
        snapshot = embed_snapshot(snapshot)
        print(f"  Embedding dimensions: {len(snapshot['embedding'])}")
    else:
        print("\nSkipping embedding (--skip-embedding flag)")
        snapshot["embedding"] = [0.0] * 1024  # placeholder

    db.snapshots.insert_one(snapshot)
    print(f"\nInserted snapshot: {snapshot['subject']}")
    print(f"  income:          ${snapshot['structured_data']['income']:,.0f}")
    print(f"  fixed_expenses:  ${snapshot['structured_data']['fixed_expenses']:,.2f}")
    print(f"  discretionary:   ${snapshot['structured_data']['discretionary']:,.2f}")
    print(f"  investments:     ${snapshot['structured_data']['investments']:,.2f}")
    print(f"  top_categories:  {list(snapshot['structured_data']['top_categories'].keys())}")

    # --- Ensure preferences and flags collections exist (empty) ---
    for coll in ["preferences", "flags"]:
        if coll not in db.list_collection_names():
            db.create_collection(coll)
            print(f"Created empty {coll} collection")

    print("\nSeed complete.")
    client.close()


if __name__ == "__main__":
    skip = "--skip-embedding" in sys.argv
    seed(skip_embedding=skip)