"""Voyage AI embedding calls.

Model: voyage-3-large
Dimensions: 1024
Asymmetric input types:
- input_type="document" when embedding memories for storage
- input_type="query" when embedding user queries for search

From technical-reference.md Section 5.
"""

import logging

import voyageai

from src.config import VOYAGE_API_KEY, VOYAGE_MODEL

logger = logging.getLogger(__name__)

# Initialize client (uses VOYAGE_API_KEY env var if not passed explicitly)
_client: voyageai.Client | None = None


def _get_client() -> voyageai.Client:
    """Get or create the Voyage AI client."""
    global _client
    if _client is None:
        if not VOYAGE_API_KEY:
            raise ValueError("VOYAGE_API_KEY environment variable is not set")
        _client = voyageai.Client(api_key=VOYAGE_API_KEY)
    return _client


def embed_document(text: str) -> list[float]:
    """Embed a memory fact for storage.

    Uses input_type="document" for asymmetric retrieval optimization.
    The embedding is optimized for being retrieved by queries.

    Args:
        text: The fact field content to embed

    Returns:
        1024-dimensional embedding vector

    Raises:
        voyageai.error.RateLimitError: If rate limited
        voyageai.error.AuthenticationError: If API key is invalid
        ValueError: If VOYAGE_API_KEY is not set
    """
    client = _get_client()
    try:
        result = client.embed([text], model=VOYAGE_MODEL, input_type="document")
        embedding = result.embeddings[0]
        logger.debug("Embedded document: %d dimensions", len(embedding))
        return embedding
    except Exception as e:
        logger.error("Failed to embed document: %s", e)
        raise


def embed_query(text: str) -> list[float]:
    """Embed a user query for search.

    Uses input_type="query" for asymmetric retrieval optimization.
    The embedding is optimized for finding relevant documents.

    Args:
        text: The user query to embed

    Returns:
        1024-dimensional embedding vector

    Raises:
        voyageai.error.RateLimitError: If rate limited
        voyageai.error.AuthenticationError: If API key is invalid
        ValueError: If VOYAGE_API_KEY is not set
    """
    client = _get_client()
    try:
        result = client.embed([text], model=VOYAGE_MODEL, input_type="query")
        embedding = result.embeddings[0]
        logger.debug("Embedded query: %d dimensions", len(embedding))
        return embedding
    except Exception as e:
        logger.error("Failed to embed query: %s", e)
        raise


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed multiple documents in a single API call.

    More efficient than calling embed_document() multiple times.

    Args:
        texts: List of fact field contents to embed

    Returns:
        List of 1024-dimensional embedding vectors
    """
    if not texts:
        return []

    client = _get_client()
    try:
        result = client.embed(texts, model=VOYAGE_MODEL, input_type="document")
        logger.debug("Embedded %d documents", len(result.embeddings))
        return result.embeddings
    except Exception as e:
        logger.error("Failed to embed documents: %s", e)
        raise
