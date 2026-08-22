# SentinelCopilot - Progress Log

This file tracks what's actually been done on this project, in order.
Every time we finish something real, add an entry here — future-you will
thank present-you when Phase 3 makes you forget what Phase 1 even did.

**How to use this:** newest entry at the BOTTOM (so it reads top-to-bottom
like a story of the build). Check a box when something is confirmed working
on your machine, not just when code is written.

---

## Phase 1 — Hybrid RAG Core

### Code written
- [x] `app/config.py` — central settings (URLs, model names, chunk size)
- [x] `app/embeddings.py` — calls Ollama to turn text into vectors
- [x] `app/es_client.py` — Elasticsearch index mapping, BM25 search, kNN search
- [x] `app/ingest.py` — chunks documents, embeds them, loads into Elasticsearch
- [x] `app/rag.py` — hybrid search + Reciprocal Rank Fusion + prompt + Ollama call
- [x] `app/main.py` — FastAPI app exposing `/ask`
- [x] `docker-compose.yml` — spins up Elasticsearch locally
- [x] `sample_docs/` — 3 fictional security docs (1 incident report, 2 runbooks)

### Environment setup (on Praneeth's Windows machine)
- [x] WSL2 confirmed installed (Ubuntu, version 2)
- [x] Docker Desktop installed, verified with `docker run hello-world`
- [x] Ollama installed
- [x] Pulled `llama3.2` (chat model, ~2GB)
- [x] Pulled `nomic-embed-text` (embedding model, ~270MB)
- [x] Verified Ollama with `ollama run llama3.2 "say hello"`

### Getting the project running
- [x] Project unzipped to
      `D:\personal codes\SentinelCopilot - perfect AI project\sentinelcopilot\sentinelcopilot`
- [x] `docker compose up -d` → Elasticsearch container started
- [x] Verified Elasticsearch healthy — `curl.exe http://localhost:9200` returned
      `"tagline" : "You Know, for Search"`
- [x] Python venv created, `pip install -r requirements.txt` completed
- [x] Ran `python -m app.ingest` → 11 chunks indexed from all 3 sample docs
- [x] Started API with `uvicorn app.main:app --reload`
- [x] Asked `/ask` a real question ("What is the ransomware runbook about?")
      and confirmed a grounded answer with sources
      (`runbook_phishing_response.txt`, `runbook_ransomware_response.txt`)

### Known quirks on this setup (so we don't re-debug them)
- Plain `curl` in PowerShell triggers a security prompt (it's aliased to
  `Invoke-WebRequest`) — use `curl.exe` instead to call the real curl.
- Project folder ended up double-nested after extracting the zip
  (`sentinelcopilot\sentinelcopilot\...`) — that inner folder is the real
  project root; always `cd` into it before running commands.
- If `uvicorn` fails with `ModuleNotFoundError: No module named 'fastapi'`,
  the venv isn't activated in that terminal — run
  `.\venv\Scripts\Activate.ps1` first (look for `(venv)` in the prompt).
- If `/ask` returns a 500 Internal Server Error, the real cause is printed
  in the terminal running `uvicorn`, not in the API response — check there
  first. Usually means Docker (Elasticsearch) or Ollama isn't running.

**Phase 1 status: done.**

---

## Phase 2 — Agent orchestration

Wraps the Phase 1 RAG core in a LangGraph agent that can choose between
multiple tools, instead of always running one fixed retrieval step.

### Code written
- [x] `app/tools.py` — two tools the agent can pick from:
      `search_knowledge_base` (wraps Phase 1's `hybrid_search`, unchanged)
      and `search_logs` (new — searches a small local mock log file; real
      live logs come in Phase 4)
- [x] `sample_logs/mock_logs.json` — 8 made-up log lines (ransomware /
      phishing themed, matching the existing `sample_docs`) so
      `search_logs` has something real to search
- [x] `app/agent.py` — the LangGraph loop itself: a `think` node (model
      decides which tool fits, or that it's ready to answer) and an `act`
      node (`ToolNode` that runs whichever tool got picked), wired in a
      loop with `add_conditional_edges`
- [x] `app/main.py` — added `/ask-agent` endpoint alongside the original
      `/ask`, so Phase 1 (always one fixed search) and Phase 2 (model
      decides) can be compared side by side
- [x] `requirements.txt` — added `langgraph`, `langchain-core`,
      `langchain-ollama`

### Sanity-checked (in an isolated environment, no live Elasticsearch/Ollama)
- [x] All new/changed files compile and import cleanly
- [x] `agent.py`'s graph builds with the expected two nodes (`think`, `act`)
- [x] `search_logs` tool correctly finds/misses entries in the mock log file

### Confirmed against the real venv on this machine (2026-08-22)
- [x] `pip install -r requirements.txt` picked up the three new packages
      without conflicts — `pip freeze` shows all 9 pinned versions matching
      `requirements.txt` exactly, so a fresh clone reproduces this setup
- [x] `app.main` imports cleanly with all three routes registered
      (`/ask`, `/ask-agent`, `/health`) — so uvicorn has no import errors
- [x] Re-ran the isolated-env checks above against the real venv: the
      compiled graph reports its two nodes, and `search_logs` returns real
      matches for `WKSTN-042`

### Still to confirm — these need Elasticsearch + Ollama actually running
- [ ] `POST /ask-agent` with a knowledge-base-style question (e.g. "What is
      the ransomware runbook about?") picks `search_knowledge_base` and
      returns sources like `/ask` does
- [ ] `POST /ask-agent` with a log-style question (e.g. "Anything suspicious
      on WKSTN-042?") picks `search_logs` instead
- [ ] A question needing both (e.g. "Did the ransomware runbook get
      followed on WKSTN-042?") makes the agent call both tools before
      answering — this is the one that actually proves the loop, not just
      the tool-picking

---

## Published to GitHub — 2026-08-22

- [x] Secrets audit before the first push: no `.env`, keys, certs or tokens
      anywhere in the tree, and `app/config.py` is all `os.getenv` with
      localhost defaults. The only hits for "credential" were the word
      itself inside the fictional runbook prose
- [x] `.gitignore` confirmed doing its job — `venv/` and `__pycache__/`
      were the only things excluded. 19 files, 998 lines, 124K total
- [x] Pushed to https://github.com/PRANEETH1659/Sentinel-Copilot-
- [x] `README.md` brought up to date with Phase 2 (`/ask-agent`, `/health`,
      and the think/act loop) — it had still described the agent as future
      work, which contradicted the code that was already built

Reminder for a fresh clone: Docker has to be running, and both
`ollama pull llama3.2` and `ollama pull nomic-embed-text` have to be done,
before `python -m app.ingest` will work.

---

## Phase 3 — Production hardening (not started)
Redis caching, streaming responses, latency tracing.

## Phase 4 — Event-driven ingestion (not started)
Kafka/Redpanda producer + consumer for live alerts (this is what
`search_logs` will read from instead of the Phase 2 mock file).

## Phase 5 — Governance and deployment (not started)
Audit logging, RBAC, PII redaction, Docker/Kubernetes, CI/CD.
