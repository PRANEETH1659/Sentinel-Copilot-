#PURPOSE OF THE FILE - CONVERTING THE CHUNKS INTO VECTORS (it is called in (ingest.py))

import requests

from . import config


def embed_text(text: str) -> list[float]:
    """
    Turns text into a vector using Ollama's local embedding model.

    This is the free, local replacement for OpenAI's embeddings API - same
    concept (text in, list-of-numbers out, similar texts get similar
    vectors), just running entirely on your machine with zero API cost.
    """
    resp = requests.post(
        f"{config.OLLAMA_URL}/api/embeddings",
        json={"model": config.EMBED_MODEL, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]
