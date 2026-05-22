"""
MiniLM embedding model wrapper.
The model is loaded once at module import time and reused for all requests.
Model: all-MiniLM-L6-v2 (384-dimensional vectors, fast and lightweight).
"""
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading MiniLM model (all-MiniLM-L6-v2)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("MiniLM model loaded")
    return _model


def encode(text: str) -> list[float]:
    """Encode a single string to a 384-dim vector."""
    if not text or not text.strip():
        return [0.0] * 384
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def encode_batch(texts: list[str]) -> list[list[float]]:
    """Encode a batch of strings. Empty strings get zero vectors."""
    if not texts:
        return []
    model = _get_model()
    cleaned = [t if t and t.strip() else "" for t in texts]
    vectors = model.encode(cleaned, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    return [v.tolist() for v in vectors]
