def _post_measurements(client, headers, items, recorded_at_utc=None):
    body = {"items": items}
    if recorded_at_utc is not None:
        body["recorded_at_utc"] = recorded_at_utc
    return client.post("/api/v1/measurements", headers=headers, json=body)


def test_sandra_amsler_distortion_triggers_alert_and_physician_review(
    client, login, temp_db_path
):
    from app.db import open_connection

    crew_headers = login("ID-04")
    physician_headers = login("ID-03")
    payload = {
        "sandra_test": {
            "milestone": "Mission Day 30",
            "acuity_bilateral": {
                "OD": {
                    "snellen": "20/20",
                    "decimal": "1.00",
                    "logMar": "0.00",
                    "avgResponseTime": "1.10",
                },
                "OS": {
                    "snellen": "20/20",
                    "decimal": "1.00",
                    "logMar": "0.00",
                    "avgResponseTime": "1.15",
                },
                "OU": None,
            },
            "amsler": {
                "OD": {
                    "affectedCount": 4,
                    "metamorphopsiaCount": 4,
                    "scotomaCount": 0,
                    "affectedPercent": 1.0,
                    "hasMetamorphopsia": True,
                    "hasScotoma": False,
                    "hasPerceptualAlert": True,
                    "centralInvolved": False,
                    "status": "warn",
                    "cells": [{"r": 9, "c": 11, "t": "metamorphopsia"}],
                    "perceptual": {
                        "seeCenter": True,
                        "seeCorners": True,
                        "hasWavyLines": True,
                        "hasBlankSpots": False,
                    },
                },
                "OS": {
                    "affectedCount": 0,
                    "metamorphopsiaCount": 0,
                    "scotomaCount": 0,
                    "affectedPercent": 0.0,
                    "hasMetamorphopsia": False,
                    "hasScotoma": False,
                    "hasPerceptualAlert": False,
                    "centralInvolved": False,
                    "status": "ok",
                    "cells": [],
                    "perceptual": {
                        "seeCenter": True,
                        "seeCorners": True,
                        "hasWavyLines": False,
                        "hasBlankSpots": False,
                    },
                },
            },
            "symptoms": {
                "risk_score": 15,
                "risk_level": "OBSERVATION",
                "triage_score": 20,
                "triage_level": "OBSERVATION",
                "active_flags": ["metamorphopsia"],
                "answered_count": 13,
                "total_questions": 13,
                "summary_rows": [
                    {
                        "label": "Subjective Metamorphopsia",
                        "value": "Detected (OD)",
                        "critical": False,
                    }
                ],
            },
        }
    }

    saved = _post_measurements(
        client,
        crew_headers,
        [{"metric_key": "visual_acuity_snellen", "value_num": 20, "payload_json": payload}],
    )
    assert saved.status_code == 201, saved.text
    alert_ids = saved.json()["alerts_created"]
    assert len(alert_ids) == 1

    exam = client.get("/api/v1/vision/ID-04", headers=crew_headers).json()
    assert exam["status"] in ("WARNING", "CRITICAL")
    assert exam["review"]["state"] == "PENDING_REVIEW"
    assert exam["functional_exam"] is not None
    assert exam["functional_exam"]["milestone"] == "Mission Day 30"
    assert exam["functional_exam"]["next_milestone"] == "Mission Day 90"
    assert exam["functional_exam"]["amsler"]["OD"]["hasMetamorphopsia"] is True
    assert exam["functional_exam"]["acuity_bilateral"]["OD"]["snellen"] == "20/20"
    assert exam["functional_exam"]["symptoms"]["risk_level"] == "OBSERVATION"

    with open_connection(temp_db_path) as conn:
        row = conn.execute(
            "SELECT severity, title_en, message_en FROM alerts WHERE id = ?",
            (alert_ids[0],),
        ).fetchone()
    assert row is not None
    assert row["severity"] == "WARNING"
    assert "SANS Visual Battery" in row["title_en"]
    assert "Amsler macular distortion" in row["message_en"]

    review = client.post(
        "/api/v1/vision/ID-04/review",
        headers=physician_headers,
        json={"decision": "APPROVED", "notes_en": "Schedule macular OCT recheck."},
    )
    assert review.status_code == 201, review.text


