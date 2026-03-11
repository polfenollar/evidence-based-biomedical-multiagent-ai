"""Unit tests for the Embedder class.

The SentenceTransformer model is mocked so these tests run without any
GPU/CPU-heavy model downloads.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.embedding_worker.embedder import Embedder


_DIMENSION = 384
_MOCK_VECTOR = np.ones(_DIMENSION, dtype=np.float32)


def _make_mock_model(dimension: int = _DIMENSION) -> MagicMock:
    """Return a MagicMock that mimics a SentenceTransformer instance."""
    mock = MagicMock()
    mock.get_sentence_embedding_dimension.return_value = dimension
    # encode returns a 2-D numpy array with shape (n_texts, dimension)
    mock.encode.side_effect = lambda texts, **kwargs: np.tile(
        np.ones(dimension, dtype=np.float32), (len(texts), 1)
    )
    return mock


class TestEmbedder(unittest.TestCase):
    """Tests for src.embedding_worker.embedder.Embedder."""

    # ── embed_batch ────────────────────────────────────────────────────────────

    def test_embed_batch_returns_list_of_float_lists(self) -> None:
        """embed_batch should return a list[list[float]]."""
        with patch(
            "src.embedding_worker.embedder.SentenceTransformer",
            return_value=_make_mock_model(),
        ):
            embedder = Embedder()
            result = embedder.embed_batch(["hello world", "foo bar"])

        assert isinstance(result, list)
        assert len(result) == 2
        for vec in result:
            assert isinstance(vec, list)
            assert all(isinstance(v, float) for v in vec)

    def test_embed_batch_correct_length(self) -> None:
        """Each returned vector should have the model's dimension."""
        with patch(
            "src.embedding_worker.embedder.SentenceTransformer",
            return_value=_make_mock_model(_DIMENSION),
        ):
            embedder = Embedder()
            result = embedder.embed_batch(["test"])

        assert len(result[0]) == _DIMENSION

    def test_embed_batch_empty_returns_empty(self) -> None:
        """embed_batch([]) must return [] without loading the model."""
        embedder = Embedder()
        # No mock needed — model should NOT be loaded for an empty input
        result = embedder.embed_batch([])
        assert result == []

    def test_embed_batch_multiple_texts(self) -> None:
        """embed_batch should return one vector per input text."""
        texts = ["alpha", "beta", "gamma", "delta"]
        with patch(
            "src.embedding_worker.embedder.SentenceTransformer",
            return_value=_make_mock_model(),
        ):
            embedder = Embedder()
            result = embedder.embed_batch(texts)

        assert len(result) == len(texts)

    # ── embed_single ───────────────────────────────────────────────────────────

    def test_embed_single_returns_list_of_floats(self) -> None:
        """embed_single should return a list[float]."""
        with patch(
            "src.embedding_worker.embedder.SentenceTransformer",
            return_value=_make_mock_model(),
        ):
            embedder = Embedder()
            result = embedder.embed_single("single text")

        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_embed_single_correct_dimension(self) -> None:
        """embed_single should return a vector of the correct dimension."""
        with patch(
            "src.embedding_worker.embedder.SentenceTransformer",
            return_value=_make_mock_model(_DIMENSION),
        ):
            embedder = Embedder()
            result = embedder.embed_single("test")

        assert len(result) == _DIMENSION

    # ── dimension property ─────────────────────────────────────────────────────

    def test_dimension_returns_model_dimension(self) -> None:
        """dimension property should delegate to the model."""
        with patch(
            "src.embedding_worker.embedder.SentenceTransformer",
            return_value=_make_mock_model(_DIMENSION),
        ):
            embedder = Embedder()
            assert embedder.dimension == _DIMENSION

    # ── lazy loading ───────────────────────────────────────────────────────────

    def test_model_lazy_loaded_on_embed(self) -> None:
        """The SentenceTransformer constructor should not be called until embed is invoked."""
        with patch(
            "src.embedding_worker.embedder.SentenceTransformer",
            return_value=_make_mock_model(),
        ) as MockST:
            embedder = Embedder()
            # Model not yet loaded
            MockST.assert_not_called()
            # Trigger lazy load
            embedder.embed_single("trigger load")
            MockST.assert_called_once()

    # ── model_name / model_version properties ──────────────────────────────────

    def test_model_name_and_version_properties(self) -> None:
        """model_name and model_version should return constructor arguments."""
        embedder = Embedder(model_name="custom-model", model_version="42")
        assert embedder.model_name == "custom-model"
        assert embedder.model_version == "42"


if __name__ == "__main__":
    unittest.main()
