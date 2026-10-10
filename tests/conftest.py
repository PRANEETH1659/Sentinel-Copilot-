# Shared test setup. No real Redpanda here: audit events go to a fake
# producer the tests can inspect, instead of waiting on a 2s broker timeout.
import pytest

from app import audit_ph5


class FakeProducer:
    def __init__(self):
        self.sent = []

    def send(self, topic, value):
        self.sent.append(value)


@pytest.fixture
def audit_events(monkeypatch):
    fake = FakeProducer()
    monkeypatch.setattr(audit_ph5, "_get_producer", lambda: fake)
    return fake.sent
