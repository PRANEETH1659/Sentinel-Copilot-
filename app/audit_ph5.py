# PURPOSE OF THE FILE -- AUDIT TRAIL: one record per question asked.
#
# Every /ask, /ask-agent (and their /stream variants) call publishes a small
# "who asked what, and what happened" event onto its own Redpanda topic
# ('audit-events'). A SEPARATE consumer (app/audit_consumer_ph5.py) files each
# event into the 'audit_log' Elasticsearch index. This is the second
# consumer-style use of Redpanda after Phase 4's alert ingestion: the API
# never waits on the audit write, and adding another reader of the same
# events later (PII redaction, alerting) needs no change here.
#
# Same fail-open contract as the Phase 3 caches: if Redpanda is down, the
# question still gets answered - we log a warning and lose that audit record,
# rather than turning a broker outage into a broken API.
#
# Deliberately NOT stored: the answer text. Only its length. Answers can echo
# alert contents (IPs, hostnames); deciding what is safe to keep is Phase 5b's
# (PII redaction) job, not something to guess at here.

import json
import logging
import threading
import time
from datetime import datetime, timezone

from elasticsearch import Elasticsearch
from kafka import KafkaProducer

from . import config_ph1 as config

log = logging.getLogger("sentinelcopilot.audit")

AUDIT_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "timestamp": {"type": "date"},
            "endpoint": {"type": "keyword"},
            "question": {"type": "text"},
            "client": {"type": "keyword"},
            "status": {"type": "keyword"},  # "ok" | "error"
            "cached": {"type": "boolean"},
            "sources": {"type": "keyword"},
            "answer_chars": {"type": "integer"},
            "duration_ms": {"type": "float"},
            "error": {"type": "text"},
        }
    }
}


def ensure_audit_index(es: Elasticsearch) -> None:
    """Creates the audit index if missing. Called at API startup and inside
    the audit consumer - a no-op once the index exists."""
    if not es.indices.exists(index=config.ES_AUDIT_INDEX):
        es.indices.create(index=config.ES_AUDIT_INDEX, body=AUDIT_INDEX_MAPPING)


# One shared producer for the whole process (building one per request would
# reconnect to the broker every time). Created lazily so importing this
# module never needs Redpanda to be up.
_producer: KafkaProducer | None = None
_producer_lock = threading.Lock()
_retry_after = 0.0  # don't hammer a dead broker: skip attempts until this time
_RETRY_COOLDOWN_SECONDS = 30


def _get_producer() -> KafkaProducer | None:
    global _producer, _retry_after
    if _producer is not None:
        return _producer
    with _producer_lock:
        if _producer is not None:
            return _producer
        if time.monotonic() < _retry_after:
            return None
        try:
            _producer = KafkaProducer(
                bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                max_block_ms=2000,  # never stall a request for long on a dead broker
            )
        except Exception as exc:
            _retry_after = time.monotonic() + _RETRY_COOLDOWN_SECONDS
            log.warning("audit producer unavailable, skipping audit for now: %s", exc)
            return None
        return _producer


def record_audit(
    *,
    endpoint: str,
    question: str,
    client: str,
    status: str = "ok",
    cached: bool = False,
    sources: list[str] | None = None,
    answer_chars: int = 0,
    duration_ms: float = 0.0,
    error: str | None = None,
) -> None:
    """Publishes one audit event. Never raises."""
    try:
        producer = _get_producer()
        if producer is None:
            return
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "question": question,
            "client": client,
            "status": status,
            "cached": cached,
            "sources": sources or [],
            "answer_chars": answer_chars,
            "duration_ms": round(duration_ms, 1),
        }
        if error:
            event["error"] = error
        producer.send(config.KAFKA_AUDIT_TOPIC, value=event)
    except Exception as exc:
        log.warning("failed to record audit event: %s", exc)


def flush_audit() -> None:
    """Called at API shutdown so buffered events aren't lost."""
    if _producer is not None:
        try:
            _producer.flush(timeout=5)
        except Exception as exc:
            log.warning("audit flush failed: %s", exc)
