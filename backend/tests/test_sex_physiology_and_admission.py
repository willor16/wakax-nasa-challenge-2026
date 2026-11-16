"""Sex-calibrated ranges and the two-level admission of readings (Capture -> Physical)."""

import pytest

from app.services import reference_ranges
from app.services.clinical_view import assess


def test_haemoglobin_range_depends_on_sex():
    assert reference_ranges.status_label("hemoglobin_g_dl", 12.5, "F") == "NOMINAL"
    assert reference_ranges.status_label("hemoglobin_g_dl", 12.5, "M") == "WATCH"
    assert reference_ranges.status_label("hemoglobin_g_dl", 16.8, "F") == "WATCH"
    assert reference_ranges.status_label("hemoglobin_g_dl", 16.8, "M") == "NOMINAL"


def test_muscle_mass_range_depends_on_sex():
    assert assess("muscle_mass_kg", 22.0, None, "F")[0] == "NOMINAL"
    assert assess("muscle_mass_kg", 22.0, None, "M")[0] == "WARNING"


def test_shared_metrics_ignore_sex():
    for sex in ("F", "M", None):
        assert reference_ranges.status_label("spo2_pct", 98, sex) == "NOMINAL"


def test_skeletal_muscle_index_uses_sex_minimum():
    woman = reference_ranges.smi(20.8, 168.0, "F")
    man = reference_ranges.smi(20.8, 168.0, "M")
    assert woman["value"] == man["value"] == pytest.approx(7.37, abs=0.01)
    assert woman["status"] == "NOMINAL" and woman["min"] == 5.75
    assert man["status"] == "WARNING" and man["min"] == 8.5


def test_every_metric_has_an_admissible_range():
    for entry in reference_ranges.load_reference()["metrics"]:
        assert entry["plausible_min"] is not None, entry["metric_key"]
        assert entry["plausible_max"] > entry["plausible_min"], entry["metric_key"]


def test_help_carries_ranges_by_sex(client):
    items = {i["key"]: i for i in client.get("/api/v1/metrics/help").json()}
    assert items["hemoglobin_g_dl"]["by_sex"]["F"]["nominal_max"] == 16.0
    assert items["hemoglobin_g_dl"]["by_sex"]["M"]["nominal_min"] == 13.5
    assert items["smi_kg_m2"]["summary_en"]
    catalog = {i["metric_key"]: i for i in client.get("/api/v1/metrics/catalog").json()}
    assert catalog["muscle_mass_kg"]["by_sex"]["F"]["nominal_max"] == 24.0
    assert catalog["spo2_pct"]["by_sex"] is None


def _count(client, headers):
    return len(client.get("/api/v1/measurements", headers=headers, params={"limit": 200}).json())


@pytest.mark.parametrize(
    "items",
    [
        [{"metric_key": "spo2_pct", "value_num": 105}],
        [{"metric_key": "body_temp_c", "value_num": 52}],
        [{"metric_key": "body_weight_kg", "value_num": -5}],
        [{"metric_key": "bp_systolic_mmhg", "value_num": 90},
         {"metric_key": "bp_diastolic_mmhg", "value_num": 110}],
        [{"metric_key": "bp_systolic_mmhg", "value_num": 118},
         {"metric_key": "bp_diastolic_mmhg", "value_num": 112}],
        # One impossible value rejects the whole batch: nothing is stored.
        [{"metric_key": "resting_hr_bpm", "value_num": 64},
         {"metric_key": "hydration_ml", "value_num": 9000}],
    ],
)
def test_non_admissible_readings_are_rejected_whole(client, login, items):
    headers = login("ID-01")
    before = _count(client, headers)
    response = client.post("/api/v1/measurements", headers=headers, json={"items": items})
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Non-admissible reading")
    assert _count(client, headers) == before


@pytest.mark.parametrize(
    "items",
    [
        [{"metric_key": "spo2_pct", "value_num": 89}],
        [{"metric_key": "bp_systolic_mmhg", "value_num": 165},
         {"metric_key": "bp_diastolic_mmhg", "value_num": 102}],
        [{"metric_key": "blood_glucose_mg_dl", "value_num": 155}],
    ],
)
def test_abnormal_but_possible_readings_are_stored_with_an_advisory(client, login, items):
    headers = login("ID-04")
    response = client.post("/api/v1/measurements", headers=headers, json={"items": items})
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["inserted_ids"]) == len(items)
    assert body["alerts_created"], "an abnormal reading must raise an advisory"


def test_haemoglobin_advisory_follows_sex(client, login):
    # 12.6 g/dL sits close to both members' own baselines (no personal drift), so only the
    # fixed limit decides: normal for a woman, below the male range for a man.
    woman = client.post(
        "/api/v1/measurements",
        headers=login("ID-03"),
        json={"items": [{"metric_key": "hemoglobin_g_dl", "value_num": 12.6}]},
    )
    man = client.post(
        "/api/v1/measurements",
        headers=login("ID-04"),
        json={"items": [{"metric_key": "hemoglobin_g_dl", "value_num": 12.6}]},
    )
    assert woman.status_code == man.status_code == 201
    assert woman.json()["alerts_created"] == []
    assert man.json()["alerts_created"]


def test_profile_shows_sex_reference_and_muscle_index(client, login):
    profile = client.get("/api/v1/crew/ID-03/profile", headers=login("ID-03")).json()
    assert profile["reference_profile_en"] == "Female ranges"
    muscle = next(c for c in profile["biometrics"] if c["metric_key"] == "muscle_mass_kg")
    assert muscle["smi"]["min"] == 5.75
    blood = next(c for c in profile["labs"] if c["metric_key"] == "hemoglobin_g_dl")
    assert (blood["nominal_min"], blood["nominal_max"]) == (12.0, 16.0)


def test_login_returns_sex(client):
    response = client.post("/api/v1/auth/login", json={"crew_id": "ID-02", "pin": "2084"})
    assert response.json()["crew"]["sex"] == "M"


def test_sex_specific_protocol_is_in_the_guide(client):
    found = client.get("/api/v1/wiki/search", params={"q": "orthostatic"}).json()
    ids = [a["id"] for a in found.get("results", found if isinstance(found, list) else [])]
    assert "wiki-sex-01" in ids
