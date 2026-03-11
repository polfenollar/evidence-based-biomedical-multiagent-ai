"""DQ report builder and serialiser."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.ingestion_worker.dq.rules import DQResult, has_blocking_failures


@dataclass
class DQReport:
    run_id: str
    pipeline_version: str
    source_name: str
    evaluated_at: str
    total_records: int
    results: list[DQResult]
    snapshot_id: str | None = None
    has_failures: bool = False


def build_report(
    run_id: str,
    pipeline_version: str,
    source_name: str,
    records: list[dict[str, Any]],
    results: list[DQResult],
    snapshot_id: str | None = None,
) -> DQReport:
    """Build a :class:`DQReport` from a list of records and DQ results.

    Parameters
    ----------
    run_id:
        Ingestion run identifier.
    pipeline_version:
        Semver string for the pipeline release.
    source_name:
        ``"pubmed"`` or ``"clinicaltrials"``.
    records:
        The parsed records that were evaluated.
    results:
        DQ results produced by the rule runners.
    snapshot_id:
        Optional Iceberg snapshot ID after writing.

    Returns
    -------
    DQReport
    """
    return DQReport(
        run_id=run_id,
        pipeline_version=pipeline_version,
        source_name=source_name,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        total_records=len(records),
        results=results,
        snapshot_id=snapshot_id,
        has_failures=has_blocking_failures(results),
    )


def report_to_dict(report: DQReport) -> dict[str, Any]:
    """Serialise *report* to a plain dict suitable for JSON storage."""
    d = asdict(report)
    return d
