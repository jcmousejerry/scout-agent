import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import KNOWLEDGE_FILES
from embedding_client import embed_texts
from rag.vector_store import insert_embeddings, drop_collection


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
    print(f"Ingested {count} chunks into Milvus.")

    seen = set()
    for c in chunks:
        label = (c["source"], c["section"])
        if c["section"] and label not in seen:
            print(f"  [{c['source']} > {c['section']}] ({len(c['text'])} chars)")
            seen.add(label)


if __name__ == "__main__":
    ingest()
