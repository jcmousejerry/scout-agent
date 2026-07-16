from openai import OpenAI
from config import API_KEY, BASE_URL_CHAT, EMBEDDING_MODEL, EMBEDDING_DIMENSION

client = OpenAI(api_key=API_KEY, base_url=BASE_URL_CHAT)

BATCH_SIZE = 10


def embed_texts(texts):
    if isinstance(texts, str):
        texts = [texts]
    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        resp = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch,
            dimensions=EMBEDDING_DIMENSION,
        )
        all_embeddings.extend([item.embedding for item in resp.data])
    return all_embeddings
