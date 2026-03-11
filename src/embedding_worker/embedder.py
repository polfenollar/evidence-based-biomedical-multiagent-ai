"""Embedding utilities for the biomedical embedding worker.

Wraps sentence-transformers with lazy model loading and batch/single
embedding helpers.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover — installed in Docker, mocked in unit tests
    SentenceTransformer = None  # type: ignore[assignment,misc]

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer


class Embedder:
    """Generates embeddings using a sentence-transformers model.

    The underlying model is lazy-loaded on the first call to
    :meth:`embed_batch` or :meth:`embed_single` to avoid loading the model
    at import time (useful for unit tests and worker startup speed).

    Parameters
    ----------
    model_name:
        HuggingFace / sentence-transformers model identifier.
    model_version:
        Logical version string stored in Qdrant payloads.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", model_version: str = "1") -> None:
        self._model_name = model_name
        self._model_version = model_version
        self._model: _SentenceTransformer | None = None

    # ── Lazy loader ────────────────────────────────────────────────────────────

    def _get_model(self) -> _SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model

    # ── Public API ─────────────────────────────────────────────────────────────

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts and return normalised float vectors.

        Parameters
        ----------
        texts:
            Texts to embed.  An empty list returns an empty list immediately
            without loading the model.

        Returns
        -------
        list[list[float]]
            One float vector per input text, L2-normalised.
        """
        if not texts:
            return []

        model = self._get_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [vec.tolist() for vec in embeddings]

    def embed_single(self, text: str) -> list[float]:
        """Embed a single text string.

        Parameters
        ----------
        text:
            Text to embed.

        Returns
        -------
        list[float]
            L2-normalised float vector.
        """
        return self.embed_batch([text])[0]

    # ── Properties ─────────────────────────────────────────────────────────────

    @property
    def dimension(self) -> int:
        """Vector dimension of the loaded model (e.g. 384 for MiniLM)."""
        return self._get_model().get_sentence_embedding_dimension()

    @property
    def model_name(self) -> str:
        """Sentence-transformers model identifier."""
        return self._model_name

    @property
    def model_version(self) -> str:
        """Logical version string for this embedding model."""
        return self._model_version
