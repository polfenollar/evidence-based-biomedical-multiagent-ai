"""PubMed Open Access record parser.

Parses simplified JSON records sourced from PubMed OA and normalises them
into a canonical shape for ingestion into the raw Iceberg table.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


_PROVENANCE_FIELDS = (
    "source_name",
    "source_version",
    "source_uri",
    "ingested_at",
    "ingestion_run_id",
    "pipeline_version",
)


def _normalize_date(raw_date: str | None) -> str | None:
    """Attempt to parse *raw_date* into an ISO date string.

    Accepted formats: ``YYYY-MM-DD``, ``YYYY-MM``, ``YYYY``.
    Returns the string as-is when it already matches an expected pattern so
    that downstream tooling can rely on the raw value.  Returns ``None`` when
    parsing fails entirely.
    """
    if raw_date is None:
        return None
    value = raw_date.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            datetime.strptime(value, fmt)
            return value  # already a valid partial ISO string
        except ValueError:
            continue
    return None


class PubMedParser:
    """Parser for PubMed OA JSON records."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_record(
        self,
        raw: dict[str, Any],
        run_id: str,
        pipeline_version: str,
    ) -> dict[str, Any]:
        """Parse a single raw PubMed record.

        Parameters
        ----------
        raw:
            Dict matching the PubMed input shape.
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
            If ``pmid`` is absent or ``None``.
        """
        pmid = raw.get("pmid")
        if pmid is None or str(pmid).strip() == "":
            raise ValueError(
                f"Record is missing required field 'pmid': {raw!r}"
            )

        pub_date = _normalize_date(raw.get("publication_date"))

        return {
            "pmid": str(pmid).strip(),
            "title": raw.get("title") or "",
            "abstract": raw.get("abstract"),
            "authors": raw.get("authors") or [],
            "publication_date": pub_date,
            "journal": raw.get("journal"),
            "source_name": "pubmed",
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
        """Parse a batch of raw PubMed records.

        Returns
        -------
        tuple[list[dict], list[dict]]
            A 2-tuple of ``(parsed, rejected)``.  Each rejected record is the
            original dict with an additional ``parse_error`` field.
        """
        parsed: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for record in records:
            try:
                parsed.append(self.parse_record(record, run_id, pipeline_version))
            except (ValueError, Exception) as exc:
                rejected.append({**record, "parse_error": str(exc)})

        return parsed, rejected
