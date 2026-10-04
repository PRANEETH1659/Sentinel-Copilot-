# SentinelCopilot - Hybrid RAG Core + Agent

An AI security-operations copilot that answers questions by hybrid-searching
(keyword + semantic) a knowledge base of incident reports and runbooks, then
asks a locally-running LLM to answer using only that retrieved context.

Four phases are built and working:

- **Phase 1** (`/ask`) - always runs one fixed hybrid search, then answers.
- **Phase 2** (`/ask-agent`) - a LangGraph agent decides *which* tool(s) to
  use (knowledge base, logs, or both) before it answers.
- **Phase 3** - production hardening on top of both: Redis caching (repeat
  questions skip retrieval + generation entirely), a `timings` breakdown in
  every response, and streaming variants (`/ask/stream`, `/ask-agent/stream`)
  that return the answer token-by-token instead of all at once.
- **Phase 4** - event-driven ingestion: a Redpanda (Kafka-API-compatible)
  producer/consumer pair chunks, embeds, and stores each new alert into its
  own Elasticsearch index (`security_live_alerts`) the moment it arrives, no
  manual ingest step needed - that's what `search_logs` (used by
  `/ask-agent`) actually searches now.
- **Phase 5a** - audit logging: every question asked (any of the four
  endpoints) publishes one audit event to its own Redpanda topic
  (`audit-events`); a separate consumer files it into the `audit_log`
  Elasticsearch index. Run it with `python -u -m app.audit_consumer_ph5`.

All four non-streaming/streaming endpoint pairs stay live side by side on
purpose, so you can compare them.

Python files in `app/` are suffixed with the phase that created them -
`rag_ph1.py`, `agent_ph2.py` - so you can see which phase a file belongs to
without opening it. The suffix marks where a file was born, not the last
phase to touch it (`main_ph1.py` is Phase 1 even though Phase 2 added
`/ask-agent` to it). See `PROGRESS.md` for the full rule.

**Cost: $0.** Everything below runs on your own machine.

## Prerequisites (do these once)

1. Docker Desktop installed and running (WSL2 backend)
2. Ollama installed, with two models pulled:
   ```
   ollama pull qwen2.5:7b
   ollama pull nomic-embed-text
   ```
   `qwen2.5:7b` is the default chat model (`app/config_ph1.py`). It replaced
   `llama3.2` because the 3B model couldn't reliably make two tool calls in
   one turn - see `PROGRESS.md` for the compound-routing fix. `llama3.2`
   still works fine for `/ask` alone if you want the smaller download; set
   `CHAT_MODEL=llama3.2` to use it.

## Run it

Open PowerShell in this project folder and run each step:

**1. Start Elasticsearch and Redis**
```powershell
docker compose up -d
```
Wait ~30 seconds for it to finish starting, then check Elasticsearch is healthy:
```powershell
curl http://localhost:9200
```
You should get back a JSON blob with a `"tagline" : "You Know, for Search"`.
Redis (added in Phase 3, used for caching) needs no manual check - if it's
unreachable, `/ask` and `/ask-agent` just skip the cache and work normally.

**2. Create a virtual environment and install dependencies**
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**3. Ingest the sample documents**
```powershell
python -m app.ingest_ph1
```
This reads the 3 sample files in `sample_docs/`, splits them into chunks,
embeds each chunk with Ollama, and indexes them into Elasticsearch. You
should see output like `Indexed 4 chunks from incident_2026_0142.txt`.

**4. Start the API**
```powershell
uvicorn app.main_ph1:app --reload
```

**5. Ask it something** (in a new PowerShell window, venv still active or not - this is just a plain HTTP call)
```powershell
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"question\": \"What should I do if a laptop gets hit by ransomware?\"}"
```

Try questions that use *different words* than the source docs to see hybrid
search earn its keep, e.g. "how do we handle credential stuffing attacks"
even though the incident report never uses the phrase "credential stuffing"
in that exact wording everywhere.

**6. Ask the agent instead (Phase 2)**

Same request shape, different endpoint - this one lets the model pick its
own tools rather than always running one fixed search:
```powershell
curl -X POST http://localhost:8000/ask-agent -H "Content-Type: application/json" -d "{\"question\": \"Anything suspicious on WKSTN-042?\"}"
```

Three questions worth trying, because each takes a different path through
the agent:
- *"What is the ransomware runbook about?"* -> picks `search_knowledge_base`
- *"Anything suspicious on WKSTN-042?"* -> picks `search_logs` instead
- *"Did the ransomware runbook get followed on WKSTN-042?"* -> calls BOTH
  tools before answering. This is the one that actually proves the loop
  works, rather than just proving it can pick a tool.

