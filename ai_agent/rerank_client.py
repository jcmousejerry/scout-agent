import requests
from config import API_KEY, BASE_URL_RERANK, RERANK_MODEL


def rerank(query, documents, top_n=10):
    url = f"{BASE_URL_RERANK}/reranks"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": RERANK_MODEL,
        "query": query,
        "documents": documents,
        "top_n": top_n,
    }
    resp = requests.post(url, headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()
