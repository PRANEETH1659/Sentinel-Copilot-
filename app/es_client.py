
#THIS FILE PRIMARY USE IS ,Functionality of Elastic Search 
#step-1: connection and setting up. like creating table
#step-2:desiging blue print and what columns need to be stored
#step-3:Defining Methods BM25 and KNN 
#step-4:Using them ,whereever they called.




from elasticsearch import Elasticsearch

from . import config


def get_client() -> Elasticsearch:
    return Elasticsearch(config.ES_URL)


# Each document (chunk) gets THREE fields:
#   text      -> plain text, searched via BM25 (keyword/lexical search)
#   embedding -> a vector, searched via kNN (semantic search)
#   source    -> which file this chunk came from, so we can cite it later
INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "text": {"type": "text"},
            "embedding": {
                "type": "dense_vector",
                "dims": config.EMBED_DIMS,
                "index": True,
                "similarity": "cosine",
            },
            "source": {"type": "keyword"},
            "chunk_id": {"type": "keyword"},
        }
    }
}


def ensure_index(es: Elasticsearch):
    if not es.indices.exists(index=config.ES_INDEX):
        es.indices.create(index=config.ES_INDEX, body=INDEX_MAPPING)
        print(f"Created index '{config.ES_INDEX}'")
    else:
        print(f"Index '{config.ES_INDEX}' already exists - reusing it")


def bm25_search(es: Elasticsearch, query: str, k: int = 10):
    """Keyword search. Great at exact terms like 'CVE-2024-3400' or 'PsExec'."""
    resp = es.search(
        index=config.ES_INDEX,
        query={"match": {"text": query}},
        size=k,
    )
    return resp["hits"]["hits"]


def knn_search(es: Elasticsearch, query_vector: list[float], k: int = 10):
    """Semantic search. Finds meaning-matches even with zero shared keywords -
    e.g. 'what do I do if a laptop gets encrypted by malware' will still
    match a document about 'ransomware response' with no words in common."""
    resp = es.search(
        index=config.ES_INDEX,
        knn={
            "field": "embedding",
            "query_vector": query_vector,
            "k": k,
            "num_candidates": 50,
        },
        size=k,
    )
    return resp["hits"]["hits"]
