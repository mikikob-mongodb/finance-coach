"""MongoDB connection and collection handles.

Uses PyMongo directly — no ODM.
"""

import logging
from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from src.config import APP_NAME, DATABASE_NAME, MONGODB_URI

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    """Get a cached MongoDB client.

    Uses appname for DevRel attribution tracking.
    The appname is passed via the driver API, not the connection string,
    so users can't accidentally overwrite it when pasting their own Atlas URI.
    """
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI environment variable is not set")

    logger.info("Creating MongoDB client with appname=%s", APP_NAME)
    return MongoClient(MONGODB_URI, appname=APP_NAME)


def get_database() -> Database:
    """Get the Finance Coach database handle.

    Returns:
        PyMongo Database object for finance_coach_db
    """
    client = get_client()
    return client[DATABASE_NAME]
