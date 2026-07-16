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
    doc_map = {}
    for i, r in enumerate(raw_results):
        entity = r.get("entity") or {}
        text = entity.get("text", "")
        if text:
            doc_id = f"doc_{i}"
            documents.append(text)
            doc_map[doc_id] = {
                "text": text,
                "name": entity.get("name", ""),
                "team": entity.get("team", ""),
                "position": entity.get("position", ""),
                "score": r.get("distance", 0),
            }

    reranked = rerank(query, documents, top_n=top_k_rerank)
    results = reranked.get("results", [])
    final = []
    for r in results:
        idx = r.get("index")
        doc = documents[idx] if idx < len(documents) else ""
        final.append({
            "text": doc,
            "relevance_score": r.get("relevance_score", 0),
        })
    return final
