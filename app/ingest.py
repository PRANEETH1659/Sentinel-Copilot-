#PURPOSE OF THE FILE -- CHUNKING THE SENTENCES. 

import glob
import os

from . import config
from .embeddings import embed_text
from .es_client import ensure_index, get_client


def chunk_text(
    text: str,
    size: int = config.CHUNK_SIZE_CHARS,
    overlap: int = config.CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """
    Splits a long document into overlapping chunks. Two reasons this matters:

    1. Embedding an entire multi-page document into ONE vector blurs its
       meaning - the vector ends up being a vague average of everything in
       the doc, matching nothing well.
    2. Smaller chunks give more PRECISE retrieval - you want to hand the LLM
       the 3 relevant sentences, not a whole document, so it isn't distracted
       by irrelevant surrounding text.

    The overlap exists so a sentence that lands right on a chunk boundary
    doesn't get awkwardly split in half and lose its meaning in both pieces.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return [c.strip() for c in chunks if c.strip()]


def run_ingest(docs_dir: str = "sample_docs"):
    es = get_client()
    ensure_index(es)

    files = glob.glob(os.path.join(docs_dir, "*.txt"))
    print(f"Found {len(files)} document(s) to ingest\n")

    total_chunks = 0
    for filepath in files:
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            vector = embed_text(chunk)
            es.index(
                index=config.ES_INDEX,
                document={
                    "text": chunk,
                    "embedding": vector,
                    "source": filename,
                    "chunk_id": f"{filename}::{i}",
                },
            )
            total_chunks += 1
        print(f"  Indexed {len(chunks)} chunks from {filename}")

    # refresh makes newly indexed docs immediately searchable (normally ES
    # does this automatically every 1s, but we force it for a clean demo)
    es.indices.refresh(index=config.ES_INDEX)
    print(f"\nDone. {total_chunks} chunks indexed into '{config.ES_INDEX}'.")


if __name__ == "__main__":
    run_ingest()
