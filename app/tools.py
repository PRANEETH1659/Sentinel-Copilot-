# THIS FILE DEFINES THE TOOLS THE PHASE-2 AGENT CAN CHOOSE BETWEEN.
#
# Each tool below is just a normal Python function with a @tool decorator
# and a docstring. The docstring is NOT a comment for humans here - it's
# the "label on the toolbox" the AI model actually reads when deciding
# which tool fits a question. Keep these descriptions specific; a vague
# description is the #1 reason an agent picks the wrong tool.

import json
import os

from langchain_core.tools import tool

from .rag import hybrid_search

# ---------------------------------------------------------------------------
# Tool 1: the SAME Elasticsearch hybrid search from Phase 1 (BM25 + kNN +
# Reciprocal Rank Fusion, all still living in app/rag.py). Nothing about the
# search itself changed - it's just wrapped so the agent can call it as one
# option instead of it being the only, hardcoded step.
# ---------------------------------------------------------------------------


@tool
def search_knowledge_base(query: str) -> str:
    """Search the security knowledge base of written runbooks, policies, and
    past incident reports. Use this for questions about documented
    procedures, past incidents, or "what should I do if..." style questions.
    Do NOT use this for questions about live or recent system activity."""
    chunks = hybrid_search(query, top_n=5)
    if not chunks:
        return "No relevant documents found in the knowledge base."

    return "\n\n".join(
        f"[Source: {c['_source']['source']}]\n{c['_source']['text']}"
        for c in chunks
    )


# ---------------------------------------------------------------------------
# Tool 2: search_logs. Phase 4 will wire this up to a real, live event
# stream (Kafka/Redpanda). For now it just reads a small local JSON file of
# made-up sample log lines - that's enough to give the agent a genuinely
# different second tool to weigh against the first one. The point of Phase 2
# is the DECIDING between tools, not the data source behind each tool.
# ---------------------------------------------------------------------------

LOGS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "sample_logs", "mock_logs.json"
)


@tool
def search_logs(keyword: str) -> str:
    """Search recent system activity logs for a keyword, such as a hostname,
    username, or process name. Use this for questions about live or recent
    system/server activity. Do NOT use this for questions about written
    documents, policies, or runbooks - use search_knowledge_base for those."""
    with open(LOGS_PATH, "r", encoding="utf-8") as f:
        logs = json.load(f)

    matches = [
        entry for entry in logs if keyword.lower() in json.dumps(entry).lower()
    ]

    if not matches:
        return f"No log entries found matching '{keyword}'."

    return "\n".join(
        f"[{m['timestamp']}] {m['host']} - {m['event']}" for m in matches
    )
