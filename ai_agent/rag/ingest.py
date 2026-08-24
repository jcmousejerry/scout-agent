import re
import sys
import os
import hashlib
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    COLLECTION_NAME,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    KNOWLEDGE_FILES,
    MILVUS_URI,
)
from embedding_client import embed_texts
from rag.vector_store import insert_embeddings, drop_collection


MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".scout_knowledge_manifest.json")


def calculate_source_signature():
    digest = hashlib.sha256()
    digest.update(COLLECTION_NAME.encode("utf-8"))
    digest.update(EMBEDDING_MODEL.encode("utf-8"))
    digest.update(str(EMBEDDING_DIMENSION).encode("ascii"))
    for filepath in KNOWLEDGE_FILES:
        digest.update(os.path.basename(filepath).encode("utf-8"))
        with open(filepath, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def index_is_current():
    if not os.path.exists(MILVUS_URI) or not os.path.isfile(MANIFEST_PATH):
        return False
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        return manifest.get("source_signature") == calculate_source_signature()
    except (OSError, ValueError):
        return False


def write_manifest(chunk_count):
    manifest = {
        "source_signature": calculate_source_signature(),
        "collection": COLLECTION_NAME,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "chunk_count": chunk_count,
        "sources": [os.path.basename(path) for path in KNOWLEDGE_FILES],
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def parse_knowledge_chunks(filepath, chunk_size=5):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    chunks = []
    current_section = ""
    current_lines = []

    for line in lines:
        if line.startswith("## "):
            if current_lines:
                chunks.append({
                    "section": current_section,
                    "text": "\n".join(current_lines),
                })
            current_section = re.sub(r"^##\s+", "", line).strip()
            current_lines = [line]
        elif line.startswith("### "):
            if current_lines and len(current_lines) >= chunk_size:
                chunks.append({
                    "section": current_section,
                    "text": "\n".join(current_lines),
                })
                current_lines = [line]
            else:
                current_lines.append(line)
        else:
            current_lines.append(line)

    if current_lines:
        chunks.append({
            "section": current_section,
            "text": "\n".join(current_lines),
        })

    return chunks


def ingest():
    print("Dropping existing collection...")
    drop_collection()

    chunks = []
    for filepath in KNOWLEDGE_FILES:
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Knowledge file not found: {filepath}")
        source = os.path.basename(filepath)
        file_chunks = parse_knowledge_chunks(filepath)
        for chunk in file_chunks:
            chunk["source"] = source
        chunks.extend(file_chunks)

    texts = [c["text"] for c in chunks]
    metadatas = [
        {"source": c["source"], "section": c["section"]}
        for c in chunks
    ]

    print(f"Parsed {len(chunks)} knowledge chunks. Generating embeddings...")
    embeddings = embed_texts(texts)
    count = insert_embeddings(embeddings, texts, metadatas)
    write_manifest(count)
    print(f"Ingested {count} chunks into Milvus.")

    seen = set()
    for c in chunks:
        label = (c["source"], c["section"])
        if c["section"] and label not in seen:
            print(f"  [{c['source']} > {c['section']}] ({len(c['text'])} chars)")
            seen.add(label)


if __name__ == "__main__":
    if "--check" in sys.argv:
        if index_is_current():
            print("Knowledge vector index is current.")
            raise SystemExit(0)
        print("Knowledge vector index is missing or stale.")
        raise SystemExit(1)
    ingest()
