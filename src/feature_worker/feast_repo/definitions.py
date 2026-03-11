"""Feast entity and feature view definitions for the biomedical feature store.

Entities and feature views are defined programmatically so they can be
registered without relying on YAML discovery files.
"""
from __future__ import annotations

from datetime import timedelta

from feast import Entity, FeatureView, Field
from feast.infra.offline_stores.file_source import FileSource
from feast.types import Int64, String

# ── Entities ──────────────────────────────────────────────────────────────────

ARTICLE_ENTITY = Entity(
    name="biomedical_article",
    join_keys=["pmid"],
    description="A biomedical article identified by its PubMed ID.",
)

TRIAL_ENTITY = Entity(
    name="clinical_trial",
    join_keys=["nct_id"],
    description="A clinical trial identified by its NCT ID.",
)


# ── Feature view factories ─────────────────────────────────────────────────────


def get_article_feature_view(source: FileSource) -> FeatureView:
    """Return the ``article_stats`` FeatureView backed by ``source``.

    Parameters
    ----------
    source:
        A :class:`feast.infra.offline_stores.file_source.FileSource` pointing
        to the parquet file written by the feature worker.

    Returns
    -------
    FeatureView
    """
    return FeatureView(
        name="article_stats",
        entities=[ARTICLE_ENTITY],
        ttl=timedelta(days=365),
        schema=[
            Field(name="title_word_count", dtype=Int64),
            Field(name="abstract_word_count", dtype=Int64),
            Field(name="publication_year", dtype=Int64),
            Field(name="has_abstract", dtype=Int64),
            Field(name="journal_encoded", dtype=String),
            Field(name="snapshot_ref", dtype=String),
        ],
        source=source,
        description="Computed statistics for biomedical articles.",
    )


def get_trial_feature_view(source: FileSource) -> FeatureView:
    """Return the ``trial_stats`` FeatureView backed by ``source``.

    Parameters
    ----------
    source:
        A :class:`feast.infra.offline_stores.file_source.FileSource` pointing
        to the parquet file written by the feature worker.

    Returns
    -------
    FeatureView
    """
    return FeatureView(
        name="trial_stats",
        entities=[TRIAL_ENTITY],
        ttl=timedelta(days=365),
        schema=[
            Field(name="sample_size", dtype=Int64),
            Field(name="has_outcomes", dtype=Int64),
            Field(name="status_encoded", dtype=String),
            Field(name="condition_count", dtype=Int64),
            Field(name="snapshot_ref", dtype=String),
        ],
        source=source,
        description="Computed statistics for clinical trials.",
    )
