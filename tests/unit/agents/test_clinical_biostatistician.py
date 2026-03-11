"""Unit tests for the Clinical Biostatistician agent node."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent_worker.agents.clinical_biostatistician import make_clinical_biostatistician

_BASE_URL = "http://feature-api:8002"


def _mock_get(status: int, body: dict) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = body
    return m


def _article_doc(doc_id: str = "PMID:99000001") -> dict:
    return {
        "doc_id": doc_id,
        "source_type": "article",
        "snippet": "snippet",
        "score": 0.9,
        "title": "Title",
        "iceberg_snapshot_ref": "snap-1",
        "indexing_run_id": "run-1",
    }


def _trial_doc(doc_id: str = "NCT99000001") -> dict:
    return {
        "doc_id": doc_id,
        "source_type": "trial",
        "snippet": "snippet",
        "score": 0.8,
        "title": "Trial Title",
        "iceberg_snapshot_ref": "snap-1",
        "indexing_run_id": "run-1",
    }


class TestClinicalBiostatistician:
    def test_looks_up_article_features(self) -> None:
        biostat = make_clinical_biostatistician(_BASE_URL)
        feat = {"pmid": "99000001", "abstract_word_count": 100}
        with patch("src.agent_worker.agents.clinical_biostatistician.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, feat)
            result = biostat({"retrieved_docs": [_article_doc()]})
        assert "PMID:99000001" in result["features"]
        assert result["features"]["PMID:99000001"]["abstract_word_count"] == 100

    def test_looks_up_trial_features(self) -> None:
        biostat = make_clinical_biostatistician(_BASE_URL)
        feat = {"nct_id": "NCT99000001", "sample_size": 500}
        with patch("src.agent_worker.agents.clinical_biostatistician.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, feat)
            result = biostat({"retrieved_docs": [_trial_doc()]})
        assert "NCT99000001" in result["features"]
        assert result["features"]["NCT99000001"]["sample_size"] == 500

    def test_strips_pmid_prefix_from_doc_id(self) -> None:
        biostat = make_clinical_biostatistician(_BASE_URL)
        with patch("src.agent_worker.agents.clinical_biostatistician.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {})
            biostat({"retrieved_docs": [_article_doc("PMID:12345")]})
        url_called = mock_get.call_args[0][0]
        assert url_called.endswith("/v1/features/article/12345")

    def test_404_response_omits_doc_from_features(self) -> None:
        biostat = make_clinical_biostatistician(_BASE_URL)
        with patch("src.agent_worker.agents.clinical_biostatistician.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(404, {"detail": "not found"})
            result = biostat({"retrieved_docs": [_article_doc()]})
        assert result["features"] == {}

    def test_network_error_omits_doc(self) -> None:
        biostat = make_clinical_biostatistician(_BASE_URL)
        with patch("src.agent_worker.agents.clinical_biostatistician.httpx.get") as mock_get:
            mock_get.side_effect = Exception("timeout")
            result = biostat({"retrieved_docs": [_article_doc()]})
        assert result["features"] == {}

    def test_empty_docs_returns_empty_features(self) -> None:
        biostat = make_clinical_biostatistician(_BASE_URL)
        result = biostat({"retrieved_docs": []})
        assert result["features"] == {}

    def test_multiple_docs_multiple_lookups(self) -> None:
        biostat = make_clinical_biostatistician(_BASE_URL)
        docs = [_article_doc("PMID:1"), _article_doc("PMID:2")]
        responses = [_mock_get(200, {"pmid": "1"}), _mock_get(200, {"pmid": "2"})]
        with patch("src.agent_worker.agents.clinical_biostatistician.httpx.get") as mock_get:
            mock_get.side_effect = responses
            result = biostat({"retrieved_docs": docs})
        assert len(result["features"]) == 2

    def test_unknown_source_type_skipped(self) -> None:
        biostat = make_clinical_biostatistician(_BASE_URL)
        doc = {
            "doc_id": "OTHER:999",
            "source_type": "guideline",
            "snippet": "s",
            "score": 0.5,
        }
        with patch("src.agent_worker.agents.clinical_biostatistician.httpx.get") as mock_get:
            result = biostat({"retrieved_docs": [doc]})
        mock_get.assert_not_called()
        assert result["features"] == {}
