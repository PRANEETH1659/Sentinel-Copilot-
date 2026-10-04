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

## Phase 3 — Production hardening — 2026-09-11

Three pieces: Redis caching, latency tracing, streaming responses. All
three built, and all three verified against the live stack (Elasticsearch +
Redis in Docker, Ollama native, `qwen2.5:7b`).

### Code written
- [x] `app/cache_ph3.py` - Redis get/set for `/ask` and `/ask-agent`
      answers. Cache key = endpoint + question + current `CHAT_MODEL` (so a
      future model swap, like the Phase 2 llama3.2 -> qwen2.5:7b change,
      can never serve a stale answer from a different model). Fails open -
      if Redis is unreachable, `get_cached_answer` returns `None` and
      `set_cached_answer` silently no-ops, so a cache outage degrades to
      "always recompute," not a broken API.
- [x] `app/tracing_ph3.py` - a `Trace` class that times named steps within
      one request. Deliberately not OpenTelemetry/Jaeger - this is one
      Python process talking to two local dependencies, so a plain
      step-timings dict answers "where did the time go?" with zero extra
      infrastructure. `Trace` is always a fresh local object per request,
      never shared/global state, so concurrent requests can't cross-
      contaminate each other's timings.
- [x] `redis` service added to `docker-compose.yml` (no volume - it's a
      cache, not a datastore; losing it on restart just means the next
      question recomputes)
- [x] `REDIS_URL`, `CACHE_TTL_SECONDS` added to `app/config_ph1.py`
- [x] `rag_ph1.answer_question` and `agent_ph2.ask_agent` both wrapped with
      `Trace` and now return a `timings` dict (`hybrid_search_ms` +
      `llm_generate_ms` for `/ask`; `agent_reasoning_ms` for `/ask-agent`)
- [x] `main_ph1.py`: both endpoints check Redis before running and store
      the result after; responses gained a `cached: bool` field. An
      `X-Process-Time` response header plus a per-request log line were
      added via FastAPI middleware.
- [x] `rag_ph1.ask_ollama_stream` / `answer_question_stream` and
      `agent_ph2.ask_agent_stream` - streaming counterparts that yield
      `{"type": "answer"|"sources", "content": ...}` events instead of
      returning one finished dict
- [x] `POST /ask/stream` and `POST /ask-agent/stream` - Server-Sent Events
      (`data: <json>\n\n`, closed with `data: [DONE]\n\n`). Both bypass the
      Redis cache on purpose - caching a token stream (store it, then
      replay it at the same pace or all at once?) is real complexity not
      worth it here; every streaming call recomputes.

