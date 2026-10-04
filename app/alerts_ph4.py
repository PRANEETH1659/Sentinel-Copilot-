# THIS FILE OWNS THE LIVE-ALERTS ELASTICSEARCH INDEX.
#
# Phase 4's consumer (app/consumer_ph4.py) writes every live-ingested alert
# here instead of into the knowledge-base index (config.ES_INDEX) - the same
# separation Phase 3b already used for the semantic cache (app/cache_ph3.py),
# which got its own dedicated index instead of overloading an existing one.
# Keeping alerts in their own index means search_knowledge_base/`/ask`
# (which point at config.ES_INDEX) can never accidentally surface live alert
# text, and search_logs (app/tools_ph2.py) can query just this index.

from elasticsearch import Elasticsearch

from . import config_ph1 as config

ALERTS_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "text": {"type": "text"},
            "embedding": {
                "type": "dense_vector",
                "dims": config.EMBED_DIMS,
                "index": True,
                "similarity": "cosine",
            },
            "source": {"type": "keyword"},
            "chunk_id": {"type": "keyword"},
            "received_at": {"type": "date"},
        }
    }
}


def ensure_alerts_index(es: Elasticsearch) -> None:
    """Creates the live-alerts index if it doesn't exist yet. Called both at
    API startup (see main_ph1.py) and inside the consumer itself (see
    consumer_ph4.py) - safe to call every time, it's a no-op once the index
    is there."""
    if not es.indices.exists(index=config.ES_ALERTS_INDEX):
        es.indices.create(index=config.ES_ALERTS_INDEX, body=ALERTS_INDEX_MAPPING)
