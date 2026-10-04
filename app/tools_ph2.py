# THIS FILE DEFINES THE TOOLS THE PHASE-2 AGENT CAN CHOOSE BETWEEN.
#
# Each tool below is just a normal Python function with a @tool decorator
# and a docstring. The docstring is NOT a comment for humans here - it's
# the "label on the toolbox" the AI model actually reads when deciding
# which tool fits a question. Keep these descriptions specific; a vague
# description is the #1 reason an agent picks the wrong tool.

from langchain_core.tools import tool

from . import config_ph1 as config
from .rag_ph1 import hybrid_search

# ---------------------------------------------------------------------------
# Tool 1: the SAME Elasticsearch hybrid search from Phase 1 (BM25 + kNN +
# Reciprocal Rank Fusion, all still living in app/rag_ph1.py). Nothing about the
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
# Tool 2: search_logs. Phase 4's consumer (app/consumer_ph4.py) chunks and
# embeds every live-ingested alert into its own Elasticsearch index
# (config.ES_ALERTS_INDEX, separate from the knowledge-base index above) -
# this just points the SAME hybrid_search used by search_knowledge_base at
# that index instead, so live alerts get the same BM25+kNN+RRF retrieval
# quality without duplicating any search logic.
# ---------------------------------------------------------------------------


@tool
def search_logs(keyword: str) -> str:
    """Search recent system activity logs for a keyword, such as a hostname,
    username, or process name. Use this for questions about live or recent
    system/server activity. Do NOT use this for questions about written
    documents, policies, or runbooks - use search_knowledge_base for those."""
    chunks = hybrid_search(keyword, top_n=5, index=config.ES_ALERTS_INDEX)
    if not chunks:
        return f"No log entries found matching '{keyword}'."

    return "\n".join(
        f"[{c['_source'].get('received_at', 'unknown time')}] ({c['_source']['source']}) {c['_source']['text']}"
        for c in chunks
    )