### How the agent's streaming actually works
`agent_ph2.ask_agent_stream` uses LangGraph's `agent.stream(...,
stream_mode="messages")`, which streams every chat-model call in the graph
- including the "think" turn that only emits a tool call. Verified
empirically (not assumed) before writing the endpoint: a tool-call-only
turn produces an `AIMessageChunk` with `content=""` and `node="think"`; the
tool's result comes back as ONE complete `ToolMessage` on `node="act"` (not
token-streamed, since it's not LLM output); the real answer streams in as a
series of non-empty `AIMessageChunk`s. So the generator forwards only
chunks with real text, and uses the `ToolMessage`s for source collection
(same per-tool logic as `ask_agent`) - the caller sees just the final
answer typing in, with tool calls happening silently in between exactly
like the non-streaming endpoint.

### Confirmed against the real venv (Elasticsearch + Redis + Ollama live)
- [x] Redis and Elasticsearch containers both healthy via `docker compose up -d`
- [x] `/ask` cache: first call `cached:false` with real timings
      (`hybrid_search_ms=3425.3`, `llm_generate_ms=68098.2`); identical
      second call `cached:true`, returned in 0.26s (measured with
      `curl -w %{time_total}`) instead of ~71.5s
- [x] `/ask-agent` cache: same pattern - first call `cached:false` with
      `agent_reasoning_ms=167975.4`; second call `cached:true` in 0.26s
- [x] `/ask/stream`: tokens arrive incrementally (confirmed by reading the
      output file mid-stream, not just at the end), ends with a `sources`
      event and `[DONE]`
- [x] `/ask-agent/stream`: single-tool question (`search_logs`) streamed
      cleanly - no leaked empty/tool-call chunks, real answer tokens only,
      correct `sources` event, `[DONE]` at the end

### Known limitation, not fixed (documented, out of scope for this phase)
Local LLM generation on this machine is slow - ~68s for one `/ask` answer,
~168s for a 3-tool-call `/ask-agent` compound question. Caching hides this
for repeat questions but does nothing for the first one. Streaming (this
phase) at least makes that first wait feel shorter, since text appears
as it's generated instead of all at once. Actually reducing generation
time would mean a smaller/faster model or a quantized build - not pursued
here since it trades off against the qwen2.5:7b tool-calling quality fix
from the previous session.

---

## Pushed to GitHub — 2026-09-13

- [x] Secrets audit before pushing: scanned the diff for
      `api_key`/`secret`/`password`/`token`/`private_key`/etc. - only hits
      were "token" in the streaming code's own comments and log messages
      (LLM output tokens, not auth tokens). `.env` confirmed still untracked
      and still in `.gitignore`; `app/config_ph1.py` and the new
      `REDIS_URL`/`CACHE_TTL_SECONDS` are all `os.getenv` with localhost/
      no-auth defaults.
- [x] Pushed 4 commits to `origin/main` (`6800de7..c497453`): the file
      naming refactor, both Phase 2 agent fixes, and all of Phase 3

## Semantic cache (Phase 3b) — 2026-09-13

Redis caching from Phase 3 only recognizes a question it's seen byte-for-
byte before (after trim/lowercase) - any rewording is a guaranteed miss,
even though real usage rarely repeats the exact same sentence. This adds a
second, fuzzier cache tier on top of the existing exact-match one, so a
REWORDED repeat of a past question can still skip the expensive hybrid-
search + LLM-generate path.

### Code written
- [x] `app/config_ph1.py` - added `ES_CACHE_INDEX` (`qa_cache`) and
      `SEMANTIC_CACHE_SCORE_THRESHOLD` (default `0.93`, on ES's kNN cosine
      score scale of 0-1)
- [x] `app/cache_ph3.py` - added a new `qa_cache` Elasticsearch index
      (`question`, `embedding`, `endpoint`, `model`, `result`,
      `created_at`) and `ensure_cache_index()` to create it. `get_cached_answer`
      now tries Redis exact-match first (unchanged, still free/instant),
      and on a miss falls through to `_semantic_lookup()` - embeds the
      question, kNN-searches `qa_cache` filtered to the same
      endpoint+model, returns the top hit's answer if its score clears the
      threshold. `set_cached_answer` now writes to both tiers on every
      fresh answer. Same fail-open contract as the Redis tier - any
      Elasticsearch/Ollama error during the semantic path returns `None`
      instead of raising, so a semantic-cache outage degrades to "always
      recompute," not a broken API.
- [x] `app/main_ph1.py` - added a FastAPI startup hook that calls
      `ensure_cache_index()`, so `qa_cache` exists before the first
      request instead of being lazily (and wrongly - dynamic mapping
      wouldn't make `embedding` a `dense_vector`) auto-created by ES on
      first write.

### Design decision: why Elasticsearch, not Redis Stack or Qdrant
Considered three places to run the similarity search: swap Redis for
Redis Stack (adds RediSearch's vector module), add Qdrant (a dedicated
vector DB - already planned for Phase 4 log ingestion per the
`docker-compose.yml` comment), or reuse Elasticsearch. Went with
Elasticsearch - `embed_text()` and kNN search already exist for Phase 1's
RAG pipeline, so this needed zero new infrastructure, just a second index.

### Confirmed against the real venv (Elasticsearch + Redis + Ollama live)
- [x] `qa_cache` index created automatically on `uvicorn --reload`
      restart, with the correct explicit mapping (verified via
      `GET _cat/indices`, not dynamically inferred)
- [x] Fresh question ("What immediate actions should be taken when
      ransomware is detected on a workstation?") → `cached:false`,
      `hybrid_search_ms=2199.8`, `llm_generate_ms=49699.3`
- [x] Reworded repeat ("If ransomware is found on a workstation, what
      should I do right away?") → `cached:true`, identical answer,
      returned near-instantly instead of regenerating - the semantic tier
      fired correctly on completely different wording
- [x] Unrelated question ("What should I check in SSH logs for suspicious
      login attempts?") → `cached:false`, did NOT falsely match the
      ransomware answer - threshold isn't too loose

### Known limitations, not fixed (out of scope for now)
- `SEMANTIC_CACHE_SCORE_THRESHOLD=0.93` is from one round of manual
  testing, not tuned against a real paraphrase set - revisit if real
  usage shows misses (too strict) or wrong-answer matches (too loose).
- `qa_cache` has no TTL/cleanup, unlike Redis's `CACHE_TTL_SECONDS` - ES
  has no native per-document expiry, so this index grows unboundedly.
  Fine for a demo; a long-running deployment would need a scheduled
  cleanup job on `created_at`.

---

## Phase 4 — Event-driven ingestion — 2026-09-27

Producer/consumer pair on Redpanda (Kafka-API-compatible), so a new alert
gets chunked + embedded + stored in Elasticsearch automatically the moment
it arrives - no manual `python -m app.ingest_ph1` run needed. Core loop
proven end-to-end; wiring `search_logs` to read from this instead of the
Phase 2 mock file is still open (see below).

### Code written
- [x] `app/producer_ph4.py` - announces an alert onto the `security-alerts`
      topic. Stand-in for whatever eventually detects real alerts (log
      monitor, IDS, SIEM webhook).
- [x] `app/consumer_ph4.py` - listens on that topic; reuses
      `ingest_ph1.chunk_text`, `embeddings_ph1.embed_text`,
      `es_client_ph1.ensure_index`/`get_client` - same three-step filing
      logic as Phase 1's `run_ingest()`, just triggered per-message instead
      of per-file. No LLM involved in this path - that's still `/ask`'s job.
- [x] `docker-compose.yml` - added `redpanda` service (single-node,
      `--overprovisioned`, listener on `9092`)
- [x] `app/config_ph1.py` - added `KAFKA_BOOTSTRAP_SERVERS`,
      `KAFKA_ALERTS_TOPIC`
- [x] `requirements.txt` - `kafka-python-ng` (see quirk below)

### Environment setup
- [x] `docker.redpanda.com` registry unreachable from this machine (DNS
      failure on `docker compose up`) - switched the image to
      `redpandadata/redpanda:latest` on Docker Hub, which pulled fine
- [x] Verified with `docker exec -it redpanda rpk cluster info` - broker up
- [x] Created topic: `docker exec -it redpanda rpk topic create
      security-alerts` -> `OK`

### Known quirks on this setup (so we don't re-debug them)
- `echo text >> file` in PowerShell writes UTF-16, not UTF-8 - silently
  corrupted `requirements.txt`'s `kafka-python` line (showed as null-byte-
  separated characters when read back as UTF-8). Fixed by rewriting the
  file cleanly; use `Add-Content` (or an explicit UTF-8 redirect) instead
  of a bare `echo >>` when appending to text files in PowerShell.
- `kafka-python` (the original PyPI package) is unmaintained and throws
  `ModuleNotFoundError: No module named 'kafka.vendor.six.moves'` on this
  Python version - a bug in its vendored `six` compat shim. Fixed by
  swapping to `kafka-python-ng`, an actively maintained fork with an
  identical `from kafka import ...` API - no code changes needed.

### Confirmed against the real venv (Elasticsearch + Redpanda live)
- [x] `pip install -r requirements.txt` picked up `kafka-python-ng` cleanly
      after uninstalling the broken `kafka-python`
- [x] `python -m app.consumer_ph4` started clean, reused the existing
      `security_knowledge_base` index, printed `Listening on topic
      'security-alerts'...`
- [x] `python -m app.producer_ph4 "Failed SSH login attempts detected from
      IP 203.0.113.45"` -> `Sent alert to 'security-alerts': ...`
