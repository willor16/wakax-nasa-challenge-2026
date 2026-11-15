"""Keeps ``metric_catalog`` in sync with the clinical reference ranges."""

import sqlite3

from app.services.reference_ranges import metric_rows

_UPSERT_SQL = """
    INSERT INTO metric_catalog (
        metric_key, display_name_en, category, unit, nominal_min, nominal_max,
        warning_min, warning_max, critical_min, critical_threshold,
        recommended_frequency_hours, clinical_reference
    ) VALUES (
        :metric_key, :display_name_en, :category, :unit, :nominal_min, :nominal_max,
        :warning_min, :warning_max, :critical_min, :critical_threshold,
        :recommended_frequency_hours, :clinical_reference
    )
    ON CONFLICT(metric_key) DO UPDATE SET
        display_name_en = excluded.display_name_en,
        category = excluded.category,
        unit = excluded.unit,
        nominal_min = excluded.nominal_min,
        nominal_max = excluded.nominal_max,
        warning_min = excluded.warning_min,
        warning_max = excluded.warning_max,
        critical_min = excluded.critical_min,
        critical_threshold = excluded.critical_threshold,
        recommended_frequency_hours = excluded.recommended_frequency_hours,
        clinical_reference = excluded.clinical_reference
"""


def ensure_clinical_metrics(conn: sqlite3.Connection) -> int:
    """Insert or refresh every reference metric. Returns the number of rows touched."""
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'metric_catalog'"
    ).fetchone()
    if table_exists is None:
        return 0
    before = conn.total_changes
    conn.executemany(_UPSERT_SQL, metric_rows())
    return conn.total_changes - before
