# SentinelCopilot — Full Build Log (Phases 1–4)

Sequential, oldest first. Each entry: **Change → Purpose → Content**.
Phase 5 (governance and deployment) has not started.

---

# Phase 1 — Hybrid RAG Core

## 2026-08-21 — Initial commit (`ad4913e`)
- **Change:** Built the hybrid RAG pipeline: `config`, `embeddings`, `es_client`, `ingest`, `rag`, `main` (FastAPI `/ask`), `docker-compose.yml` (Elasticsearch), and 3 fictional `sample_docs/`.
- **Purpose:** Answer security questions grounded in documents instead of the model's memory.
- **Content:**
  - Documents are chunked and embedded with Ollama `nomic-embed-text`, then stored in Elasticsearch.
  - Search runs BM25 (keyword) and kNN (vector), merged with Reciprocal Rank Fusion.
  - `llama3.2` writes the answer from the retrieved chunks and returns its sources.
  - Verified: 11 chunks indexed, and `/ask` returned a grounded answer for "What is the ransomware runbook about?".

---

# Phase 2 — Agent Orchestration

## 2026-08-21 — Phase 2 agent (in `ad4913e`, docs in `abdf072`)
- **Change:** Added `agent_ph2.py` (LangGraph `think`/`act` loop), `tools_ph2.py` (`search_knowledge_base`, `search_logs`), `sample_logs/mock_logs.json`, and the `/ask-agent` endpoint.
- **Purpose:** Let the model choose which tool fits the question instead of always running one fixed search.
- **Content:**
  - `search_knowledge_base` wraps Phase 1 retrieval unchanged.
  - `search_logs` reads 8 mock log lines.
  - `/ask` and `/ask-agent` sit side by side so they can be compared.

## 2026-08-22 — Docs sync and GitHub push (`6800de7`)
- **Change:** Updated `PROGRESS.md` and the README, ran a secrets audit, and pushed to GitHub.
- **Purpose:** The docs had described the agent as future work after it was built.
- **Content:** 19 files, no secrets found, and `.gitignore` confirmed working.

## 2026-08-28 — File naming refactor (`f528ad2`)
- **Change:** Renamed every `app/*.py` file to carry a `_ph<N>` suffix (for example `main.py` became `main_ph1.py`), using `git mv`.
- **Purpose:** Show at a glance which phase created each file.
- **Content:**
  - The suffix marks where a file was born, not where it was last edited.
  - It must be `_ph2`, not `_ph-2`, because a hyphen is illegal in a Python module name.
  - Commands changed: `python -m app.ingest_ph1` and `uvicorn app.main_ph1:app`.

## 2026-08-28 — Agent hallucination fix (`8163efa`)
- **Change:** Prompt and routing fix in the agent.
- **Purpose:** Stop the agent from claiming events it had never checked in the logs.
- **Content:** The agent now says what the logs do and don't show.

## 2026-09-11 — Compound tool-calling fix (`a530c17`)
- **Change:**
  - Default `CHAT_MODEL` moved from `llama3.2` to `qwen2.5:7b`.
  - `search_logs` now splits the keyword on whitespace and requires every word to match (AND).
- **Purpose:**
  - `llama3.2` (3B) skipped `search_logs` on compound questions and asserted unverified facts.
  - The old whole-string match gave false "no log entries" results for multi-word queries.
- **Content:**
  - `qwen2.5:7b` routed 3/3 test questions correctly: knowledge base only, logs only, and both tools in order.
  - `/ask` was re-checked and showed no regression.
  - Known quirk: `sources` can include a related but different runbook (existing retrieval behaviour).

---

# Phase 3 — Production Hardening

## 2026-09-11 — Caching, tracing, streaming (`c497453`)
- **Change:** Added `cache_ph3.py` (Redis), `tracing_ph3.py` (`Trace`), a `redis` service in docker-compose, `/ask/stream` and `/ask-agent/stream` (SSE), a `timings` field, a `cached` field, and an `X-Process-Time` header.
- **Purpose:** Local LLM calls take about 68–168s, so repeats should be instant and first calls should feel shorter.
- **Content:**
  - The cache key is endpoint + question + model, so swapping models can't serve stale answers.
  - The cache fails open: if Redis is down, the API recomputes instead of breaking.
  - Tracing is a plain per-request timings dict, not OpenTelemetry.
  - Streaming endpoints bypass the cache on purpose.
  - Verified: a repeat call returned in 0.26s instead of about 71s, and tokens arrived incrementally.