There's also a `GET /health` that returns `{"status": "ok"}` when the API is
up - handy for confirming the server started without asking it a question.

You can also open **http://localhost:8000/docs** in a browser for a free
interactive UI (FastAPI generates this automatically) instead of using curl.

**7. Caching and timings (Phase 3)**

Both `/ask` and `/ask-agent` now check Redis before doing any real work.
Ask the exact same question twice and look at the response:
```powershell
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"question\": \"What is the ransomware runbook about?\"}"
```
The first call returns `"cached": false` and a `"timings"` object showing
how long retrieval vs. generation took; asking the *exact same* question
again returns `"cached": true` with the same answer, back in well under a
second. The cache key includes the current `CHAT_MODEL`, so switching
models never serves you an answer generated by a different one.

**8. Streaming (Phase 3)**

`/ask/stream` and `/ask-agent/stream` take the same request body but return
Server-Sent Events instead of one JSON blob - the answer appears
token-by-token as the model writes it:
```powershell
curl -N -X POST http://localhost:8000/ask/stream -H "Content-Type: application/json" -d "{\"question\": \"What is the ransomware runbook about?\"}"
```
(`-N` disables curl's output buffering so you actually see it arrive
incrementally instead of all at once.) Each line is `data: {"type":
"answer", "content": "..."}` until a final `data: {"type": "sources", ...}`
and `data: [DONE]`. Streaming endpoints don't check the cache - they always
recompute, since caching a token stream is a different, more complex
problem than caching a finished answer.

## What's actually happening

1. `app/ingest_ph1.py` splits each `.txt` file into overlapping chunks and stores
   each chunk in Elasticsearch twice: once as plain text (for keyword search)
   and once as a vector (for semantic search).
2. `app/rag_ph1.py` takes your question, runs BOTH a keyword search and a
   semantic search against Elasticsearch, then merges the two ranked result
   lists using Reciprocal Rank Fusion (RRF) - see the big comment in that
   file for exactly how and why.
3. The top merged chunks get stuffed into a prompt and sent to your local
   chat model (`qwen2.5:7b` by default) via Ollama, which answers using only
   that context.
4. FastAPI (`app/main_ph1.py`) exposes this as a simple HTTP API.
5. For `/ask-agent`, `app/agent_ph2.py` wraps steps 2-3 in a LangGraph loop: a
   `think` node where the model decides which tool fits (or that it already
   has enough to answer), and an `act` node that runs whichever tool it
   picked - looping back to `think` after each one. `app/tools_ph2.py` defines
   the two tools it chooses between.
6. Phase 3 wraps both of those: `app/cache_ph3.py` checks/stores answers in
   Redis before/after steps 2-5 run, and `app/tracing_ph3.py` times the
   expensive steps so slow requests are debuggable. The `/stream` endpoints
   skip the cache and swap the one-shot Ollama/LangGraph call for their
   streaming equivalents, forwarding each token as it's generated.

## Troubleshooting

- `curl http://localhost:9200` fails -> Elasticsearch isn't up yet. Run
  `docker compose ps` to check container status, and `docker compose logs
  elasticsearch` if it's not healthy after a minute.
- Ingest script hangs or errors on `embed_text` -> Ollama isn't running, or
  the model wasn't pulled. Test with `ollama run nomic-embed-text` /
  `ollama run qwen2.5:7b` directly.
- Empty/weird answers -> check `docker compose logs elasticsearch` and make
  sure ingest actually ran (`python -m app.ingest_ph1`) before you started asking
  questions.
- `/ask-agent` gives an empty answer, skips a tool it should have called, or
  narrates a tool call as text instead of actually calling it -> this was the
  behavior with `llama3.2` (3B) on compound questions; `qwen2.5:7b` (the
  default) fixes it. If you deliberately switched to a smaller model via
  `CHAT_MODEL`, this is that model's tool-calling ceiling, not your setup -
  check `/ask` first: if that works, retrieval is fine.
- A repeat question doesn't come back instantly (`"cached": false` twice in
  a row) -> Redis isn't reachable. Check `docker compose ps` for
  `sentinel-redis`; the API still works either way, it just always
  recomputes.

## What's next (Phase 5)

Phase 4 wired `search_logs` up to real, live-ingested alerts (Redpanda ->
Elasticsearch's `security_live_alerts` index) instead of the Phase 2 mock
file. What's left:

- **Phase 5b** - PII redaction (next).
- **Phase 5c-e** - RBAC, CI/CD, Docker/Kubernetes. (5a, audit logging, is done.)

See `PROGRESS.md` for the detailed build log.
