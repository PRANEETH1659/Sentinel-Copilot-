import os

# Everything defaults to localhost - no cloud accounts, no API keys, no cost.
# Override any of these via a .env file later if you ever move to hosted
# services, but for this project you shouldn't need to.

ES_URL = os.getenv("ES_URL", "http://localhost:9200")
ES_INDEX = os.getenv("ES_INDEX", "security_knowledge_base")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama3.2")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# nomic-embed-text always outputs 768-dimensional vectors. If you ever swap
# to a different embedding model, this number MUST match that model's output
# size, or Elasticsearch will reject every document at index time.
EMBED_DIMS = 768

# How we split long documents before embedding them (see app/ingest.py for why).
CHUNK_SIZE_CHARS = 800
CHUNK_OVERLAP_CHARS = 150
