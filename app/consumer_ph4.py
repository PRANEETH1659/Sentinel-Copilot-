# PURPOSE OF THE FILE -- CONSUMER: the automatic version of ingest_ph1.run_ingest().
#
# Instead of you running `python -m app.ingest_ph1` by hand, this script sits
# and waits on the 'security-alerts' topic. The moment a new alert lands on
# it, this does the exact same three steps ingest_ph1 does for files - chunk,
# embed, store in Elasticsearch - just triggered by a queued message instead
# of a manual command. No LLM involved here; this is pure filing, same as
# Phase 1. The LLM only gets involved later, when /ask is actually called.

import json
import time

from kafka import KafkaConsumer

from . import config_ph1 as config
from .embeddings_ph1 import embed_text
from .es_client_ph1 import ensure_index, get_client
from .ingest_ph1 import chunk_text


def get_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        config.KAFKA_ALERTS_TOPIC,
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        # "earliest" = if this consumer was offline when an alert arrived,
        # catch up on it instead of skipping straight to whatever's newest.
        auto_offset_reset="earliest",
        # Consumers sharing a group_id split the work and never reprocess
        # each other's messages. One consumer for now - this just makes
        # adding more workers later a config change, not a rewrite.
        group_id="sentinelcopilot-ingest",
    )


def run_consumer():
    es = get_client()
    ensure_index(es)
    consumer = get_consumer()

    print(f"Listening on topic '{config.KAFKA_ALERTS_TOPIC}'... (Ctrl+C to stop)")
    for message in consumer:
        alert = message.value
        text = alert["text"]
        source = alert.get("source", "live-alert")
        received_at = alert.get("timestamp", time.time())

        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            vector = embed_text(chunk)
            es.index(
                index=config.ES_INDEX,
                document={
                    "text": chunk,
                    "embedding": vector,
                    "source": source,
                    "chunk_id": f"{source}::{received_at}::{i}",
                },
            )
        es.indices.refresh(index=config.ES_INDEX)
        print(f"Ingested alert from '{source}' ({len(chunks)} chunk(s)): {text[:80]}")


if __name__ == "__main__":
    run_consumer()
