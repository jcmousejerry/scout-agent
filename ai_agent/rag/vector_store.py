import logging
import os
import shutil
import threading

logging.getLogger("faiss").setLevel(logging.WARNING)
logging.getLogger("faiss.loader").setLevel(logging.WARNING)

from pymilvus import MilvusClient
from config import MILVUS_URI, COLLECTION_NAME, EMBEDDING_DIMENSION

logger = logging.getLogger("vector_store")

_client = None
_lock = threading.Lock()


def _create_client():
    c = MilvusClient(MILVUS_URI)
    if COLLECTION_NAME not in c.list_collections():
        c.create_collection(
            collection_name=COLLECTION_NAME,
            dimension=EMBEDDING_DIMENSION,
            metric_type="COSINE",
        )
    c.load_collection(COLLECTION_NAME)
    logger.info(f"MilvusClient initialized, collection '{COLLECTION_NAME}' loaded")
    return c


def get_client():
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = _create_client()
    return _client


def drop_collection():
    """Reset the local Milvus Lite store before a full knowledge rebuild."""
    global _client
    if _client is not None:
        try:
            _client.close()
        finally:
            _client = None

    # This database contains only the generated knowledge collection. Recreating
    # it is more reliable than drop_collection on Windows, where Milvus Lite can
    # leave a manifest.json.tmp that prevents the collection from being dropped.
    if os.path.isdir(MILVUS_URI):
        shutil.rmtree(MILVUS_URI)
    elif os.path.isfile(MILVUS_URI):
        os.remove(MILVUS_URI)
    _client = None


def ensure_collection():
    return get_client()


def insert_embeddings(embeddings, texts, metadatas):
    client = ensure_collection()
    data = []
    for i, (emb, txt, meta) in enumerate(zip(embeddings, texts, metadatas)):
        data.append({
            "id": i,
            "vector": emb,
            "text": txt,
            **meta,
        })
    client.insert(collection_name=COLLECTION_NAME, data=data)
    return len(data)


def search(query_embedding, top_k=20):
    global _client
    for attempt in range(2):
        try:
            client = get_client()
            results = client.search(
                collection_name=COLLECTION_NAME,
                data=[query_embedding],
                limit=top_k,
                output_fields=["text", "source", "section"],
            )
            return results[0]
        except Exception as e:
            if attempt == 0:
                logger.warning(f"Milvus search failed, recreating client: {e}")
                with _lock:
                    _client = None
            else:
                raise
