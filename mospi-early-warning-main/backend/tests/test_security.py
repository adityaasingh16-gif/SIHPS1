import os
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB", "dhrishti_test")

from fastapi.testclient import TestClient
from app.main import app
from app.database import mongo_db
from app.security.rate_limiter import rate_limiter

client=TestClient(app)


def setup_function():
    for name in ("security_logs","threat_intelligence","blocked_ips"):
        mongo_db[name].delete_many({})
    rate_limiter.reset()
    rate_limiter.limit=60


def test_nosql_injection_flagged():
    r=client.get("/projects",params={"q":"$ne"})
    assert r.status_code != 500
    doc=mongo_db.threat_intelligence.find_one({"ip_address":"testclient"}) or mongo_db.threat_intelligence.find_one({"ip_address":"127.0.0.1"})
    assert doc and "nosql_injection_attempt" in doc["violation_types"]


def test_blocked_ip_receives_403():
    mongo_db.blocked_ips.insert_one({"ip_address":"testclient","blocked_at":__import__('datetime').datetime.now(__import__('datetime').timezone.utc),"reason":"test","violation_count":5,"expires_at":__import__('datetime').datetime.now(__import__('datetime').timezone.utc)+__import__('datetime').timedelta(hours=1)})
    r=client.get("/")
    assert r.status_code==403


def test_rate_limit_triggers_after_threshold():
    rate_limiter.limit=2
    client.get("/security/unknown-a")
    client.get("/security/unknown-b")
    r=client.get("/security/unknown-c")
    assert r.status_code==429


def test_threats_shape():
    client.get("/projects",params={"q":"$regex"})
    r=client.get("/security/threats")
    assert r.status_code==200
    body=r.json()
    assert {"total","page","page_size","threats"} <= set(body)
    if body["threats"]:
        assert {"ip_address","violation_count","risk_score","violation_types","is_blocked"} <= set(body["threats"][0])
