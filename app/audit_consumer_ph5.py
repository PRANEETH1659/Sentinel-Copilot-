# PURPOSE OF THE FILE -- AUDIT CONSUMER: files audit events into Elasticsearch.
#
# Run with: python -u -m app.audit_consumer_ph5
#
# Reads the 'audit-events' topic that app/audit_ph5.py publishes to and
# writes each event, unchanged, into the 'audit_log' index. Its group_id
# differs from Phase 4's alert consumer ("sentinelcopilot-ingest"), so the
# two consumers are independent readers - neither one sees or disturbs the
# other's progress. No embedding or LLM here: an audit log is looked up by
# field (endpoint, time, status), not by meaning.

import json

from kafka import KafkaConsumer

from . import config_ph1 as config
from .audit_ph5 import ensure_audit_index
from .es_client_ph1 import get_client


def get_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        config.KAFKA_AUDIT_TOPIC,
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        # Catch up on events published while this process was offline.
        auto_offset_reset="earliest",
        group_id="sentinelcopilot-audit",
    )


def run_consumer():
    es = get_client()
    ensure_audit_index(es)
    consumer = get_consumer()

    print(f"Listening on topic '{config.KAFKA_AUDIT_TOPIC}'... (Ctrl+C to stop)")
    for message in consumer:
        event = message.value
        es.index(index=config.ES_AUDIT_INDEX, document=event)
        print(
            f"Audited {event.get('endpoint')} status={event.get('status')} "
            f"cached={event.get('cached')}: {str(event.get('question'))[:60]}"
        )


if __name__ == "__main__":
    run_consumer()
