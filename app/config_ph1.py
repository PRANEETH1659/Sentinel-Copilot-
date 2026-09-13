import os

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
