"""Feast FeatureStore factory and helpers.

The ``build_feature_store`` function writes a temporary ``feature_store.yaml``
with real connection values substituted and returns a
:class:`feast.FeatureStore` pointed at that directory.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import feast
from feast import FeatureStore
from feast.infra.offline_stores.file_source import FileSource

from src.feature_worker.config import FeatureConfig
from src.feature_worker.feast_repo.definitions import (
    ARTICLE_ENTITY,
    TRIAL_ENTITY,
    get_article_feature_view,
    get_trial_feature_view,
)

if TYPE_CHECKING:
    pass

_YAML_TEMPLATE = """\
project: biomedical
registry:
  registry_type: sql
  path: postgresql+psycopg2://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/feast_registry
provider: local
online_store:
  type: redis
  connection_string: "{redis_host}:{redis_port},password={redis_password}"
offline_store:
  type: file
entity_key_serialization_version: 2
"""


def build_feature_store(config: FeatureConfig) -> FeatureStore:
    """Build and return a :class:`feast.FeatureStore` using real config values.

    A temporary directory is created, a ``feature_store.yaml`` with all
    placeholders substituted is written into it, and a
    :class:`~feast.FeatureStore` is instantiated from that directory.

    Parameters
    ----------
    config:
        :class:`~src.feature_worker.config.FeatureConfig` containing
        connection details.

    Returns
    -------
    feast.FeatureStore
    """
    yaml_content = _YAML_TEMPLATE.format(
        postgres_user=config.postgres_user,
        postgres_password=config.postgres_password,
        postgres_host=config.postgres_host,
        postgres_port=config.postgres_port,
        redis_host=config.redis_host,
        redis_port=config.redis_port,
        redis_password=config.redis_password,
    )

    # Use a persistent temp directory so the FeatureStore reference stays valid
    tmpdir = tempfile.mkdtemp(prefix="feast_biomedical_")
    yaml_path = Path(tmpdir) / "feature_store.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")

    return FeatureStore(repo_path=tmpdir)


def get_entity_definitions() -> list:
    """Return the list of Feast entity objects to register.

    Returns
    -------
    list
        [ARTICLE_ENTITY, TRIAL_ENTITY]
    """
    return [ARTICLE_ENTITY, TRIAL_ENTITY]


def get_feature_views(
    article_parquet_path: str,
    trial_parquet_path: str,
) -> list:
    """Return the list of Feast feature view objects to register.

    Parameters
    ----------
    article_parquet_path:
        Absolute path to the parquet file containing article features.
    trial_parquet_path:
        Absolute path to the parquet file containing trial features.

    Returns
    -------
    list
        [article_stats FeatureView, trial_stats FeatureView]
    """
    article_source = FileSource(
        path=article_parquet_path,
        timestamp_field="event_timestamp",
    )
    trial_source = FileSource(
        path=trial_parquet_path,
        timestamp_field="event_timestamp",
    )

    return [
        get_article_feature_view(article_source),
        get_trial_feature_view(trial_source),
    ]
