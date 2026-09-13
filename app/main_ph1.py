import json
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent_ph2 import ask_agent, ask_agent_stream
from .cache_ph3 import (
    ensure_cache_index,
    get_cached_answer,
    get_client as get_redis_client,
    set_cached_answer,
)
from .es_client_ph1 import get_client as get_es_client
from .rag_ph1 import answer_question, answer_question_stream

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="SentinelCopilot", version="0.3.0")


@app.on_event("startup")
def _ensure_semantic_cache_index():
    """The semantic cache (app/cache_ph3.py) writes into its own ES index on
    every /ask or /ask-agent call - it needs to exist before the first
    request, not get lazily created mid-request."""
    ensure_cache_index(get_es_client())


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    cached: bool = False
    timings: dict[str, float] = {}


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Phase 3: every response gets an X-Process-Time header (in ms), and
    every request gets one summary log line - cheap, request-level
    observability on top of the per-step timings /ask and /ask-agent
    already return in their body."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time"] = f"{elapsed_ms:.1f}"
    logging.getLogger("sentinelcopilot").info(
        "%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code, elapsed_ms
    )
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """Phase 1: always runs one fixed hybrid search, then answers. Phase 3
    adds a Redis cache check in front of it."""
    redis_client = get_redis_client()
    cached = get_cached_answer(redis_client, "ask", req.question)
    if cached is not None:
        return {**cached, "cached": True}

    result = answer_question(req.question)
    set_cached_answer(redis_client, "ask", req.question, result)
    return {**result, "cached": False}


@app.post("/ask-agent", response_model=AskResponse)
def ask_agent_endpoint(req: AskRequest):
    """Phase 2: the model decides which tool(s) to use - knowledge base,
    logs, or both - possibly looping through more than one, before it
    answers. Phase 3 adds a Redis cache check in front of it."""
    redis_client = get_redis_client()
    cached = get_cached_answer(redis_client, "ask-agent", req.question)
    if cached is not None:
        return {**cached, "cached": True}

    result = ask_agent(req.question)
    set_cached_answer(redis_client, "ask-agent", req.question, result)
    return {**result, "cached": False}


def _sse(generator, endpoint: str, question: str):
    """Wraps a {"type", "content"} event generator as Server-Sent Events
    (`data: <json>\\n\\n` per event, `data: [DONE]\\n\\n` to close) and logs
    the total stream time once it's done."""
    start = time.perf_counter()
    for event in generator:
        yield f"data: {json.dumps(event)}\n\n"
    elapsed_ms = (time.perf_counter() - start) * 1000
    logging.getLogger("sentinelcopilot").info(
        "%s question=%r stream total=%.1fms", endpoint, question, elapsed_ms
    )
    yield "data: [DONE]\n\n"


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    """Same as /ask, but the answer streams back token-by-token (Server-Sent
    Events) instead of waiting for the whole thing. Bypasses the Redis cache
    on purpose - caching a token stream (store it, then replay it at the
    same pace vs. all at once?) is real complexity that isn't worth it here;
    every /ask/stream call recomputes."""
    return StreamingResponse(
        _sse(answer_question_stream(req.question), "ask", req.question),
        media_type="text/event-stream",
    )


@app.post("/ask-agent/stream")
def ask_agent_stream_endpoint(req: AskRequest):
    """Same as /ask-agent, but streams the model's answer tokens as they're
    generated. Also bypasses the Redis cache, for the same reason as
    /ask/stream."""
    return StreamingResponse(
        _sse(ask_agent_stream(req.question), "ask-agent", req.question),
        media_type="text/event-stream",
    )
