"""Configuration and constants for the Finance Coach application.

All constants from technical-reference.md Section 1.
"""

import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# Environment Variables
# =============================================================================

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "finance_coach_db")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# =============================================================================
# Database Constants
# =============================================================================

DATABASE_NAME = MONGODB_DATABASE
DEMO_USER_ID = "alex_demo"
APP_NAME = "devrel-presentation-python-financial-coach-oreilly"

# =============================================================================
# Collections
# =============================================================================

COLLECTION_PREFERENCES = "preferences"
COLLECTION_SNAPSHOTS = "snapshots"
COLLECTION_FLAGS = "flags"
COLLECTION_TRANSACTIONS = "transactions"

# =============================================================================
# Voyage AI
# =============================================================================

VOYAGE_MODEL = "voyage-3-large"
VOYAGE_DIMENSIONS = 1024

# =============================================================================
# Claude
# =============================================================================

CLAUDE_MODEL = "claude-sonnet-4-20250514"

# =============================================================================
# Search
# =============================================================================

HYBRID_SEARCH_LIMIT = 5
VECTOR_NUM_CANDIDATES = 50
BASELINE_PREFERENCES_LIMIT = 5

# =============================================================================
# Memory
# =============================================================================

FLAG_DEFAULT_EXPIRY_DAYS = 30