def test_sandra_acuity_loss_and_diplopia_raise_critical_alert(client, login):
    crew_headers = login("ID-02")
    payload = {
        "sandra_test": {
            "milestone": "Mission Day 90",
            "acuity_bilateral": {
                "OD": {
                    "snellen": "20/40",
                    "decimal": "0.50",
                    "logMar": "0.30",
                    "avgResponseTime": "1.80",
                },
                "OS": {
                    "snellen": "20/25",
                    "decimal": "0.80",
                    "logMar": "0.10",
                    "avgResponseTime": "1.40",
                },
                "OU": None,
            },
            "amsler": {
                "OD": {
                    "affectedCount": 3,
                    "metamorphopsiaCount": 1,
                    "scotomaCount": 2,
                    "affectedPercent": 0.8,
                    "hasMetamorphopsia": True,
                    "hasScotoma": True,
                    "hasPerceptualAlert": True,
                    "centralInvolved": True,
                    "status": "critica",
                    "cells": [{"r": 10, "c": 10, "t": "scotoma"}],
                },
                "OS": {
                    "affectedCount": 0,
                    "metamorphopsiaCount": 0,
                    "scotomaCount": 0,
                    "affectedPercent": 0.0,
                    "hasMetamorphopsia": False,
                    "hasScotoma": False,
                    "hasPerceptualAlert": False,
                    "centralInvolved": False,
                    "status": "ok",
                    "cells": [],
                },
            },
            "symptoms": {
                "risk_score": 52,
                "risk_level": "CRITICAL",
                "triage_score": 68,
                "triage_level": "ALERT",
                "active_flags": ["diplopia", "metamorphopsia"],
                "answered_count": 13,
                "total_questions": 13,
                "summary_rows": [],
            },
        }
    }

    saved = _post_measurements(
        client,
        crew_headers,
        [{"metric_key": "visual_acuity_snellen", "value_num": 40, "payload_json": payload}],
    )
    assert saved.status_code == 201, saved.text
    assert len(saved.json()["alerts_created"]) == 1

    exam = client.get("/api/v1/vision/ID-02", headers=crew_headers).json()
    assert exam["status"] == "CRITICAL"
    assert exam["review"]["state"] == "PENDING_REVIEW"
    assert exam["functional_exam"]["milestone"] == "Mission Day 90"
    assert exam["functional_exam"]["next_milestone"] == "30 Days Before Return"
    assert "diplopia" in exam["functional_exam"]["symptoms"]["active_flags"]

    alerts = client.get("/api/v1/alerts", headers=crew_headers).json()
    titles = [item["title_en"] for item in alerts["items"] if item["kind"] == "ADVISORY"]
    assert any("SANS Visual Battery Alert" in title for title in titles)


