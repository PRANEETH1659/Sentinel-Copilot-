# SentinelCopilot - Phase 1: Hybrid RAG Core

An AI security-operations copilot that answers questions by hybrid-searching
(keyword + semantic) a knowledge base of incident reports and runbooks, then
asks a locally-running LLM to answer using only that retrieved context.

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

## What's next (Phase 2)

Once this is working end-to-end, we'll wrap it in a LangGraph agent that can
decide *which* tool to use (search knowledge base vs. search live logs vs.
summarize) instead of always doing a single fixed retrieval step - that's
what turns this from "a search box" into "a copilot."
