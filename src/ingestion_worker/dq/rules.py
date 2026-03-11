"""Data Quality rules for raw ingestion records.

Rules are pure Python functions operating on lists of dicts — no Spark
dependency — so they can be executed and unit-tested without a Spark cluster.

Rule IDs are taken directly from ``05-data-quality-rules.md``:
  DQ-PUB-RAW-1  pmid present
  DQ-PUB-CUR-1  pmid unique
  DQ-PUB-CUR-2  title non-empty
  DQ-P1         provenance fields complete
  DQ-CT-RAW-1   nct_id present
  DQ-CT-CUR-1   nct_id unique
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ── Result type ──────────────────────────────────────────────────────────────

@dataclass
class DQResult:
    rule_id: str
    outcome: Literal["PASS", "WARN", "FAIL"]
    message: str
    record_count: int = 0
    failed_ids: list[str] = field(default_factory=list)


# ── Provenance fields that must be present ────────────────────────────────────

_PROVENANCE_REQUIRED = [
    "source_name",
    "source_version",
    "source_uri",
    "ingested_at",
    "ingestion_run_id",
    "pipeline_version",
]


# ── Individual rule functions ─────────────────────────────────────────────────

def check_pmid_present(record: dict[str, Any]) -> DQResult:
    """DQ-PUB-RAW-1: pmid must not be null or empty."""
    pmid = record.get("pmid")
    if pmid is None or str(pmid).strip() == "":
        return DQResult(
            rule_id="DQ-PUB-RAW-1",
            outcome="FAIL",
            message="pmid is null or empty",
            record_count=1,
            failed_ids=[],
        )
    return DQResult(
        rule_id="DQ-PUB-RAW-1",
        outcome="PASS",
        message="pmid present",
        record_count=1,
    )


def check_pmid_unique(records: list[dict[str, Any]]) -> DQResult:
    """DQ-PUB-CUR-1: All pmids in the batch must be unique."""
    seen: dict[str, int] = {}
    for rec in records:
        pmid = rec.get("pmid")
        if pmid is not None:
            seen[str(pmid)] = seen.get(str(pmid), 0) + 1

    duplicates = [pmid for pmid, count in seen.items() if count > 1]
    if duplicates:
        return DQResult(
            rule_id="DQ-PUB-CUR-1",
            outcome="FAIL",
            message=f"Duplicate pmids found: {duplicates}",
            record_count=len(records),
            failed_ids=duplicates,
        )
    return DQResult(
        rule_id="DQ-PUB-CUR-1",
        outcome="PASS",
        message="All pmids are unique",
        record_count=len(records),
    )


def check_title_nonempty(record: dict[str, Any]) -> DQResult:
    """DQ-PUB-CUR-2: title must not be empty."""
    title = record.get("title")
    if title is None or str(title).strip() == "":
        pmid = record.get("pmid", "unknown")
        return DQResult(
            rule_id="DQ-PUB-CUR-2",
            outcome="FAIL",
            message=f"title is empty for pmid={pmid}",
            record_count=1,
            failed_ids=[str(pmid)],
        )
    return DQResult(
        rule_id="DQ-PUB-CUR-2",
        outcome="PASS",
        message="title is non-empty",
        record_count=1,
    )


def check_provenance_fields(record: dict[str, Any]) -> DQResult:
    """DQ-P1: All provenance fields must be present and non-empty."""
    missing = [
        f for f in _PROVENANCE_REQUIRED
        if record.get(f) is None or str(record.get(f, "")).strip() == ""
    ]
    if missing:
        record_id = record.get("pmid") or record.get("nct_id") or "unknown"
        return DQResult(
            rule_id="DQ-P1",
            outcome="FAIL",
            message=f"Missing provenance fields: {missing}",
            record_count=1,
            failed_ids=[str(record_id)],
        )
    return DQResult(
        rule_id="DQ-P1",
        outcome="PASS",
        message="All provenance fields present",
        record_count=1,
    )


def check_nct_id_present(record: dict[str, Any]) -> DQResult:
    """DQ-CT-RAW-1: nct_id must not be null or empty."""
    nct_id = record.get("nct_id")
    if nct_id is None or str(nct_id).strip() == "":
        return DQResult(
            rule_id="DQ-CT-RAW-1",
            outcome="FAIL",
            message="nct_id is null or empty",
            record_count=1,
            failed_ids=[],
        )
    return DQResult(
        rule_id="DQ-CT-RAW-1",
        outcome="PASS",
        message="nct_id present",
        record_count=1,
    )


def check_nct_id_unique(records: list[dict[str, Any]]) -> DQResult:
    """DQ-CT-CUR-1: All nct_ids in the batch must be unique."""
    seen: dict[str, int] = {}
    for rec in records:
        nct_id = rec.get("nct_id")
        if nct_id is not None:
            seen[str(nct_id)] = seen.get(str(nct_id), 0) + 1

    duplicates = [nct_id for nct_id, count in seen.items() if count > 1]
    if duplicates:
        return DQResult(
            rule_id="DQ-CT-CUR-1",
            outcome="FAIL",
            message=f"Duplicate nct_ids found: {duplicates}",
            record_count=len(records),
            failed_ids=duplicates,
        )
    return DQResult(
        rule_id="DQ-CT-CUR-1",
        outcome="PASS",
        message="All nct_ids are unique",
        record_count=len(records),
    )


# ── Batch runners ─────────────────────────────────────────────────────────────

def run_pubmed_dq(records: list[dict[str, Any]]) -> list[DQResult]:
    """Run all PubMed DQ rules against *records*.

    Returns
    -------
    list[DQResult]
        One result per rule execution.  Record-level rules produce one result
        per record; batch rules produce a single result for the whole batch.
    """
    results: list[DQResult] = []

    # Record-level rules
    for record in records:
        results.append(check_pmid_present(record))
        results.append(check_title_nonempty(record))
        results.append(check_provenance_fields(record))

    # Batch-level rules
    results.append(check_pmid_unique(records))

    return results


def run_clinicaltrials_dq(records: list[dict[str, Any]]) -> list[DQResult]:
    """Run all ClinicalTrials DQ rules against *records*.

    Returns
    -------
    list[DQResult]
        One result per rule execution.
    """
    results: list[DQResult] = []

    # Record-level rules
    for record in records:
        results.append(check_nct_id_present(record))
        results.append(check_provenance_fields(record))

    # Batch-level rules
    results.append(check_nct_id_unique(records))

    return results


# ── Aggregate helper ──────────────────────────────────────────────────────────

def has_blocking_failures(results: list[DQResult]) -> bool:
    """Return ``True`` if any result has outcome ``"FAIL"``."""
    return any(r.outcome == "FAIL" for r in results)
