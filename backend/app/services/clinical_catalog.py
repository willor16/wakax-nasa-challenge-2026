import sqlite3
from typing import Any

DEV2_SUPPLEMENTAL_METRICS: tuple[dict[str, Any], ...] = (
    {
        "metric_key": "bp_diastolic_mmhg",
        "display_name_en": "Diastolic Blood Pressure",
        "category": "VITALS",
        "unit": "mmHg",
        "nominal_min": 60.0,
        "nominal_max": 85.0,
        "warning_min": 55.0,
        "warning_max": 90.0,
        "critical_min": 50.0,
        "critical_threshold": 105.0,
        "recommended_frequency_hours": 24.0,
        "clinical_reference": "Arterial Diastolic Pressure & Microgravity Fluid Shift Standard",
    },
    {
        "metric_key": "ecg_lead_ii_mv",
        "display_name_en": "Electrocardiogram Lead II",
        "category": "VITALS",
        "unit": "mV",
        "nominal_min": -0.5,
        "nominal_max": 2.0,
        "warning_min": -1.0,
        "warning_max": 2.5,
        "critical_min": -1.5,
        "critical_threshold": 3.0,
        "recommended_frequency_hours": 24.0,
        "clinical_reference": "Single-Lead Rhythm & R-Peak Amplitude Telemetry Standard",
    },
    {
        "metric_key": "orthostatic_hr_delta_bpm",
        "display_name_en": "Orthostatic Heart Rate Delta",
        "category": "VITALS",
        "unit": "bpm",
        "nominal_min": 0.0,
        "nominal_max": 20.0,
        "warning_min": None,
        "warning_max": 27.0,
        "critical_min": None,
        "critical_threshold": 30.0,
        "recommended_frequency_hours": 168.0,
        "clinical_reference": "Post-Transit Orthostatic Intolerance Screening (>= 30 bpm critical)",
    },
    {
        "metric_key": "bmi_kg_m2",
        "display_name_en": "Body Mass Index",
        "category": "BIOMETRICS",
        "unit": "kg/m2",
        "nominal_min": 18.5,
        "nominal_max": 26.5,
        "warning_min": 17.5,
        "warning_max": 28.5,
        "critical_min": 16.5,
        "critical_threshold": 32.0,
        "recommended_frequency_hours": 168.0,
        "clinical_reference": "Crew Anthropometric Mass-to-Stature Index",
    },
    {
        "metric_key": "hemoglobin_g_dl",
        "display_name_en": "Hemoglobin",
        "category": "LABS",
        "unit": "g/dL",
        "nominal_min": 12.5,
        "nominal_max": 17.0,
        "warning_min": 11.2,
        "warning_max": 18.0,
        "critical_min": 10.0,
        "critical_threshold": 19.5,
        "recommended_frequency_hours": 168.0,
        "clinical_reference": "Spaceflight Hemolysis & Erythrocyte Mass Reference",
    },
    {
        "metric_key": "urine_specific_gravity",
        "display_name_en": "Urine Specific Gravity",
        "category": "LABS",
        "unit": "SG",
        "nominal_min": 1.005,
        "nominal_max": 1.022,
        "warning_min": 1.003,
        "warning_max": 1.028,
        "critical_min": 1.001,
        "critical_threshold": 1.032,
        "recommended_frequency_hours": 72.0,
        "clinical_reference": "Nephrolithiasis Risk & Urinary Concentration Marker",
    },
    {
        "metric_key": "urine_protein_mg_dl",
        "display_name_en": "Urine Protein",
        "category": "LABS",
        "unit": "mg/dL",
        "nominal_min": 0.0,
        "nominal_max": 14.0,
        "warning_min": None,
        "warning_max": 30.0,
        "critical_min": None,
        "critical_threshold": 100.0,
        "recommended_frequency_hours": 168.0,
        "clinical_reference": "Renal Dipstick Proteinuria Screening Reference",
    },
    {
        "metric_key": "respiratory_rate_brpm",
        "display_name_en": "Respiratory Rate",
        "category": "RESPIRATORY",
        "unit": "brpm",
        "nominal_min": 10.0,
        "nominal_max": 20.0,
        "warning_min": 8.0,
        "warning_max": 24.0,
        "critical_min": 6.0,
        "critical_threshold": 28.0,
        "recommended_frequency_hours": 12.0,
        "clinical_reference": "Resting Ventilation & Hypercapnic Drive Standard",
    },
    {
        "metric_key": "cardiorespiratory_index",
        "display_name_en": "Cardiorespiratory Coupling Index",
        "category": "RESPIRATORY",
        "unit": "pts",
        "nominal_min": 75.0,
        "nominal_max": 100.0,
        "warning_min": 60.0,
        "warning_max": 100.0,
        "critical_min": 45.0,
        "critical_threshold": None,
        "recommended_frequency_hours": 24.0,
        "clinical_reference": "Integrated Phonocardiogram & Ventilation Readiness Score",
    },
    {
        "metric_key": "work_shift_min",
        "display_name_en": "Operational Work Shift Duration",
        "category": "HABITS",
        "unit": "min",
        "nominal_min": 180.0,
        "nominal_max": 540.0,
        "warning_min": 60.0,
        "warning_max": 600.0,
        "critical_min": None,
        "critical_threshold": 720.0,
        "recommended_frequency_hours": 24.0,
        "clinical_reference": "Operational Duty & Extravehicular Exposure Workload Limit",
    },
)

_SUPPLEMENTAL_KEYS: tuple[str, ...] = tuple(m["metric_key"] for m in DEV2_SUPPLEMENTAL_METRICS)
_PLACEHOLDERS = ",".join("?" for _ in _SUPPLEMENTAL_KEYS)


def ensure_clinical_metrics(conn: sqlite3.Connection) -> int:
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'metric_catalog'"
    ).fetchone()
    if table_exists is None:
        return 0

    present_count = conn.execute(
        f"SELECT COUNT(*) FROM metric_catalog WHERE metric_key IN ({_PLACEHOLDERS})",
        _SUPPLEMENTAL_KEYS,
    ).fetchone()[0]
    if int(present_count) == len(DEV2_SUPPLEMENTAL_METRICS):
        return 0

    before_changes = conn.total_changes
    conn.executemany(
        """
        INSERT OR IGNORE INTO metric_catalog (
            metric_key, display_name_en, category, unit, nominal_min, nominal_max,
            warning_min, warning_max, critical_min, critical_threshold,
            recommended_frequency_hours, clinical_reference
        ) VALUES (
            :metric_key, :display_name_en, :category, :unit, :nominal_min, :nominal_max,
            :warning_min, :warning_max, :critical_min, :critical_threshold,
            :recommended_frequency_hours, :clinical_reference
        )
        """,
        DEV2_SUPPLEMENTAL_METRICS,
    )
    return conn.total_changes - before_changes
