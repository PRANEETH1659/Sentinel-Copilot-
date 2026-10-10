import os

from dotenv import load_dotenv

# Reads a .env file in the project root, if there is one (see .env.example).
# Real environment variables always win over the file.
load_dotenv()

# Everything defaults to localhost - no cloud accounts, no API keys, no cost.
# Override any of these via a .env file later if you ever move to hosted
# services, but for this project you shouldn't need to.

ES_URL = os.getenv("ES_URL", "http://localhost:9200")
ES_INDEX = os.getenv("ES_INDEX", "security_knowledge_base")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen2.5:7b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# nomic-embed-text always outputs 768-dimensional vectors. If you ever swap
# to a different embedding model, this number MUST match that model's output
# size, or Elasticsearch will reject every document at index time.
EMBED_DIMS = 768

# How we split long documents before embedding them (see app/ingest_ph1.py for why).
CHUNK_SIZE_CHARS = 800
CHUNK_OVERLAP_CHARS = 150

# Phase 3 - production hardening
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

# Semantic cache (Phase 3b) - a second, fuzzier cache tier on top of the
# exact-match Redis one. Stores past (question embedding -> answer) pairs in
# their own Elasticsearch index, so a REWORDED repeat of a past question can
# still skip the expensive hybrid-search + LLM-generate path.
ES_CACHE_INDEX = os.getenv("ES_CACHE_INDEX", "qa_cache")

# ES kNN score for cosine similarity is (1 + cosine_similarity) / 2, so this
# lives on a 0-1 scale where 1.0 = identical vectors. Start conservative
# (only near-duplicate phrasing counts as a hit) and tune down if real
# paraphrases you'd expect to hit are missing - too low and unrelated
# questions start sharing answers.
SEMANTIC_CACHE_SCORE_THRESHOLD = float(os.getenv("SEMANTIC_CACHE_SCORE_THRESHOLD", "0.93"))

# Phase 4 - event-driven ingestion
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_ALERTS_TOPIC = os.getenv("KAFKA_ALERTS_TOPIC", "security-alerts")

# Live alerts get their own Elasticsearch index, separate from ES_INDEX (the
# curated knowledge base) - same reasoning as ES_CACHE_INDEX above: a
# dedicated index instead of overloading an existing one. See app/alerts_ph4.py.
ES_ALERTS_INDEX = os.getenv("ES_ALERTS_INDEX", "security_live_alerts")

# Phase 5a - audit logging. Every question asked is published to its own
# Redpanda topic, then filed into its own index by a separate consumer. See
# app/audit_ph5.py.
KAFKA_AUDIT_TOPIC = os.getenv("KAFKA_AUDIT_TOPIC", "audit-events")
ES_AUDIT_INDEX = os.getenv("ES_AUDIT_INDEX", "audit_log")

# Phase 5b - PII redaction (see app/pii_ph5.py). Masks emails, phone numbers,
# Aadhaar/PAN, card numbers, secrets and usernames in anything we STORE
# (audit events, log lines). IPs are masked too by default; set this to
# "false" if your audit reviewers need to see which IP a question was about.
PII_REDACT_IPS = os.getenv("PII_REDACT_IPS", "true").lower() == "true"

# Phase 5c - RBAC (see app/auth_ph5.py). Comma-separated key:user:role
# entries, e.g. "k3y-aaa:priya:analyst,k3y-bbb:praneeth:admin".
# Roles: analyst (ask questions), admin (ask + read the audit log).
# Left empty, the API falls back to built-in DEV keys and logs a warning.
API_KEYS = os.getenv("API_KEYS", "")
