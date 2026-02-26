"""Create vector, text, and TTL indexes.

Vector indexes: 1024 dimensions, cosine similarity
Text indexes: on subject + fact fields
TTL index: on flags.expires_at only

Note: Vector and text (Atlas Search) indexes must be created via
Atlas UI or Atlas Admin API, not PyMongo. This script:
1. Creates the TTL index on flags.expires_at via PyMongo
2. Prints instructions for creating Atlas Search indexes

Usage:
    python scripts/setup_indexes.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    COLLECTION_FLAGS,
    COLLECTION_PREFERENCES,
    COLLECTION_SNAPSHOTS,
)
from src.db import get_database

# Index definitions for Atlas Search (copy to Atlas UI)
VECTOR_INDEX_DEFINITION = """{
  "type": "vectorSearch",
  "definition": {
    "fields": [
      {
        "type": "vector",
        "path": "embedding",
        "numDimensions": 1024,
        "similarity": "cosine"
      },
      {
        "type": "filter",
        "path": "user_id"
      },
      {
        "type": "filter",
        "path": "is_active"
      }
    ]
  }
}"""

TEXT_INDEX_DEFINITION = """{
  "mappings": {
    "dynamic": false,
    "fields": {
      "subject": { "type": "string" },
      "fact": { "type": "string" },
      "user_id": { "type": "token" },
      "is_active": { "type": "boolean" }
    }
  }
}"""


def create_ttl_index(db) -> bool:
    """Create TTL index on flags.expires_at.

    This index auto-deletes flag documents when expires_at passes.
    """
    try:
        # Check if index already exists
        existing = db[COLLECTION_FLAGS].index_information()
        if "expires_at_1" in existing:
            print(f"  TTL index on {COLLECTION_FLAGS}.expires_at already exists")
            return True

        db[COLLECTION_FLAGS].create_index("expires_at", expireAfterSeconds=0)
        print(f"  ✅ Created TTL index on {COLLECTION_FLAGS}.expires_at")
        return True
    except Exception as e:
        print(f"  ❌ Failed to create TTL index: {e}")
        return False


def print_atlas_search_instructions():
    """Print instructions for creating Atlas Search indexes."""
    memory_collections = [COLLECTION_PREFERENCES, COLLECTION_SNAPSHOTS, COLLECTION_FLAGS]

    print("\n" + "=" * 70)
    print("ATLAS SEARCH INDEXES — Manual Setup Required")
    print("=" * 70)
    print("""
Vector and text indexes must be created in the Atlas UI.

Go to: Atlas UI → Your Cluster → Atlas Search → Create Search Index

For EACH of these collections:""")
    for coll in memory_collections:
        print(f"  - {coll}")

    print("""
Create TWO indexes per collection:

1. VECTOR INDEX
   Name: memory_vector_index
   Type: Vector Search
   Definition:""")
    print(VECTOR_INDEX_DEFINITION)

    print("""
2. TEXT INDEX
   Name: memory_text_index
   Type: Search
   Definition:""")
    print(TEXT_INDEX_DEFINITION)

    print("""
Total: 6 indexes (2 per collection × 3 collections)

Alternative: Use the Atlas Admin API or Atlas CLI to create these
indexes programmatically. See:
https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-type/
""")
    print("=" * 70)


def main():
    """Create all required indexes."""
    print("Setting up indexes for Finance Coach...\n")

    db = get_database()

    # Ensure collections exist (seed_data.py creates them, but run this standalone)
    for coll in [COLLECTION_PREFERENCES, COLLECTION_SNAPSHOTS, COLLECTION_FLAGS]:
        if coll not in db.list_collection_names():
            db.create_collection(coll)
            print(f"  Created collection: {coll}")

    # Create TTL index (the only one we can create via PyMongo)
    print("\n1. TTL Index (PyMongo):")
    create_ttl_index(db)

    # Print instructions for Atlas Search indexes
    print_atlas_search_instructions()

    print("\n✅ Index setup complete.")
    print("   - TTL index: created via PyMongo")
    print("   - Vector/Text indexes: create manually in Atlas UI")


if __name__ == "__main__":
    main()
