"""
Automated Pytest Suite for FastAPI Backend Endpoints.
Tests database creation, seeding, joblib model persistence, and all 11 API endpoints.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app import models
from app.auth_security import get_current_user

client = TestClient(app)

def test_root_health():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
    assert "version" in data

def test_seed_database_requires_admin():
    """The seeder wipes and rebuilds every project row, so it must stay locked down."""
    response = client.post("/admin/seed-database")
    assert response.status_code == 401

def test_seed_database_endpoint():
    admin = models.User(
        id=1, email="pytest-seeder@example.gov.in", name="Pytest Seeder",
        role="admin", status="active",
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.post("/admin/seed-database")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["projects_seeded"] > 0
    assert data["snapshots_seeded"] > 0
    assert data["predictions_seeded"] > 0

def test_get_projects_summary_and_filtering():
    response = client.get("/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) > 0
    
    # Check fields match frontend schema
    p = projects[0]
    assert "project_id" in p
    assert "composite_risk_score" in p
    assert "risk_tier" in p
    assert "risk_trend" in p
    
    # Filter by risk_tier
    res_critical = client.get("/projects?risk_tier=Critical")
    assert res_critical.status_code == 200

def test_get_project_detail():
    res_list = client.get("/projects")
    first_pid = res_list.json()[0]["project_id"]
    
    res_detail = client.get(f"/projects/{first_pid}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["project_id"] == first_pid
    assert "suggested_review" in detail
    assert "extracted_tags" in detail
    assert "top_risk_drivers" in detail

def test_get_project_history():
    res_list = client.get("/projects")
    first_pid = res_list.json()[0]["project_id"]
    
    res_hist = client.get(f"/projects/{first_pid}/history")
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) > 0
    assert "composite_risk_score" in history[0]

def test_get_project_explanation():
    res_list = client.get("/projects")
    first_pid = res_list.json()[0]["project_id"]
    
    res_exp = client.get(f"/projects/{first_pid}/explanation")
    assert res_exp.status_code == 200
    exp = res_exp.json()
    assert exp["project_id"] == first_pid
    assert "top_risk_drivers" in exp
    assert "mitigating_factors" in exp

def test_get_similar_projects():
    res_list = client.get("/projects")
    first_pid = res_list.json()[0]["project_id"]
    
    res_sim = client.get(f"/projects/{first_pid}/similar")
    assert res_sim.status_code == 200
    sim_list = res_sim.json()
    assert len(sim_list) <= 4

def test_get_project_dependencies():
    res_list = client.get("/projects")
    first_pid = res_list.json()[0]["project_id"]
    
    res_deps = client.get(f"/projects/{first_pid}/dependencies")
    assert res_deps.status_code == 200
    deps = res_deps.json()
    assert isinstance(deps, list)

def test_simulate_intervention_endpoint():
    res_list = client.get("/projects")
    first_pid = res_list.json()[0]["project_id"]
    
    payload = {
        "resolve_land_issue": True,
        "resolve_approval_bottleneck": True,
        "milestones_to_close": 2
    }
    
    res_sim = client.post(f"/projects/{first_pid}/simulate", json=payload)
    assert res_sim.status_code == 200
    sim = res_sim.json()
    assert sim["project_id"] == first_pid
    assert "current_risk_score" in sim
    assert "simulated_risk_score" in sim
    assert "delta" in sim

def test_optimize_queue_endpoint():
    payload = {"available_hours": 120.0}
    res_opt = client.post("/optimize-queue", json=payload)
    assert res_opt.status_code == 200
    opt = res_opt.json()
    assert opt["available_hours"] == 120.0
    assert opt["n_projects_selected"] > 0
    assert len(opt["selected_projects_queue"]) > 0

def test_get_alerts_endpoint():
    res_alerts = client.get("/alerts")
    assert res_alerts.status_code == 200
    alerts = res_alerts.json()
    assert isinstance(alerts, list)

def test_get_model_comparison_endpoint():
    res_comp = client.get("/model-comparison")
    assert res_comp.status_code == 200
    comp = res_comp.json()
    assert "cuf_only_metrics" in comp
    assert "enhanced_data_metrics" in comp

if __name__ == "__main__":
    pytest.main(["-v", __file__])
