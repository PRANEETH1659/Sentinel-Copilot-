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
- [x] `app/config_ph1.py` — central settings (URLs, model names, chunk size)
- [x] `app/embeddings_ph1.py` — calls Ollama to turn text into vectors
- [x] `app/es_client_ph1.py` — Elasticsearch index mapping, BM25 search, kNN search
- [x] `app/ingest_ph1.py` — chunks documents, embeds them, loads into Elasticsearch
- [x] `app/rag_ph1.py` — hybrid search + Reciprocal Rank Fusion + prompt + Ollama call
- [x] `app/main_ph1.py` — FastAPI app exposing `/ask`
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
- [x] Ran `python -m app.ingest_ph1` → 11 chunks indexed from all 3 sample docs
- [x] Started API with `uvicorn app.main_ph1:app --reload`
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
- [x] `app/tools_ph2.py` — two tools the agent can pick from:
      `search_knowledge_base` (wraps Phase 1's `hybrid_search`, unchanged)
      and `search_logs` (new — searches a small local mock log file; real
      live logs come in Phase 4)
- [x] `sample_logs/mock_logs.json` — 8 made-up log lines (ransomware /
      phishing themed, matching the existing `sample_docs`) so
      `search_logs` has something real to search
- [x] `app/agent_ph2.py` — the LangGraph loop itself: a `think` node (model
      decides which tool fits, or that it's ready to answer) and an `act`
      node (`ToolNode` that runs whichever tool got picked), wired in a
      loop with `add_conditional_edges`
- [x] `app/main_ph1.py` — added `/ask-agent` endpoint alongside the original
      `/ask`, so Phase 1 (always one fixed search) and Phase 2 (model
      decides) can be compared side by side
- [x] `requirements.txt` — added `langgraph`, `langchain-core`,
      `langchain-ollama`

### Files: what's new in Phase 2 vs Phase 1 (2026-08-23)

Worth writing down because git can't answer it — the initial commit
(`ad4913e`) landed Phases 1 and 2 together, so `git log` marks every file
as new and there's no phase-to-phase diff to run.

Genuinely new — 3 files:
- `app/agent_ph2.py` — the LangGraph loop itself: a `think` node (model picks a
  tool or writes the final answer) and an `act` node (`ToolNode`), joined
  by a conditional edge out of `think` and a normal edge back from `act`.
  Also `ask_agent()`, which walks the message history to rebuild `sources`
  so the response keeps the same shape Phase 1 already returned.
- `app/tools_ph2.py` — the two `@tool` functions: `search_knowledge_base` (a
  thin wrapper around Phase 1's `hybrid_search`, search logic unchanged)
  and `search_logs` (new, reads the mock log file).
- `sample_logs/mock_logs.json` — 8 made-up log lines so `search_logs` has
  something real to search. Phase 4 replaces this with a live stream.

Modified, not new — 2 files:
- `app/main_ph1.py` — `POST /ask-agent` added alongside `/ask`, and the app
  version bumped to `0.2.0`
- `requirements.txt` — `langgraph==1.2.11`, `langchain-core==1.6.0`,
  `langchain-ollama==1.1.0`

Untouched Phase 1 code — `app/config_ph1.py`, `app/embeddings_ph1.py`,
`app/es_client_ph1.py`, `app/ingest_ph1.py`, `app/rag_ph1.py`, `docker-compose.yml`,
`sample_docs/`. The retrieval path is byte-for-byte identical; Phase 2 only
wrapped it. That's exactly why `/ask` and `/ask-agent` are worth comparing
side by side — same retrieval underneath, different decision-making on top.

### Sanity-checked (in an isolated environment, no live Elasticsearch/Ollama)
- [x] All new/changed files compile and import cleanly
- [x] `agent_ph2.py`'s graph builds with the expected two nodes (`think`, `act`)
- [x] `search_logs` tool correctly finds/misses entries in the mock log file

### Confirmed against the real venv on this machine (2026-08-22)
- [x] `pip install -r requirements.txt` picked up the three new packages
      without conflicts — `pip freeze` shows all 9 pinned versions matching
      `requirements.txt` exactly, so a fresh clone reproduces this setup
- [x] `app.main_ph1` imports cleanly with all three routes registered
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
      anywhere in the tree, and `app/config_ph1.py` is all `os.getenv` with
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
before `python -m app.ingest_ph1` will work.

---

## File naming convention — 2026-08-23

Every Python file in `app/` now carries the phase it was created in, so you
can tell at a glance which files are Phase 1 and which arrived later,
without opening any of them:

| Was | Now |
|---|---|
| `app/config.py` | `app/config_ph1.py` |
| `app/embeddings.py` | `app/embeddings_ph1.py` |
| `app/es_client.py` | `app/es_client_ph1.py` |
| `app/ingest.py` | `app/ingest_ph1.py` |
| `app/rag.py` | `app/rag_ph1.py` |
| `app/main.py` | `app/main_ph1.py` |
| `app/agent.py` | `app/agent_ph2.py` |
| `app/tools.py` | `app/tools_ph2.py` |

**Rule going forward: any new `.py` file gets `_ph<N>` for the phase that
created it.** The suffix records where a file was BORN, not the last phase
that touched it — `main_ph1.py` keeps its `_ph1` even though Phase 2 added
`/ask-agent` to it.

Two things worth knowing about this:

- It's `_ph2`, NOT `_ph-2`, and that's not a style choice. A hyphen is
  illegal in a Python module name, so `from .agent_ph-2 import ask_agent`
  is a SyntaxError — the file would be unimportable by normal means.
- `app/__init__.py` keeps its name. It's what makes `app/` a package;
  Python looks for that exact filename.

Config/doc files (`README.md`, `PROGRESS.md`, `requirements.txt`,
`docker-compose.yml`) deliberately do NOT get a suffix — they span every
phase, and external tools expect those exact names.

Two commands changed as a result, so old notes and shell history are stale:
- `python -m app.ingest`  ->  `python -m app.ingest_ph1`
- `uvicorn app.main:app`  ->  `uvicorn app.main_ph1:app`

Verified after renaming: all 8 files compile, `app.main_ph1` imports with
all three routes (`/ask`, `/ask-agent`, `/health`), the graph still reports
its two nodes (`think`, `act`), and `search_logs` still matches
`WKSTN-042`. Renames were done with `git mv`, so file history survives.

---

## Compound tool-calling fix — 2026-09-11

Picked up where the 2026-08-28 prompt fix (`8163efa`) left off. That commit
fixed the prompt's routing *rules* but left an open problem: `llama3.2`
(3B) still couldn't reliably execute a compound question (procedure +
named host, e.g. "Did the ransomware runbook get followed on WKSTN-042?")
because it's a tool-calling capability limit, not a wording problem.

Reproduced first, against the live venv (Elasticsearch + Ollama both up):
- `llama3.2`: called `search_knowledge_base` once, then answered directly
  from the runbook alone - never attempted `search_logs` at all. Answered
  "the ransomware runbook was followed on WKSTN-042," the exact unverified
  claim the 08-28 fix was trying to prevent.

Tried `qwen2.5:7b` (already pulled locally, 4.7GB) as `CHAT_MODEL` instead:
- Correctly called `search_knowledge_base` then `search_logs`, in order,
  before answering, on the compound question - 3/3 test questions routed
  correctly (single knowledge-base, single logs, compound).
- Its first attempt at the compound case used a two-word log query
  (`"WKSTN-042 ransomware"`), which surfaced a second, separate bug (next
  item) rather than a model problem.

### Bug found while testing: `search_logs` word matching
`app/tools_ph2.py`'s `search_logs` matched the *whole* keyword string as one
substring against each log entry. A capable model composing a natural
multi-word query (host + topic, e.g. `"WKSTN-042 ransomware"`) got a false
"no log entries found," even though a real entry existed for that host
describing ransomware-consistent activity - the words just weren't
contiguous in the JSON. That's the same failure mode as the 08-28 bug
(reporting something as absent/present without real evidence), just
flipped: false negative instead of false positive. Fixed by splitting the
keyword on whitespace and requiring every word to appear somewhere in the
entry (AND, not one contiguous substring) - single-word queries behave
exactly as before.

### Result: `qwen2.5:7b` is now the default `CHAT_MODEL`
`app/config_ph1.py` changed - `llama3.2` remains available via
`CHAT_MODEL=llama3.2` for anyone who wants the smaller (~2GB vs ~4.7GB)
download and only needs `/ask` or single-tool `/ask-agent` questions.

### Confirmed against the real venv (Elasticsearch + Ollama live)
- [x] `llama3.2` reproduces the original bug: skips `search_logs` entirely
      on the compound question, asserts an unverified fact
- [x] `qwen2.5:7b` + the `search_logs` fix: all three test questions from
      the Phase 2 log route correctly -
      - "What is the ransomware runbook about?" -> `search_knowledge_base` only
      - "Anything suspicious on WKSTN-042?" -> `search_logs` only
      - "Did the ransomware runbook get followed on WKSTN-042?" -> both
        tools, in order, then a grounded answer that lists what the logs
        DO show (encryptor.exe, mass file rename, EDR auto-isolation) and
        explicitly says it can't confirm the runbook's later steps
        (scope identification, account disablement) from the available
        logs - no hedging, no unverified claims
- [x] Phase 1's `/ask` (`answer_question` in `app/rag_ph1.py`) re-verified
      end-to-end with `qwen2.5:7b` as the new default - still returns a
      grounded answer with sources, no regression from the model swap

### Known minor quirk, not fixed (out of scope for this fix)
`ask_agent()`'s source-collection walks every tool message in the
conversation, so a compound answer's `sources` can include a knowledge-base
chunk from a *different* runbook than the one actually discussed (observed:
`runbook_phishing_response.txt` alongside `runbook_ransomware_response.txt`
for a ransomware-only question) - `hybrid_search`'s `top_n=5` sometimes
pulls in a related-but-different document. Pre-existing Phase 1 retrieval
behavior, not something this fix touched.

---

## Phase 3 — Production hardening (not started)
Redis caching, streaming responses, latency tracing.

## Phase 4 — Event-driven ingestion (not started)
Kafka/Redpanda producer + consumer for live alerts (this is what
`search_logs` will read from instead of the Phase 2 mock file).

## Phase 5 — Governance and deployment (not started)
Audit logging, RBAC, PII redaction, Docker/Kubernetes, CI/CD.