- [x] Consumer picked it up automatically and printed `Ingested alert from
      'manual-test' (1 chunk(s)): Failed SSH login attempts detected from
      IP 203.0.113.45` - full producer -> queue -> consumer -> Elasticsearch
      loop confirmed, zero manual steps between send and store

### Still to confirm
- [ ] `search_logs` (`tools_ph2.py`) swapped from the Phase 2 mock
      `mock_logs.json` file to actually query live-ingested alerts
- [ ] Consumer survives being offline when a message is sent (start
      producer first, then consumer, confirm it still picks up the
      backlog via `auto_offset_reset="earliest"`)
- [ ] Ask `/ask` or `/ask-agent` a question about this specific alert and
      confirm it retrieves it from the live-ingested data, not just
      `sample_docs`

## Phase 4 follow-up — live alerts wired to `search_logs` — 2026-09-30

Closes out the three "Still to confirm" items above. `search_logs`
(`app/tools_ph2.py`) now queries live-ingested alerts instead of the Phase 2
mock file, and the consumer's offline-backlog recovery and live-retrieval
behavior were both confirmed against the running stack.

### Design decision: a separate `security_live_alerts` index, not the KB index
The consumer (`app/consumer_ph4.py`) was writing every live alert into
`config.ES_INDEX` (`security_knowledge_base`) - the SAME index `sample_docs/`
live in. That meant live alerts were already retrievable via
`search_knowledge_base`/`/ask`, directly contradicting that tool's own
docstring ("Do NOT use this for questions about live or recent system
activity"), and `search_logs` still couldn't see them at all (it read the
dead `sample_logs/mock_logs.json` file). Fixed by giving live alerts their
own index (`app/alerts_ph4.py`'s `ALERTS_INDEX_MAPPING` /
`ensure_alerts_index()`, `config.ES_ALERTS_INDEX` = `security_live_alerts`)
- the same pattern Phase 3b already established for the semantic cache
(`qa_cache`, its own index rather than overloading the KB one). Reused
Phase 1's exact BM25+kNN+RRF logic for the new index too, instead of
duplicating it: `es_client_ph1.bm25_search`/`knn_search` and
`rag_ph1.hybrid_search` all gained an optional `index` parameter (defaults
to `config.ES_INDEX`, so every existing call site is unaffected), and
`search_logs` just calls `hybrid_search(keyword, top_n=5,
index=config.ES_ALERTS_INDEX)` instead of reading JSON.

