# THIS FILE IS THE BRAIN OF THE PROJECT.
# It ties chunking ,searching, and LLM together into one final answer.


import requests

from . import config
from .embeddings import embed_text
from .es_client import bm25_search, get_client, knn_search



#Purpose the method is 
# A chunk that appears near the top of both BM25 and KNN results gets the high combined score.
# A chunk that only shows up in one list, and near the bottom,gets a lower combined score .

def reciprocal_rank_fusion(result_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """
    Merges multiple ranked result lists (e.g. BM25 results + kNN results)
    into a single ranked list.

    The key idea: it only ever looks at each result's RANK (its position -
    1st, 2nd, 3rd...) in each list, never its raw score. That matters because
    BM25 scores (roughly 0-40, unbounded) and cosine similarity scores (0-1)
    live on completely different scales and can't be compared directly. Rank
    position, on the other hand, always means the same thing regardless of
    scale.

    Formula, per document: sum over every list it appears in of 1 / (k + rank)
    k=60 is the constant from the original RRF paper - it just softens the
    weight of very top-ranked hits so a single list can't totally dominate
    the fused ranking.
    """
    fused_scores: dict[str, float] = {}
    doc_lookup: dict[str, dict] = {}

    for results in result_lists:
        for rank, hit in enumerate(results):
            doc_id = hit["_id"]
            doc_lookup[doc_id] = hit
            fused_scores.setdefault(doc_id, 0.0)
            fused_scores[doc_id] += 1.0 / (k + rank)

    ranked_ids = sorted(fused_scores, key=lambda d: fused_scores[d], reverse=True)
    return [doc_lookup[doc_id] for doc_id in ranked_ids]


def hybrid_search(query: str, top_n: int = 5) -> list[dict]:
    es = get_client()
    query_vector = embed_text(query)

    bm25_hits = bm25_search(es, query, k=10)
    knn_hits = knn_search(es, query_vector, k=10)

    fused = reciprocal_rank_fusion([bm25_hits, knn_hits])
    return fused[:top_n]


def build_prompt(question: str, context_chunks: list[dict]) -> str:
    context_text = "\n\n".join(
        f"[Source: {c['_source']['source']}]\n{c['_source']['text']}"
        for c in context_chunks
    )
    return f"""You are a security operations assistant. Answer the question using \
ONLY the context below. If the context doesn't contain the answer, say so \
clearly instead of guessing. Mention which source file each fact comes from.

Context:
{context_text}

Question: {question}

Answer:"""


def ask_ollama(prompt: str) -> str:
    resp = requests.post(
        f"{config.OLLAMA_URL}/api/generate",
        json={"model": config.CHAT_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def answer_question(question: str) -> dict:
    top_chunks = hybrid_search(question)

    if not top_chunks:
        return {
            "answer": "I couldn't find anything relevant in the knowledge base.",
            "sources": [],
        }

    prompt = build_prompt(question, top_chunks)
    answer = ask_ollama(prompt)
    sources = sorted({c["_source"]["source"] for c in top_chunks})

    return {"answer": answer, "sources": sources}
