import json
import logging
import time

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent_ph2 import ask_agent, ask_agent_stream
from .alerts_ph4 import ensure_alerts_index
from . import config_ph1 as config
from .audit_ph5 import ensure_audit_index, flush_audit, record_audit
from .auth_ph5 import Principal, require
from .cache_ph3 import (
    ensure_cache_index,
    get_cached_answer,
    get_client as get_redis_client,
    set_cached_answer,
)
from .es_client_ph1 import get_client as get_es_client
from .pii_ph5 import redact_text
from .rag_ph1 import answer_question, answer_question_stream

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="SentinelCopilot", version="0.5.0")


@app.on_event("startup")
def _ensure_indices():
    """Two ES indices are written to from OUTSIDE the request that first
    needs them, so both must exist before that happens, not get lazily (and
    wrongly - dynamic mapping wouldn't make `embedding` a dense_vector)
    auto-created on first write: the semantic cache (app/cache_ph3.py,
    written on every /ask or /ask-agent) and live alerts (app/alerts_ph4.py,
    normally written by the standalone `python -m app.consumer_ph4` process,
    which might not have run yet on a fresh clone)."""
    ensure_cache_index(get_es_client())
    ensure_alerts_index(get_es_client())
    ensure_audit_index(get_es_client())


@app.on_event("shutdown")
def _flush_audit():
    flush_audit()


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
    """Public on purpose: Docker/Kubernetes health checks call this without a key."""
    return {"status": "ok"}


@app.get("/whoami")
def whoami(principal: Principal = Depends(require("ask"))):
    """Phase 5c: quick way to check which user/role your API key maps to."""
    return {"user": principal.user, "role": principal.role}


@app.get("/audit")
def read_audit(
    principal: Principal = Depends(require("audit")),
    limit: int = Query(20, ge=1, le=200),
    status: str | None = Query(None, description="ok | error | denied"),
    user: str | None = None,
    endpoint: str | None = None,
):
    """Phase 5c: admin-only view of the Phase 5a audit trail, newest first.
    Questions in it are already PII-redacted (Phase 5b). Reading the audit
    log is itself NOT audited here - add that if auditors must be audited."""
    filters = [
        {"term": {field: value}}
        for field, value in (("status", status), ("user", user), ("endpoint", endpoint))
        if value
    ]
    resp = get_es_client().search(
        index=config.ES_AUDIT_INDEX,
        size=limit,
        sort=[{"timestamp": {"order": "desc"}}],
        query={"bool": {"filter": filters}} if filters else {"match_all": {}},
    )
    hits = resp["hits"]["hits"]
    return {"count": len(hits), "events": [h["_source"] for h in hits]}


def _client_of(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _audited(endpoint: str, question: str, request: Request, principal: Principal, compute):
    """Phase 5a: runs `compute()` (which returns the response dict) and
    publishes one audit event about it - success or failure. The audit
    publish never raises (see app/audit_ph5.py), so it can't break a request.
    Phase 5c: also records WHO asked (user + role from their API key)."""
    start = time.perf_counter()
    who = {"user": principal.user, "role": principal.role}
    try:
        result = compute()
    except Exception as exc:
        record_audit(
            endpoint=endpoint,
            question=question,
            client=_client_of(request),
            **who,
            status="error",
            duration_ms=(time.perf_counter() - start) * 1000,
            error=str(exc)[:500],
        )
        raise
    record_audit(
        endpoint=endpoint,
        question=question,
        client=_client_of(request),
        **who,
        cached=result["cached"],
        sources=result["sources"],
        answer_chars=len(result["answer"]),
        duration_ms=(time.perf_counter() - start) * 1000,
    )
    return result


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, request: Request, principal: Principal = Depends(require("ask"))):
    """Phase 1: always runs one fixed hybrid search, then answers. Phase 3
    adds a Redis cache check in front of it. Phase 5a audits every call."""

    def compute():
        redis_client = get_redis_client()
        cached = get_cached_answer(redis_client, "ask", req.question)
        if cached is not None:
            return {**cached, "cached": True}
        result = answer_question(req.question)
        set_cached_answer(redis_client, "ask", req.question, result)
        return {**result, "cached": False}

    return _audited("ask", req.question, request, principal, compute)


@app.post("/ask-agent", response_model=AskResponse)
def ask_agent_endpoint(
    req: AskRequest, request: Request, principal: Principal = Depends(require("ask"))
):
    """Phase 2: the model decides which tool(s) to use - knowledge base,
    logs, or both - possibly looping through more than one, before it
    answers. Phase 3 adds a Redis cache check in front of it. Phase 5a
    audits every call."""

    def compute():
        redis_client = get_redis_client()
        cached = get_cached_answer(redis_client, "ask-agent", req.question)
        if cached is not None:
            return {**cached, "cached": True}
        result = ask_agent(req.question)
        set_cached_answer(redis_client, "ask-agent", req.question, result)
        return {**result, "cached": False}

    return _audited("ask-agent", req.question, request, principal, compute)


def _sse(generator, endpoint: str, question: str, client: str, principal: Principal):
    """Wraps a {"type", "content"} event generator as Server-Sent Events
    (`data: <json>\\n\\n` per event, `data: [DONE]\\n\\n` to close), logs
    the total stream time once it's done, and (Phase 5a) publishes one audit
    event built from what actually streamed out."""
    start = time.perf_counter()
    answer_chars = 0
    sources: list[str] = []
    status, error = "ok", None
    try:
        for event in generator:
            if event.get("type") == "answer":
                answer_chars += len(event.get("content") or "")
            elif event.get("type") == "sources":
                sources = list(event.get("content") or [])
            yield f"data: {json.dumps(event)}\n\n"
    except Exception as exc:
        status, error = "error", str(exc)[:500]
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        record_audit(
            endpoint=f"{endpoint}/stream",
            question=question,
            client=client,
            user=principal.user,
            role=principal.role,
            status=status,
            sources=sources,
            answer_chars=answer_chars,
            duration_ms=elapsed_ms,
            error=error,
        )
    logging.getLogger("sentinelcopilot").info(
        "%s question=%r stream total=%.1fms", endpoint, redact_text(question), elapsed_ms
    )
    yield "data: [DONE]\n\n"


@app.post("/ask/stream")
def ask_stream(req: AskRequest, request: Request, principal: Principal = Depends(require("ask"))):
    """Same as /ask, but the answer streams back token-by-token (Server-Sent
    Events) instead of waiting for the whole thing. Bypasses the Redis cache
    on purpose - caching a token stream (store it, then replay it at the
    same pace vs. all at once?) is real complexity that isn't worth it here;
    every /ask/stream call recomputes."""
    return StreamingResponse(
        _sse(answer_question_stream(req.question), "ask", req.question, _client_of(request), principal),
        media_type="text/event-stream",
    )


@app.post("/ask-agent/stream")
def ask_agent_stream_endpoint(
    req: AskRequest, request: Request, principal: Principal = Depends(require("ask"))
):
    """Same as /ask-agent, but streams the model's answer tokens as they're
    generated. Also bypasses the Redis cache, for the same reason as
    /ask/stream."""
    return StreamingResponse(
        _sse(ask_agent_stream(req.question), "ask-agent", req.question, _client_of(request), principal),
        media_type="text/event-stream",
    )
