"""Temporal activities for the biomedical ingestion pipeline."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from temporalio import activity

from src.ingestion_worker.config import get_config
from src.ingestion_worker.dq.report import build_report, report_to_dict
from src.ingestion_worker.dq.rules import run_pubmed_dq, run_clinicaltrials_dq
from src.ingestion_worker.parsers.clinicaltrials import ClinicalTrialsParser
from src.ingestion_worker.parsers.pubmed import PubMedParser


@dataclass
class IngestionInput:
    source_name: str          # "pubmed" | "clinicaltrials"
    source_file_path: str     # path to JSON sample file
    run_id: str
    pipeline_version: str


@dataclass
class IngestionOutput:
    run_id: str
    source_name: str
    raw_snapshot_id: str
    curated_snapshot_id: str
    dq_report: dict
    records_ingested: int
    dq_passed: bool


@activity.defn
async def parse_and_validate_activity(input: IngestionInput) -> dict[str, Any]:
    """Load a JSON file, parse records, and run DQ rules.

    Parameters
    ----------
    input:
        IngestionInput describing the source and file path.

    Returns
    -------
    dict
        Contains keys: ``parsed_records``, ``rejected_records``, ``dq_report``,
        ``dq_passed``, ``source_name``, ``run_id``, ``pipeline_version``.
    """
    logger = activity.logger

    logger.info(
        "parse_and_validate_activity: source=%s file=%s run_id=%s",
        input.source_name,
        input.source_file_path,
        input.run_id,
    )

    with open(input.source_file_path, "r", encoding="utf-8") as fh:
        raw_records: list[dict[str, Any]] = json.load(fh)

    if input.source_name == "pubmed":
        parser = PubMedParser()
        parsed, rejected = parser.parse_batch(
            raw_records, input.run_id, input.pipeline_version
        )
        dq_results = run_pubmed_dq(parsed)
    elif input.source_name == "clinicaltrials":
        parser = ClinicalTrialsParser()  # type: ignore[assignment]
        parsed, rejected = parser.parse_batch(
            raw_records, input.run_id, input.pipeline_version
        )
        dq_results = run_clinicaltrials_dq(parsed)
    else:
        raise ValueError(f"Unknown source_name: {input.source_name!r}")

    report = build_report(
        run_id=input.run_id,
        pipeline_version=input.pipeline_version,
        source_name=input.source_name,
        records=parsed,
        results=dq_results,
    )
    report_dict = report_to_dict(report)

    logger.info(
        "parse_and_validate_activity: parsed=%d rejected=%d dq_passed=%s",
        len(parsed),
        len(rejected),
        not report.has_failures,
    )

    return {
        "parsed_records": parsed,
        "rejected_records": rejected,
        "dq_report": report_dict,
        "dq_passed": not report.has_failures,
        "source_name": input.source_name,
        "run_id": input.run_id,
        "pipeline_version": input.pipeline_version,
    }


@activity.defn
async def write_to_lake_activity(input: dict[str, Any]) -> IngestionOutput:
    """Write parsed records to the raw and curated Iceberg tables via Spark.

    Parameters
    ----------
    input:
        The dict returned by :func:`parse_and_validate_activity`.

    Returns
    -------
    IngestionOutput
    """
    # Import Spark dependencies here to avoid importing them at module load
    # time in environments where PySpark is not available (e.g., unit tests).
    from src.ingestion_worker.spark.jobs import (
        curate_clinicaltrials,
        curate_pubmed,
        write_raw_clinicaltrials,
        write_raw_pubmed,
    )
    from src.ingestion_worker.spark.session import build_spark_session

    logger = activity.logger

    config = get_config()
    source_name: str = input["source_name"]
    parsed_records: list[dict[str, Any]] = input["parsed_records"]

    logger.info(
        "write_to_lake_activity: source=%s records=%d",
        source_name,
        len(parsed_records),
    )

    spark = build_spark_session(config)

    try:
        if source_name == "pubmed":
            raw_snapshot_id = write_raw_pubmed(spark, parsed_records, config)
            curated_snapshot_id = curate_pubmed(spark, config)
        elif source_name == "clinicaltrials":
            raw_snapshot_id = write_raw_clinicaltrials(spark, parsed_records, config)
            curated_snapshot_id = curate_clinicaltrials(spark, config)
        else:
            raise ValueError(f"Unknown source_name: {source_name!r}")
    finally:
        spark.stop()

    return IngestionOutput(
        run_id=input["run_id"],
        source_name=source_name,
        raw_snapshot_id=raw_snapshot_id,
        curated_snapshot_id=curated_snapshot_id,
        dq_report=input["dq_report"],
        records_ingested=len(parsed_records),
        dq_passed=input["dq_passed"],
    )
