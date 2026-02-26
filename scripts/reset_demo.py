"""Reset to pre-loaded state between demo runs.

1. Delete all agent-written memories (preferences, flags) for alex_demo
2. Keep the pre-loaded snapshot and transactions
3. Print confirmation

Usage:
    python scripts/reset_demo.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DEMO_USER_ID
from src.db import get_database


def reset_demo(user_id: str = DEMO_USER_ID):
    """Reset to pre-loaded state. Keep snapshot + transactions."""
    db = get_database()

    # Delete agent-written memories
    prefs_deleted = db.preferences.delete_many({"user_id": user_id})
    flags_deleted = db.flags.delete_many({"user_id": user_id})

    print(f"✅ Reset complete for user '{user_id}':")
    print(f"   - Deleted {prefs_deleted.deleted_count} preferences")
    print(f"   - Deleted {flags_deleted.deleted_count} flags")
    print("   - Kept snapshots and transactions")


def main():
    """Run reset from command line."""
    reset_demo()


if __name__ == "__main__":
    main()