Also fixed a bug this uncovered in `app/agent_ph2.py`: `ask_agent`/
`ask_agent_stream` were hardcoding `"sample_logs/mock_logs.json"` as the
reported source for any `search_logs` hit - a literal string, not derived
from the tool's actual output. Left alone, `/ask-agent` would have kept
claiming answers came from a file that's no longer even read, even after
`search_logs` itself was fixed. Now reports `config.ES_ALERTS_INDEX`.

### Manual-test cleanup
A stray `source="manual-test"` document was sitting in
`security_knowledge_base` from the ad-hoc test alert sent while confirming
the producer/consumer loop (2026-09-27 entry, above) - leftover from before
this fix existed, when the consumer still wrote into the KB index. Removed
via `delete_by_query` filtered on `source: "manual-test"`
(`conflicts=proceed`, `refresh=true`): matched and deleted 1 document,
0 version conflicts, count confirmed 0 afterward.

### Confirmed against the real venv (Elasticsearch + Redpanda + Ollama live)
- [x] `security_live_alerts` created automatically on API startup (the new
      `_ensure_indices` startup hook in `main_ph1.py`) - confirmed via
      `GET _cat/indices` showing it alongside `qa_cache` and
      `security_knowledge_base` before the consumer had ever run
- [x] Offline backlog recovery: sent an alert via `python -m
      app.producer_ph4` with no consumer running, then started
      `python -m app.consumer_ph4` - the alert was ingested and indexed
      (confirmed via a direct ES query, `received_at:
      "2026-09-30T17:48:30+00:00"`) even though the process was stopped
      before its own "Ingested alert..." print line was observed - the
      write to Elasticsearch itself is the real proof, not the log line
