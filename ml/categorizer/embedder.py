"""
Sentence-transformer embedder for item text.
Uses all-MiniLM-L6-v2 for fast, high-quality 384-dim embeddings.
"""

import numpy as np
import logging
from typing import Optional

logger = logging.getLogger("splitsenseai.categorizer.embedder")

_model = None


def get_embedding_model():
    """Lazy-load the sentence-transformer model."""
    global _model
    if _model is None:
        logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded.")
    return _model


class ItemEmbedder:
    """
    Generates semantic embeddings for item names.
    Used for categorization and clustering.
    """

    def __init__(self):
        self.model = get_embedding_model()

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single item name."""
        return self.model.encode(text, normalize_embeddings=True)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for multiple items."""
        if not texts:
            return np.array([])
        return self.model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)

    def similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two item names."""
        emb1 = self.embed(text1)
        emb2 = self.embed(text2)
        return float(np.dot(emb1, emb2))
