"""Pure-Python feature computation functions for biomedical entities.

No Feast or Spark imports — designed for easy unit testing and to be called
from the feature worker activity before materializing to the online store.
"""
from __future__ import annotations


def _parse_publication_year(publication_date: str | None) -> int:
    """Extract the 4-digit year from a publication_date string.

    Supported formats: ``YYYY-MM-DD``, ``YYYY-MM``, ``YYYY``.
    Returns 0 on any parse failure.
    """
    if not publication_date:
        return 0
    try:
        parts = str(publication_date).strip().split("-")
        year_str = parts[0]
        if len(year_str) == 4 and year_str.isdigit():
            return int(year_str)
        return 0
    except Exception:
        return 0


def compute_article_stats(record: dict) -> dict:
    """Compute article_stats features for a single article record.

    Parameters
    ----------
    record:
        dict with keys ``pmid``, ``title``, ``abstract``,
        ``publication_date``, ``journal``, ``snapshot_ref``.

    Returns
    -------
    dict
        Keys: ``pmid``, ``title_word_count``, ``abstract_word_count``,
        ``publication_year``, ``has_abstract``, ``journal_encoded``,
        ``snapshot_ref``.
    """
    title: str = record.get("title") or ""
    abstract: str | None = record.get("abstract")
    publication_date: str | None = record.get("publication_date")
    journal: str = record.get("journal") or ""
    snapshot_ref: str = record.get("snapshot_ref") or ""

    title_word_count: int = len(title.split()) if title.strip() else 0

    if abstract and abstract.strip():
        abstract_word_count = len(abstract.split())
        has_abstract = 1
    else:
        abstract_word_count = 0
        has_abstract = 0

    publication_year = _parse_publication_year(publication_date)

    return {
        "pmid": record.get("pmid"),
        "title_word_count": title_word_count,
        "abstract_word_count": abstract_word_count,
        "publication_year": publication_year,
        "has_abstract": has_abstract,
        "journal_encoded": journal,
        "snapshot_ref": snapshot_ref,
    }


def compute_trial_stats(record: dict) -> dict:
    """Compute trial_stats features for a single trial record.

    Parameters
    ----------
    record:
        dict with keys ``nct_id``, ``sample_size``, ``primary_outcomes``,
        ``status``, ``conditions``, ``snapshot_ref``.

    Returns
    -------
    dict
        Keys: ``nct_id``, ``sample_size``, ``has_outcomes``,
        ``status_encoded``, ``condition_count``, ``snapshot_ref``.
    """
    raw_sample_size = record.get("sample_size")
    primary_outcomes: str | None = record.get("primary_outcomes")
    status: str = record.get("status") or ""
    conditions: str | None = record.get("conditions")
    snapshot_ref: str = record.get("snapshot_ref") or ""

    # sample_size: 0 if null/None
    try:
        sample_size = int(raw_sample_size) if raw_sample_size is not None else 0
    except (TypeError, ValueError):
        sample_size = 0

    # has_outcomes: 1 if primary_outcomes is non-null and non-empty
    if primary_outcomes and str(primary_outcomes).strip():
        has_outcomes = 1
    else:
        has_outcomes = 0

    # condition_count: split by comma, count non-empty items
    if conditions and str(conditions).strip():
        parts = [c.strip() for c in str(conditions).split(",")]
        condition_count = sum(1 for p in parts if p)
    else:
        condition_count = 0

    return {
        "nct_id": record.get("nct_id"),
        "sample_size": sample_size,
        "has_outcomes": has_outcomes,
        "status_encoded": status,
        "condition_count": condition_count,
        "snapshot_ref": snapshot_ref,
    }


def compute_article_stats_batch(records: list[dict]) -> list[dict]:
    """Apply :func:`compute_article_stats` to a batch of records.

    Parameters
    ----------
    records:
        List of article record dicts.

    Returns
    -------
    list[dict]
        Computed feature dicts in the same order as input.
    """
    return [compute_article_stats(r) for r in records]


def compute_trial_stats_batch(records: list[dict]) -> list[dict]:
    """Apply :func:`compute_trial_stats` to a batch of records.

    Parameters
    ----------
    records:
        List of trial record dicts.

    Returns
    -------
    list[dict]
        Computed feature dicts in the same order as input.
    """
    return [compute_trial_stats(r) for r in records]
