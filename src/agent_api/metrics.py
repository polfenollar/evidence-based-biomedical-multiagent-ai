"""Prometheus metrics for the agent-api service.

Metrics
-------
biomedical_queries_total
    Counter.  Labels: ``status`` (approved | rejected | error).
biomedical_query_duration_seconds
    Histogram.  Tracks per-query wall-clock time.
biomedical_dq_violations_total
    Counter.  Labels: ``rule`` (e.g. DQ-UI-1).
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram

QUERIES_TOTAL = Counter(
    "biomedical_queries_total",
    "Total number of evidence queries processed by the agent pipeline",
    ["status"],   # approved | rejected | error
)

QUERY_DURATION = Histogram(
    "biomedical_query_duration_seconds",
    "End-to-end query latency in seconds",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0],
)

DQ_VIOLATIONS_TOTAL = Counter(
    "biomedical_dq_violations_total",
    "Total number of data-quality violations detected at the API boundary",
    ["rule"],     # DQ-UI-1 | ...
)

INGESTION_RECORDS_TOTAL = Counter(
    "biomedical_ingestion_records_total",
    "Total records ingested (incremented by ingestion-worker via push-gateway or agent)",
    ["source"],   # articles | trials
)
