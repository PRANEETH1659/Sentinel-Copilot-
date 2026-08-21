# SentinelCopilot - Hybrid RAG Core + Agent

An AI security-operations copilot that answers questions by hybrid-searching
(keyword + semantic) a knowledge base of incident reports and runbooks, then
asks a locally-running LLM to answer using only that retrieved context.

Two phases are built and working:

- **Phase 1** (`/ask`) - always runs one fixed hybrid search, then answers.
- **Phase 2** (`/ask-agent`) - a LangGraph agent decides *which* tool(s) to
  use (knowledge base, logs, or both) before it answers.

Both endpoints stay live side by side on purpose, so you can compare them.

**Cost: $0.** Everything below runs on your own machine.

## Prerequisites (do these once)

1. Docker Desktop installed and running (WSL2 backend)
2. Ollama installed, with two models pulled:
   ```
   ollama pull llama3.2
   ollama pull nomic-embed-text
   ```

## Run it

Open PowerShell in this project folder and run each step:

**1. Start Elasticsearch**
```powershell
docker compose up -d
```
Wait ~30 seconds for it to finish starting, then check it's healthy:
```powershell
curl http://localhost:9200
```
You should get back a JSON blob with a `"tagline" : "You Know, for Search"`.

**2. Create a virtual environment and install dependencies**
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**3. Ingest the sample documents**
```powershell
python -m app.ingest
```
This reads the 3 sample files in `sample_docs/`, splits them into chunks,
embeds each chunk with Ollama, and indexes them into Elasticsearch. You
should see output like `Indexed 4 chunks from incident_2026_0142.txt`.

**4. Start the API**
```powershell
uvicorn app.main:app --reload
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

## What's actually happening

1. `app/ingest.py` splits each `.txt` file into overlapping chunks and stores
   each chunk in Elasticsearch twice: once as plain text (for keyword search)
   and once as a vector (for semantic search).
2. `app/rag.py` takes your question, runs BOTH a keyword search and a
   semantic search against Elasticsearch, then merges the two ranked result
   lists using Reciprocal Rank Fusion (RRF) - see the big comment in that
   file for exactly how and why.
3. The top merged chunks get stuffed into a prompt and sent to your local
   Llama 3.2 model via Ollama, which answers using only that context.
4. FastAPI (`app/main.py`) exposes this as a simple HTTP API.
5. For `/ask-agent`, `app/agent.py` wraps steps 2-3 in a LangGraph loop: a
   `think` node where the model decides which tool fits (or that it already
   has enough to answer), and an `act` node that runs whichever tool it
   picked - looping back to `think` after each one. `app/tools.py` defines
   the two tools it chooses between.

## Troubleshooting

- `curl http://localhost:9200` fails -> Elasticsearch isn't up yet. Run
  `docker compose ps` to check container status, and `docker compose logs
  elasticsearch` if it's not healthy after a minute.
- Ingest script hangs or errors on `embed_text` -> Ollama isn't running, or
  the model wasn't pulled. Test with `ollama run nomic-embed-text` /
  `ollama run llama3.2` directly.
- Empty/weird answers -> check `docker compose logs elasticsearch` and make
  sure ingest actually ran (`python -m app.ingest`) before you started asking
  questions.
- `/ask-agent` gives an empty answer or picks odd tools -> smaller local
  models are hit-and-miss at emitting well-formed tool calls. Check `/ask`
  first: if that works, retrieval is fine and it's the model's tool-calling,
  not your setup.

## What's next (Phase 3+)

Phase 2's `search_logs` currently reads a small local mock file
(`sample_logs/mock_logs.json`). Still ahead:

- **Phase 3** - production hardening: Redis caching, streaming responses,
  latency tracing.
- **Phase 4** - event-driven ingestion: Kafka/Redpanda feeding live alerts,
  which is what `search_logs` will read from instead of the mock file.
- **Phase 5** - governance and deployment: audit logging, RBAC, PII
  redaction, Docker/Kubernetes, CI/CD.

See `PROGRESS.md` for the detailed build log.
