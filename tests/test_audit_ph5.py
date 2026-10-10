# Checks that audit events are redacted BEFORE they leave the API process.
from app import audit_ph5


class _FakeProducer:
    def __init__(self):
        self.sent = []

    def send(self, topic, value):
        self.sent.append((topic, value))


def test_audit_event_is_redacted(monkeypatch):
    fake = _FakeProducer()
    monkeypatch.setattr(audit_ph5, "_get_producer", lambda: fake)
    audit_ph5.record_audit(
        endpoint="ask",
        question="reset password=hunter2 for priya@acme.com",
        client="127.0.0.1",
        user="analyst1",
        role="analyst",
        status="error",
        error="ES timeout while searching priya@acme.com",
    )
    (_, event), = fake.sent
    assert "hunter2" not in event["question"]
    assert "priya@acme.com" not in event["question"]
    assert "priya@acme.com" not in event["error"]
    assert event["pii_found"] == ["EMAIL", "SECRET"]
    assert event["user"] == "analyst1" and event["role"] == "analyst"


def test_audit_never_raises(monkeypatch):
    def boom():
        raise RuntimeError("broker on fire")
    monkeypatch.setattr(audit_ph5, "_get_producer", boom)
    audit_ph5.record_audit(endpoint="ask", question="q", client="x")  # no exception
