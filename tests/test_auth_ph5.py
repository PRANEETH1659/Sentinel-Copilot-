# Phase 5c tests. TestClient used WITHOUT `with`, so FastAPI's startup hook
# (which connects to Elasticsearch) never runs - no live services needed.
import pytest
from fastapi.testclient import TestClient

from app import main_ph1
from app.auth_ph5 import parse_api_keys

ANALYST = {"X-API-Key": "dev-analyst-key"}
ADMIN = {"X-API-Key": "dev-admin-key"}

client = TestClient(main_ph1.app)


@pytest.fixture
def cached_answers(monkeypatch):
    """Make /ask answer from a fake cache, so no Redis/ES/Ollama is touched."""
    monkeypatch.setattr(main_ph1, "get_redis_client", lambda: None)
    monkeypatch.setattr(
        main_ph1, "get_cached_answer",
        lambda _r, _e, _q: {"answer": "isolate the host", "sources": ["runbook.txt"]},
    )


class FakeES:
    def search(self, **kwargs):
        self.kwargs = kwargs
        return {"hits": {"hits": [{"_source": {"endpoint": "ask", "status": "ok"}}]}}


def test_health_is_public():
    assert client.get("/health").status_code == 200


def test_no_key_is_401_and_audited(audit_events):
    r = client.post("/ask", json={"question": "hi"})
    assert r.status_code == 401
    assert audit_events[-1]["status"] == "denied"
    assert audit_events[-1]["user"] == "anonymous"


def test_wrong_key_is_401(audit_events):
    r = client.post("/ask", json={"question": "hi"}, headers={"X-API-Key": "guess"})
    assert r.status_code == 401


def test_analyst_can_ask(audit_events, cached_answers):
    r = client.post("/ask", json={"question": "ransomware steps?"}, headers=ANALYST)
    assert r.status_code == 200
    assert r.json()["cached"] is True
    ev = audit_events[-1]
    assert (ev["user"], ev["role"], ev["status"]) == ("analyst1", "analyst", "ok")


def test_whoami():
    assert client.get("/whoami", headers=ADMIN).json() == {"user": "admin1", "role": "admin"}


def test_analyst_cannot_read_audit(audit_events):
    r = client.get("/audit", headers=ANALYST)
    assert r.status_code == 403
    ev = audit_events[-1]
    assert ev["status"] == "denied" and ev["user"] == "analyst1"


def test_admin_reads_audit_with_filters(monkeypatch, audit_events):
    es = FakeES()
    monkeypatch.setattr(main_ph1, "get_es_client", lambda: es)
    r = client.get("/audit?status=denied&limit=5", headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["count"] == 1
    assert es.kwargs["size"] == 5
    assert es.kwargs["query"] == {"bool": {"filter": [{"term": {"status": "denied"}}]}}


def test_parse_api_keys_rejects_typos():
    assert parse_api_keys("k1:priya:analyst")
    with pytest.raises(ValueError):
        parse_api_keys("k1:priya:superuser")   # unknown role
    with pytest.raises(ValueError):
        parse_api_keys("k1:priya")             # missing role