def test_sandra_nominal_battery_without_prior_ultrasound(client, login):
    client.post(
        "/api/v1/crew",
        headers=login("ID-02"),
        json={
            "id": "ID-09",
            "code": "ID·09",
            "full_name": "Nova Reyes",
            "role": "ASTRONAUT",
            "pin": "5555",
            "age": 30,
            "sex": "F",
            "height_cm": 165,
        },
    )
    tok = client.post("/api/v1/auth/login", json={"crew_id": "ID-09", "pin": "5555"}).json()
    crew_headers = {"Authorization": f"Bearer {tok['access_token']}"}
    nominal_payload = {
        "sandra_test": {
            "milestone": "Pre-Flight Baseline",
            "acuity_bilateral": {
                "OD": {
                    "snellen": "20/20",
                    "decimal": "1.00",
                    "logMar": "0.00",
                    "avgResponseTime": "0.95",
                },
                "OS": {
                    "snellen": "20/15",
                    "decimal": "1.33",
                    "logMar": "-0.12",
                    "avgResponseTime": "0.90",
                },
                "OU": None,
            },
            "amsler": {
                "OD": {
                    "affectedCount": 0,
                    "metamorphopsiaCount": 0,
                    "scotomaCount": 0,
                    "affectedPercent": 0.0,
                    "hasMetamorphopsia": False,
                    "hasScotoma": False,
                    "hasPerceptualAlert": False,
                    "centralInvolved": False,
                    "status": "ok",
                    "cells": [],
                },
                "OS": {
                    "affectedCount": 0,
                    "metamorphopsiaCount": 0,
                    "scotomaCount": 0,
                    "affectedPercent": 0.0,
                    "hasMetamorphopsia": False,
                    "hasScotoma": False,
                    "hasPerceptualAlert": False,
                    "centralInvolved": False,
                    "status": "ok",
                    "cells": [],
                },
            },
            "symptoms": {
                "risk_score": 0,
                "risk_level": "NOMINAL",
                "triage_score": 0,
                "triage_level": "NOMINAL",
                "active_flags": [],
                "answered_count": 13,
                "total_questions": 13,
                "summary_rows": [],
            },
        }
    }

    saved = _post_measurements(
        client,
        crew_headers,
        [{"metric_key": "visual_acuity_snellen", "value_num": 20, "payload_json": nominal_payload}],
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["alerts_created"] == []

    exam = client.get("/api/v1/vision/ID-09", headers=crew_headers).json()
    assert exam["status"] == "NOMINAL"
    assert exam["review"]["state"] == "NOT_REQUIRED"
    assert exam["exam_at_utc"] is not None
    assert exam["functional_exam"]["milestone"] == "Pre-Flight Baseline"
    assert exam["functional_exam"]["next_milestone"] == "Mission Day 30"


def test_sandra_ignores_phantom_empty_row_after_real_exam(client, login):
    crew_headers = login("ID-04")
    real_payload = {
        "sandra_test": {
            "milestone": "Mission Day 30",
            "acuity_bilateral": {
                "OD": {
                    "snellen": "20/15",
                    "decimal": "1.33",
                    "logMar": "-0.12",
                    "avgResponseTime": "1.20",
                },
                "OS": None,
                "OU": None,
            },
            "amsler": {
                "OD": {
                    "affectedCount": 3,
                    "metamorphopsiaCount": 3,
                    "scotomaCount": 0,
                    "affectedPercent": 0.8,
                    "hasMetamorphopsia": True,
                    "hasScotoma": False,
                    "hasPerceptualAlert": True,
                    "centralInvolved": False,
                    "status": "warn",
                    "cells": [{"r": 1, "c": 13, "t": "metamorphopsia"}],
                },
                "OS": {
                    "affectedCount": 0,
                    "metamorphopsiaCount": 0,
                    "scotomaCount": 0,
                    "affectedPercent": 0.0,
                    "hasMetamorphopsia": False,
                    "hasScotoma": False,
                    "hasPerceptualAlert": False,
                    "centralInvolved": False,
                    "status": "ok",
                    "cells": [],
                },
            },
            "symptoms": {
                "risk_score": 15,
                "risk_level": "OBSERVATION",
                "triage_score": 26,
                "triage_level": "OBSERVATION",
                "active_flags": ["metamorphopsia"],
                "answered_count": 13,
                "total_questions": 13,
                "summary_rows": [],
            },
        }
    }
    phantom_payload = {
        "sandra_test": {
            "milestone": "Mission Day 30",
            "acuity_bilateral": {"OD": None, "OS": None, "OU": None},
            "amsler": {
                "OD": {"affectedCount": 0, "cells": []},
                "OS": {"affectedCount": 0, "cells": []},
            },
            "symptoms": {
                "risk_score": 0,
                "risk_level": "NOMINAL",
                "triage_score": 0,
                "triage_level": "NOMINAL",
                "active_flags": [],
                "answered_count": 1,
                "total_questions": 13,
            },
        }
    }
    _post_measurements(
        client,
        crew_headers,
        [{"metric_key": "visual_acuity_snellen", "value_num": 15, "payload_json": real_payload}],
    )
    _post_measurements(
        client,
        crew_headers,
        [{"metric_key": "visual_acuity_snellen", "value_num": 20, "payload_json": phantom_payload}],
    )
    exam = client.get("/api/v1/vision/ID-04", headers=crew_headers).json()
    assert exam["functional_exam"]["acuity_bilateral"]["OD"]["snellen"] == "20/15"
    assert exam["functional_exam"]["amsler"]["OD"]["affectedCount"] == 3
    assert exam["functional_exam"]["symptoms"]["triage_level"] == "OBSERVATION"


