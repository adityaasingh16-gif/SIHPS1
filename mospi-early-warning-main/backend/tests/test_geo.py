"""Tests for state normalisation and the public geography endpoint.

The normaliser is worth testing directly because the panel's state column is
malformed in three independent ways, and each has a failure mode that would
silently corrupt a map: a CRLF-wrapped value matches nothing, a composite
value could be read as a single state, and a non-place value could be pinned
to a point in the sea.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.geo import (  # noqa: E402
    STATE_REFERENCE,
    code_for,
    coordinates_for,
    is_mappable,
    multi_state_members,
    normalise_state,
)


class TestNormaliseState:
    def test_plain_name_passes_through(self):
        assert normalise_state("Maharashtra") == "Maharashtra"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Assam", "Assam"),
            ("  Assam  ", "Assam"),
            ("Assam\r\n", "Assam"),
            ("\r\nAssam\r\n", "Assam"),
            ("Jammu and\r\nKashmir", "Jammu and Kashmir"),
            ("DADRA AND NAGAR HAVELI", "Dadra and Nagar Haveli and Daman and Diu"),
        ],
    )
    def test_whitespace_and_case_are_normalised(self, raw, expected):
        assert normalise_state(raw) == expected

    def test_every_state_in_the_reference_table_round_trips(self):
        """The table must not contain a name the normaliser cannot recover."""
        for name in STATE_REFERENCE:
            assert normalise_state(name) == name, name

    def test_crlf_multiline_value_is_not_left_as_a_fragment(self):
        """The exact shape found in the panel file."""
        raw = "Multi-States (Arunachal\r\nPradesh, Assam)"
        result = normalise_state(raw)
        assert "\r" not in result and "\n" not in result
        assert result == "Multi-State"

    def test_alias_resolves_ampersand_abbreviation(self):
        """A generic &-to-and swap cannot reach the `Islands` suffix."""
        assert normalise_state("Andaman &\r\nNicobar") == "Andaman and Nicobar Islands"

    def test_single_member_composite_collapses_to_that_state(self):
        assert normalise_state("Multi-States (Delhi)") == "Delhi"

    def test_multi_state_is_never_attributed_to_first_listed_state(self):
        """Attributing to the first member would be a fabrication."""
        assert normalise_state("Multi-States (Assam,\r\nManipur)") == "Multi-State"

    @pytest.mark.parametrize("raw", ["Offshore", "offshore", " PAN India ", "pan-india"])
    def test_non_place_values_get_their_own_buckets(self, raw):
        assert normalise_state(raw) in {"Offshore", "PAN India"}
        assert not is_mappable(normalise_state(raw))

    @pytest.mark.parametrize("raw", ["", None, "   ", "Atlantis"])
    def test_empty_and_unknown_become_unspecified(self, raw):
        assert normalise_state(raw) == "Unspecified"

    def test_buckets_are_never_mappable(self):
        for bucket in ("Multi-State", "Offshore", "PAN India", "Unspecified"):
            assert not is_mappable(bucket)
            assert coordinates_for(bucket) is None
            assert code_for(bucket) is None


class TestReferenceTable:
    def test_lookup_returns_coordinates(self):
        lat, lon = coordinates_for("Maharashtra")
        assert 6.0 < lat < 37.0, "India's latitudes"
        assert 68.0 < lon < 98.0, "India's longitudes"

    def test_every_mappable_state_has_a_centroid_and_code(self):
        for name in STATE_REFERENCE:
            lat, lon = coordinates_for(name)
            code = code_for(name)
            assert lat is not None and lon is not None, name
            assert code and len(code) == 2, name

    def test_codes_are_unique(self):
        codes = [code for code, _, _ in STATE_REFERENCE.values()]
        assert len(codes) == len(set(codes))

    def test_table_is_indias_states_and_territories(self):
        assert len(STATE_REFERENCE) == 36  # 28 states + 8 union territories


class TestMultiStateMembers:
    def test_members_are_extracted_and_deduplicated(self):
        raw = "Multi-States (Assam,\r\nManipur, Meghalaya,\r\nMizoram)"
        assert multi_state_members(raw) == ["Assam", "Manipur", "Meghalaya", "Mizoram"]

    def test_repeated_members_collapse(self):
        assert multi_state_members("Multi-States (Assam, Assam)") == ["Assam"]

    def test_non_composite_values_have_no_members(self):
        assert multi_state_members("Maharashtra") == []
        assert multi_state_members("Offshore") == []

    def test_unrecognised_member_is_dropped_not_invented(self):
        assert multi_state_members("Multi-States (Assam, Atlantis)") == ["Assam"]


class TestStateGeoEndpoint:
    """Exercises the endpoint against a throwaway database, never the live one."""

    @pytest.fixture()
    def client(self, tmp_path, monkeypatch):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.database import Base, get_db
        from app import models
        from app.routers import public as public_router

        eng = create_engine(
            f"sqlite:///{tmp_path/'geo_test.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(eng)
        Session = sessionmaker(bind=eng)
        db = Session()

        # Two visible projects, one withheld, so the privacy filter is provable.
        db.add(models.ProjectPublicRow(
            project_id="P1", is_public_visible=1, sector="Roads", ministry="MoRTH",
            status="Ongoing", completion_percent=50.0, on_track=1,
            risk_tier_label="Low", public_summary="",
        ))
        db.add(models.ProjectPublicRow(
            project_id="P2", is_public_visible=1, sector="Power", ministry="MoP",
            status="Ongoing", completion_percent=20.0, on_track=0,
            risk_tier_label="High", public_summary="",
        ))
        db.add(models.ProjectPublicRow(
            project_id="HIDDEN", is_public_visible=0, sector="Defence",
            ministry="MoD", status="Ongoing", completion_percent=1.0, on_track=0,
            risk_tier_label="High", public_summary="",
        ))
        db.add(models.ProjectGeo(
            project_id="P1", state="Maharashtra", state_code="MH",
            lat=19.7515, lon=75.7139, precision="state", geo_source="panel_csv",
        ))
        db.add(models.ProjectGeo(
            project_id="P2", state="Maharashtra", state_code="MH",
            lat=19.7515, lon=75.7139, precision="state", geo_source="panel_csv",
        ))
        db.add(models.ProjectPublicRow(
            project_id="P3", is_public_visible=1, sector="Railways", ministry="MoR",
            status="Ongoing", completion_percent=35.0, on_track=1,
            risk_tier_label="Medium", public_summary="",
        ))
        db.add(models.ProjectGeo(
            project_id="HIDDEN", state="Kerala", state_code="KL",
            lat=10.8505, lon=76.2711, precision="state", geo_source="panel_csv",
        ))
        # Visible, but names no single state: must surface as a bucket with no
        # coordinates rather than being dropped or pinned to a guessed point.
        db.add(models.ProjectGeo(
            project_id="P3", state="Multi-State", state_code=None,
            lat=None, lon=None, precision="none", member_count=4,
            geo_source="panel_csv",
        ))
        db.commit()

        # The router has to be mounted on an app before dependency_overrides
        # exists: overrides live on the app, not on an APIRouter.
        app = FastAPI()
        app.include_router(public_router.router)
        app.dependency_overrides[get_db] = lambda: db
        yield TestClient(app), db
        app.dependency_overrides.clear()
        db.close()

    def test_only_visible_projects_are_counted(self, client):
        tc, _ = client
        body = tc.get("/public/geo/states").json()
        assert body["total_projects"] == 3, "the withheld project must not appear"
        assert "Kerala" not in [s["state"] for s in body["states"]]

    def test_state_figures_sum_to_the_row_count(self, client):
        tc, _ = client
        body = tc.get("/public/geo/states").json()
        assert body["states"][0]["project_count"] == 2
        assert body["states"][0]["on_track_count"] == 1
        assert body["states"][0]["delayed_count"] == 1

    def test_unplaced_projects_are_reported_not_dropped(self, client):
        tc, _ = client
        body = tc.get("/public/geo/states").json()
        assert body["unplaced"] == [
            {"bucket": "Multi-State", "project_count": 1}
        ]
        attributed = body["state_attributed_projects"] + sum(
            b["project_count"] for b in body["unplaced"]
        )
        assert (
            attributed == body["total_projects"]
        ), "coverage must account for every project"

    def test_response_does_not_claim_project_locations(self, client):
        """The response must not use wording that implies site-level knowledge.

        These projects carry a state centroid. A field named `located_*` would
        invite a reader to conclude 1,947 project locations are known, when the
        1,947 collapse to 35 distinct points.
        """
        tc, _ = client
        body = tc.get("/public/geo/states").json()
        assert "located_projects" not in body
        assert "located_share_percent" not in body
        assert "state_attributed_projects" in body
        assert "state_attributed_share_percent" in body
        # The per-state field was always equal to project_count, so removing it
        # cannot change the arithmetic.
        for state in body["states"]:
            assert "located_count" not in state

    def test_centroid_is_labelled_as_such(self, client):
        tc, _ = client
        state = tc.get("/public/geo/states").json()["states"][0]
        assert state["precision"] == "state", "must not claim project-level precision"