- [x] The alert lands in `security_live_alerts`, NOT
      `security_knowledge_base` - a direct-text search for the alert's
      content (`"prod-db-07"`) returns exactly 1 hit in `security_live_alerts`
      and the alert's actual text is absent from `security_knowledge_base`.
      (A `match` query for the same keyword against `security_knowledge_base`
      also returns 1 hit, but it's a pre-existing, unrelated sample doc
      (`incident_2026_0142.txt`) that happens to share a token after
      hyphen-splitting - confirmed by inspecting the actual hit, not the
      alert leaking through.)
- [x] `POST /ask-agent` with "Has there been any suspicious outbound data
      transfer from prod-db-07 recently?" correctly routed to `search_logs`,
      answered with the exact alert details (2.3GB, `198.51.100.23`, 4
      minutes, DLP), and returned `"sources": ["security_live_alerts"]` -
      proving both live retrieval and the `agent_ph2.py` source-bug fix
      (`agent_reasoning_ms: 62544.7`)
- [x] Regression check: `POST /ask` with "What is the ransomware runbook
      about?" still answers correctly from `sample_docs/` only
      (`sources: ["runbook_phishing_response.txt",
      "runbook_ransomware_response.txt"]`, `hybrid_search_ms: 2255.3`,
      `llm_generate_ms: 57819.8`), and the answer text contains no trace of
      the live alert's content

### Known quirk hit during this session, not a code bug
Docker Desktop had stopped running between sessions (a Windows update had
landed - the reported OS build number changed mid-conversation). `docker
compose up -d` failed with `open //./pipe/dockerDesktopLinuxEngine: The
system cannot find the file specified` until Docker Desktop itself was
relaunched (`Start-Process "shell:AppsFolder\Docker.DockerForWindows.Settings"`
- its installed `.exe` path isn't directly under `C:\Program Files\Docker`
on this machine, so launching by its registered AppID was more reliable
than guessing the path) and given time for the daemon to come up. Once it
was up, `sentinel-es`/`sentinel-redis` (both `restart: unless-stopped`)
came back on their own; `redpanda` (no restart policy set, and the only
service with no data volume) needed an explicit `docker compose up -d` and
came up as a fresh, empty broker.

Separately: `python -m app.consumer_ph4` buffers `print()` output when its
stdout isn't a real terminal (e.g. piped through `timeout` for a bounded
test run), so log lines can appear late or not at all relative to when they
actually ran - use `python -u -m app.consumer_ph4` (or
`PYTHONUNBUFFERED=1`) when scripting a timed/bounded run of it, and verify
actual ingestion against Elasticsearch directly rather than trusting the
console output's timing in that situation.

### Known limitations, not fixed (out of scope for now)
- Live alerts have no structured `host` field (unlike the old mock log
  entries, which had `host` as its own JSON key) - the producer only ever
  sends free-text `text` + `source` + `timestamp`, so `search_logs` can
  only full-text/semantically search alert bodies, not filter by an exact
  host field. Fine for the current producer (a manual test stub); a real
  alert source would probably want a structured `host` field added to both
  the Kafka message and `ALERTS_INDEX_MAPPING`.
