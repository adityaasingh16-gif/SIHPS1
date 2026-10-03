"""Tests for the public ministry and sector aggregates.

The page these serve used to read a hardcoded list of three ministries with an
invented "health" score. These tests exist to make that impossible to restore
quietly: every figure must be an aggregate of the public projection, the group
counts must account for the whole visible portfolio, and a withheld project must
not leak in through the cost join.
"""

import os
import sys
from datetime import date as date_cls

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestMinistriesEndpoint:
    """Runs against a throwaway database, never the live one."""

    @pytest.fixture()
    def client(self, tmp_path):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.database import Base, get_db
        from app import models
        from app.routers import public as public_router

        eng = create_engine(
            f"sqlite:///{tmp_path/'ministries_test.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(eng)
        Session = sessionmaker(bind=eng)
        db = Session()

        def add(pid, ministry, sector, visible, on_track, cost, comp):
            db.add(models.Project(
                project_id=pid, sector=sector, ministry=ministry,
                implementing_agency=f"{ministry} HQ",
                original_cost_crore=cost, original_duration_months=24,
                start_date=date_cls(2024, 1, 1),
                planned_completion_date=date_cls(2026, 1, 1),
                status="Ongoing",
            ))
            db.add(models.ProjectPublicRow(
                project_id=pid, is_public_visible=visible, sector=sector,
                ministry=ministry, status="Ongoing", completion_percent=comp,
                on_track=on_track, risk_tier_label="Low", public_summary="",
            ))

        # MoRTH: two projects, 100 + 50 crore, one on track, spans two sectors.
        add("A1", "MoRTH", "Roads", 1, 1, 100.0, 60.0)
        add("A2", "MoRTH", "Bridges", 1, 0, 50.0, 20.0)
        # MoP: one project with a recorded cost.
        add("B1", "MoP", "Power", 1, 1, 70.0, 40.0)
        # Visible in the public projection but absent from the raw projects
        # table. `projects.original_cost_crore` is NOT NULL, so this is the only
        # way to reach the "cost unknown" path -- and an inner join would drop
        # the row entirely, breaking the totals.
        db.add(models.ProjectPublicRow(
            project_id="ORPHAN", is_public_visible=1, sector="Ports",
            ministry="MoPSW", status="Ongoing", completion_percent=15.0,
            on_track=0, risk_tier_label="High", public_summary="",
        ))
        # Withheld: must not appear in any group, nor contribute cost.
        add("HIDDEN", "MoD", "Defence", 0, 0, 999.0, 1.0)
        db.commit()

        app = FastAPI()
        app.include_router(public_router.router)
        app.dependency_overrides[get_db] = lambda: db
        yield TestClient(app), db
        app.dependency_overrides.clear()
        db.close()

    def _body(self, client):
        tc, _ = client
        r = tc.get("/public/ministries")
        assert r.status_code == 200
        return r.json()

    def test_lists_every_ministry_and_sector_present(self, client):
        body = self._body(client)
        assert body["total_ministries"] == 3
        assert body["total_sectors"] == 4
        assert [m["name"] for m in body["ministries"]] == ["MoRTH", "MoP", "MoPSW"]
        # Every sector has exactly one project here, so the tie-break is the
        # name, not the count.
        assert sorted(s["name"] for s in body["sectors"]) == [
            "Bridges", "Ports", "Power", "Roads",
        ]

    def test_aggregates_are_computed_not_stored(self, client):
        m = {x["name"]: x for x in self._body(client)["ministries"]}["MoRTH"]
        assert m["project_count"] == 2
        assert m["on_track_count"] == 1
        assert m["delayed_count"] == 1
        assert m["on_track_share_percent"] == 50.0
        assert m["total_original_cost_crore"] == 150.0
        # Mean of 60 and 20.
        assert m["avg_completion_percent"] == 40.0

    def test_missing_cost_is_null_not_zero(self, client):
        """A project with no cost record is 'unknown', not free.

        The ORPHAN row is public and visible but has no `projects` row, so it
        must still be counted as a project while reporting a null cost. If it
        were dropped instead, the group totals would silently undercount.
        """
        groups = {m["name"]: m for m in self._body(client)["ministries"]}
        mopsw = groups["MoPSW"]
        assert mopsw["project_count"] == 1, "must be counted, not dropped"
        assert mopsw["total_original_cost_crore"] is None
        assert mopsw["avg_completion_percent"] == 15.0

    def test_cost_coverage_reports_the_gap(self, client):
        body = self._body(client)
        # 3 of 4 visible projects carry a cost.
        assert body["cost_coverage_percent"] == 75.0

    def test_withheld_project_is_excluded_even_though_cost_is_joined(self, client):
        """The cost join must not become a privacy leak.

        `projects` has no visibility flag, so the endpoint joins it for
        original_cost_crore. If the visibility filter were dropped from that
        join, MoD would appear with its withheld cost.
        """
        body = self._body(client)
        names = [m["name"] for m in body["ministries"]]
        assert "MoD" not in names
        assert "Defence" not in [s["name"] for s in body["sectors"]]
        assert body["total_projects"] == 4
        assert body["unattributed_projects"] == 0
        total_cost = sum(
            m["total_original_cost_crore"] or 0 for m in body["ministries"]
        )
        assert total_cost == 220.0, "withheld cost must not be summed in"

    def test_ministry_totals_account_for_every_project(self, client):
        body = self._body(client)
        by_ministry = sum(m["project_count"] for m in body["ministries"])
        by_sector = sum(s["project_count"] for s in body["sectors"])
        assert by_ministry == body["total_projects"]
        assert by_sector == body["total_projects"]

    def test_ministry_lists_its_sectors(self, client):
        m = {x["name"]: x for x in self._body(client)["ministries"]}["MoRTH"]
        assert m["child_sectors"] == ["Bridges", "Roads"]
        assert m["kind"] == "ministry"

    def test_no_invented_health_score(self, client):
        """The old mock had a 'health' number with no basis in the data."""
        for group in ("ministries", "sectors"):
            for item in self._body(client)[group]:
                assert "health" not in item

    def test_sorted_by_portfolio_size(self, client):
        m = self._body(client)["ministries"]
        assert [x["project_count"] for x in m] == sorted(
            (x["project_count"] for x in m), reverse=True
        )