## 2026-09-13 — Docs and GitHub push (`b0a1158`)
- **Change:** Secrets audit, pushed 4 commits, and added Phase 3 notes.
- **Purpose:** Keep the remote and the docs in sync.
- **Content:** No secrets found (the only "token" hits were LLM output tokens).

## 2026-09-13 — Phase 3b semantic cache (`f9f6d30`)
- **Change:** Added a second cache tier backed by a new Elasticsearch `qa_cache` index (kNN on question embeddings), `ensure_cache_index()` called on startup, and config `ES_CACHE_INDEX` and `SEMANTIC_CACHE_SCORE_THRESHOLD=0.93`.
- **Purpose:** Exact-match caching misses any reworded question.
- **Content:**
  - Lookup order is Redis exact match, then semantic search in Elasticsearch, then compute.
  - Elasticsearch was chosen over Redis Stack or Qdrant because embedding and kNN already existed, so no new infrastructure was needed.
  - Verified: a reworded question hit the cache, and an unrelated question did not.
  - Limits: the 0.93 threshold was tested manually only, and `qa_cache` has no TTL.

---

# Phase 4 — Event-Driven Ingestion

## 2026-09-27 — Redpanda producer/consumer (`58ed714`)
- **Change:** Added `producer_ph4.py`, `consumer_ph4.py`, a `redpanda` service, `KAFKA_*` config, and the `kafka-python-ng` dependency.
- **Purpose:** Alerts should be chunked, embedded and stored automatically when they arrive, with no manual ingest run.
- **Content:**
  - The consumer reuses Phase 1 chunking, embedding and index code. No LLM is involved.
  - `docker.redpanda.com` was unreachable, so the image moved to `redpandadata/redpanda` on Docker Hub.
  - `kafka-python` is broken on this Python version, so it was swapped for `kafka-python-ng` (same API).
  - Windows `echo >>` wrote UTF-16 and corrupted `requirements.txt`. Use `Add-Content` instead.
  - Verified: the full producer to queue to consumer to Elasticsearch loop worked.

## 2026-09-30 — Live alerts wired to `search_logs` (uncommitted)
- **Change:**
  - Added `alerts_ph4.py` and the `security_live_alerts` index (`ES_ALERTS_INDEX`).
  - The consumer now writes there instead of the KB index.
  - `bm25_search`, `knn_search` and `hybrid_search` gained an optional `index` parameter.
  - `search_logs` now calls `hybrid_search(..., index=ES_ALERTS_INDEX)`.
  - `agent_ph2.py` now reports the real source index.
  - An `_ensure_indices` startup hook was added, and a stray `manual-test` document was deleted.
- **Purpose:**
  - Live alerts were leaking into the KB index, which contradicts the `search_knowledge_base` docstring.
  - `search_logs` still read the dead mock file and could not see them.
  - The agent hardcoded `sample_logs/mock_logs.json` as the source.
- **Content:**
  - Verified: the index is created on startup, and the consumer recovers an offline backlog.
  - Verified: alerts land only in `security_live_alerts`.
  - Verified: `/ask-agent` routed the `prod-db-07` question to `search_logs` with the correct details and `sources: ["security_live_alerts"]`.
  - Verified: `/ask` still answers from `sample_docs/` only.
  - Known quirks: Docker Desktop must be relaunched after a Windows update, Redpanda has no restart policy or volume, and the consumer's `print` is buffered when piped (use `python -u`).
  - Limits: there is no structured `host` field, and there is no TTL on `security_live_alerts`.

---

# Phase 5 — Governance and Deployment (not started)
Audit logging, RBAC, PII redaction, Docker/Kubernetes, CI/CD.
