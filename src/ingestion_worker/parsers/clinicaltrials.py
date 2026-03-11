"""ClinicalTrials.gov record parser.

Parses simplified JSON records sourced from ClinicalTrials.gov and normalises
them into a canonical shape for ingestion into the raw Iceberg table.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _normalize_date(raw_date: str | None) -> str | None:
    """Attempt to parse *raw_date* into an ISO date string.

    Accepted formats: ``YYYY-MM-DD``, ``YYYY-MM``, ``YYYY``.
    Returns the string as-is on success, ``None`` on failure.
    """
    if raw_date is None:
        return None
    value = raw_date.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            datetime.strptime(value, fmt)
            return value
        except ValueError:
            continue
    return None


class ClinicalTrialsParser:
    """Parser for ClinicalTrials.gov JSON records."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_record(
        self,
        raw: dict[str, Any],
        run_id: str,
        pipeline_version: str,
    ) -> dict[str, Any]:
        """Parse a single raw ClinicalTrials record.

        Parameters
        ----------
        raw:
            Dict matching the ClinicalTrials input shape.
        run_id:
            Identifier for the current ingestion run.
        pipeline_version:
            Semver string for the pipeline release.

        Returns
        -------
        dict
            Parsed record with all provenance fields populated.

        Raises
        ------
        ValueError
            If ``nct_id`` is absent or ``None``.
        """
        nct_id = raw.get("nct_id")
        if nct_id is None or str(nct_id).strip() == "":
            raise ValueError(
                f"Record is missing required field 'nct_id': {raw!r}"
            )

        sample_size = raw.get("sample_size")
        if sample_size is not None:
            try:
                sample_size = int(sample_size)
            except (ValueError, TypeError):
                sample_size = None

        return {
            "nct_id": str(nct_id).strip(),
            "brief_title": raw.get("brief_title") or "",
            "conditions": raw.get("conditions") or [],
            "interventions": raw.get("interventions") or [],
            "primary_outcomes": raw.get("primary_outcomes") or [],
            "sample_size": sample_size,
            "status": raw.get("status") or "",
            "start_date": _normalize_date(raw.get("start_date")),
            "completion_date": _normalize_date(raw.get("completion_date")),
            "source_name": "clinicaltrials",
            "source_version": raw.get("source_version", ""),
            "source_uri": raw.get("source_uri", ""),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "ingestion_run_id": run_id,
            "pipeline_version": pipeline_version,
        }

    def parse_batch(
        self,
        records: list[dict[str, Any]],
        run_id: str,
        pipeline_version: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Parse a batch of raw ClinicalTrials records.

        Returns
        -------
        tuple[list[dict], list[dict]]
            A 2-tuple of ``(parsed, rejected)``.  Each rejected record carries
            an additional ``parse_error`` field.
        """
        parsed: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for record in records:
            try:
                parsed.append(self.parse_record(record, run_id, pipeline_version))
            except (ValueError, Exception) as exc:
                rejected.append({**record, "parse_error": str(exc)})

        return parsed, rejected
