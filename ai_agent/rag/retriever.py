import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from embedding_client import embed_texts
from rerank_client import rerank
from rag.vector_store import search


def retrieve(query, top_k_raw=20, top_k_rerank=10):
    q_emb = embed_texts([query])[0]
    raw_results = search(q_emb, top_k=top_k_raw)

    documents = []
    document_metadata = []
    for r in raw_results:
        entity = r.get("entity") or {}
        text = entity.get("text", "")
        if text:
            documents.append(text)
            document_metadata.append({
                "source": entity.get("source", ""),
                "section": entity.get("section", ""),
                "score": r.get("distance", 0),
            })

    if not documents:
        return []

    reranked = rerank(query, documents, top_n=top_k_rerank)
    results = reranked.get("results", [])
    final = []
    for r in results:
        idx = r.get("index")
        if not isinstance(idx, int) or not 0 <= idx < len(documents):
            continue
        metadata = document_metadata[idx]
        final.append({
            "text": documents[idx],
            "source": metadata["source"],
            "section": metadata["section"],
            "relevance_score": r.get("relevance_score", 0),
        })
    return final
