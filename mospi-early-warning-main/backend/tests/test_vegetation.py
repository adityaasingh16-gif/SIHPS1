"""Tests for the satellite vegetation endpoint.

The interesting assertions here are about honesty rather than arithmetic. A
vegetation figure that is easy to misread as per-project monitoring is a worse
outcome than having no figure at all, so the guarantees that the data cannot
be presented as project-level, and that a requested date is never silently
replaced, are tested directly.
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app
from app.vegetation import flag_low_outliers

TODAY = date(2026, 8, 29)
EARLIER = date(2026, 7, 12)
LAYER = "MODIS_Terra_L3_EVI_16Day"


@pytest.fixture()
def client_and_db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path/'veg.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(
        engine,
        tables=[
            models.StateVegetation.__table__,
            # The endpoint joins project_geo to attach state codes, so the
            # fixture has to provide it even though these tests never insert
            # a geography row.
            models.ProjectGeo.__table__,
        ],
    )
    Session = sessionmaker(bind=engine)
    db = Session()
    for state, evi, outlier in [
        ("Uttar Pradesh", 0.55, False),
        ("Madhya Pradesh", 0.51, False),
        ("Kerala", 0.33, False),
        ("Ladakh", 0.07, True),
    ]:
        db.add(models.StateVegetation(
            state=state,
            acquisition_date=TODAY,
            evi_mean=evi,
            evi_median=evi,
            evi_p10=evi - 0.1,
            evi_p90=evi + 0.1,
            ndvi_median=evi + 0.2,
            valid_pixel_fraction=0.95,
            tiles_sampled=9,
            source_layer=LAYER,
            resolution_m=250,
            status="ok",
            low_outlier=outlier,
        ))
    # An earlier acquisition so trends have something to span.
    for state, evi in [("Uttar Pradesh", 0.40), ("Madhya Pradesh", 0.30),
                       ("Kerala", 0.36), ("Ladakh", 0.06)]:
        db.add(models.StateVegetation(
            state=state,
            acquisition_date=EARLIER,
            evi_mean=evi, evi_median=evi,
            evi_p10=evi - 0.1, evi_p90=evi + 0.1,
            ndvi_median=evi + 0.2,
            valid_pixel_fraction=0.90, tiles_sampled=9,
            source_layer=LAYER,
            resolution_m=250, status="ok",
        ))
    db.commit()

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app), db, Session
    app.dependency_overrides.pop(get_db, None)
    db.close()


# --- date selection ---------------------------------------------------------

def test_defaults_to_latest_acquisition(client_and_db):
    client, _, _ = client_and_db
    r = client.get("/public/geo/vegetation")
    assert r.status_code == 200
    body = r.json()
    assert body["selected_date"] == TODAY.isoformat()
    assert body["dates"][-1]["is_latest"] is True


def test_requested_date_is_honoured(client_and_db):
    client, _, _ = client_and_db
    body = client.get("/public/geo/vegetation", params={"date": EARLIER}).json()
    assert body["selected_date"] == EARLIER.isoformat()
    up = next(s for s in body["states"] if s["state"] == "Uttar Pradesh")
    assert up["evi_median"] == pytest.approx(0.40)


def test_unmeasured_date_falls_back_and_says_so(client_and_db):
    """A date that was never measured must not be quietly swapped.

    Returning the latest acquisition is reasonable; returning it while
    labelling it as the requested date is not, so the fallback is stated in
    the limitations and the date actually used comes back in selected_date.
    """
    client, _, _ = client_and_db
    body = client.get("/public/geo/vegetation", params={"date": "2026-06-26"}).json()
    assert body["selected_date"] == TODAY.isoformat()
    assert any("2026-06-26" in lim and "most recent" in lim
               for lim in body["limitations"])


def test_malformed_date_does_not_crash(client_and_db):
    client, _, _ = client_and_db
    r = client.get("/public/geo/vegetation", params={"date": "not-a-date"})
    assert r.status_code == 200
    assert r.json()["selected_date"] == TODAY.isoformat()


# --- honesty guarantees -----------------------------------------------------

def test_scope_is_state_and_no_project_fields(client_and_db):
    """No project identifier may appear in the payload.

    This is the assertion that keeps the feature from drifting into
    per-project satellite monitoring, which the underlying data cannot support.
    """
    client, _, _ = client_and_db
    body = client.get("/public/geo/vegetation").json()
    assert body["scope"] == "state"
    for state in body["states"]:
        for banned in ("project_id", "project_count", "cost", "risk_score"):
            assert banned not in state
    assert body["limitations"], "limitations must accompany the measurement"


def test_limitations_state_the_known_biases(client_and_db):
    client, _, _ = client_and_db
    text = " ".join(client.get("/public/geo/vegetation").json()["limitations"]).lower()
    assert "not project-level" in text or "state-level only" in text
    assert "cloud" in text
    assert "water" in text


def test_low_outlier_is_reported_not_silently_dropped(client_and_db):
    client, _, _ = client_and_db
    body = client.get("/public/geo/vegetation").json()
    ladakh = next(s for s in body["states"] if s["state"] == "Ladakh")
    assert ladakh["low_outlier"] is True
    assert ladakh["outlier_note"]
    # The note must not assert a cause the data cannot support.
    assert "cause not determined" in ladakh["outlier_note"].lower()


def test_valid_pixel_fraction_is_surfaced(client_and_db):
    client, _, _ = client_and_db
    body = client.get("/public/geo/vegetation").json()
    up = next(s for s in body["states"] if s["state"] == "Uttar Pradesh")
    assert up["valid_pixel_fraction"] == pytest.approx(0.95)
    assert up["tiles_sampled"] == 9


# --- trends -----------------------------------------------------------------

def test_trends_report_rate_per_month(client_and_db):
    client, _, _ = client_and_db
    body = client.get("/public/geo/vegetation").json()
    up = next(t for t in body["trends"] if t["state"] == "Uttar Pradesh")
    assert len(up["points"]) == 2
    assert up["change_over_series"] == pytest.approx(0.15, abs=1e-3)
    # 0.15 over 48 days must be expressed as a monthly rate, not left as a
    # raw difference that would look like a 0.15 monthly figure.
    assert 0.08 < up["change_per_month"] < 0.13


def test_trends_can_be_disabled(client_and_db):
    client, _, _ = client_and_db
    body = client.get("/public/geo/vegetation", params={"trend": "false"}).json()
    assert body["trends"] == []


# --- the outlier heuristic itself ------------------------------------------

def test_low_outlier_flags_only_the_tail():
    obs = [
        {"state": f"S{i}", "status": "ok", "evi_state_median": v}
        for i, v in enumerate([0.50, 0.51, 0.52, 0.53, 0.54, 0.55, 0.56, 0.57])
    ] + [
        {"state": "Ladakh", "status": "ok", "evi_state_median": 0.07},
        {"state": "Jammu and Kashmir", "status": "ok", "evi_state_median": 0.07},
    ]
    flagged = flag_low_outliers(obs)
    assert "Ladakh" in flagged
    assert "S0" not in flagged


def test_outlier_check_declines_when_too_few_states():
    """With too few states there is no notion of 'normal for this date'."""
    obs = [{"state": "A", "status": "ok", "evi_state_median": 0.1},
           {"state": "B", "status": "ok", "evi_state_median": 0.5}]
    assert flag_low_outliers(obs) == set()
    assert all(o["low_outlier"] is False for o in obs)


def test_outlier_note_does_not_claim_cloud():
    obs = [{"state": f"S{i}", "status": "ok", "evi_state_median": 0.5}
           for i in range(9)]
    obs.append({"state": "Ladakh", "status": "ok", "evi_state_median": 0.07})
    flag_low_outliers(obs)
    note = obs[-1]["outlier_note"].lower()
    # "cloud" may appear as one of several possibilities but never as a verdict.
    assert "cause not determined" in note
    assert "suspected cloud" not in note