- `security_live_alerts`, like `qa_cache`, has no TTL/cleanup - it grows
  unboundedly. Fine for a demo; a long-running deployment would want a
  retention policy (e.g. ILM) on `received_at`.

## Phase 4 local re-test — 2026-10-04

Came back after a 4-day gap and re-ran the whole stack locally (Docker:
Elasticsearch + Redis + Redpanda; Ollama native). All `/ask`, `/ask-agent`
and live-alert queries behaved as before - Phase 4 is closed out.

## Phase 5 — Governance and deployment

Planned order: 5a audit logging -> 5b PII redaction -> 5c RBAC -> 5d CI/CD +
containerising the API -> 5e Kubernetes (stretch).

### 5a — Audit logging — 2026-10-04

Every question asked publishes one audit event (who/what/when/outcome) onto
its own Redpanda topic, `audit-events`; a separate consumer files it into
the `audit_log` Elasticsearch index. This is the second use of Redpanda's
real strength: the API never waits on the audit write, and further readers
of the same events (5b PII redaction, alerting) can be added without
touching the API.

#### Code written
- [x] `app/audit_ph5.py` - `record_audit()` (publishes one event; a shared
      lazily-created producer; **fails open** like the caches - if Redpanda
      is down it logs a warning and the question still gets answered, with a
      30s cooldown so a dead broker isn't retried on every request),
      `AUDIT_INDEX_MAPPING`, `ensure_audit_index()`, `flush_audit()`
- [x] `app/audit_consumer_ph5.py` - reads `audit-events` with its own
      `group_id` (`sentinelcopilot-audit`), independent of Phase 4's alert
      consumer, and indexes each event into `audit_log`
- [x] `app/main_ph1.py` - `/ask` and `/ask-agent` wrapped by `_audited()`
      (records success AND errors); `/ask/stream` and `/ask-agent/stream`
      record from what actually streamed out; startup creates the index,
      shutdown flushes the producer; version bumped to `0.4.0`
- [x] `app/config_ph1.py` - `KAFKA_AUDIT_TOPIC`, `ES_AUDIT_INDEX`

#### Recorded per event
`timestamp`, `endpoint`, `question`, `client` (IP), `status` (ok/error),
`cached`, `sources`, `answer_chars`, `duration_ms`, `error`.
Deliberately **not** the answer text, only its length - answers can echo
alert contents (IPs, hostnames), and deciding what is safe to store is 5b's
job.

#### Confirmed against the live stack
- [x] Created the topic: `docker exec redpanda rpk topic create audit-events`
- [x] `/ask` call -> consumer printed `Audited ask status=ok cached=True`;
      `audit_log` held the document with sources, `answer_chars=614`,
      `duration_ms`, `client=127.0.0.1`
- [x] `/ask/stream` (uncached, ~87s) -> audit event recorded with
      `endpoint=ask/stream`, `answer_chars=489`, correct sources
- [x] Fail-open: with `KAFKA_BOOTSTRAP_SERVERS=localhost:1`, `record_audit`
      raised nothing; first call took ~2s (broker connect timeout), later
      calls 0.00s (cooldown)

#### Not verified / known gaps
- [ ] The `error` path (an endpoint raising mid-request) was not exercised
      live - only written.
- [ ] `/ask-agent` and `/ask-agent/stream` audit events were not sent live;
      they use the same `_audited` / `_sse` code as the verified two.
- `audit_log` has no retention policy and no way to read it except querying
  Elasticsearch directly (no `/audit` endpoint yet - that belongs with 5c
  RBAC, since an audit log should be admin-only).
- Redpanda has no volume, so `audit-events` (and `security-alerts`) must be
  recreated with `rpk topic create` after the container is recreated.

### Next: 5b — PII redaction
Mask IPs/emails/usernames before they are stored or returned.
