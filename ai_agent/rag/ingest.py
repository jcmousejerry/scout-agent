import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import KNOWLEDGE_FILE
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

    chunks = parse_knowledge_chunks(KNOWLEDGE_FILE)
    texts = [c["text"] for c in chunks]
    metadatas = [{"section": c["section"]} for c in chunks]

    print(f"Parsed {len(chunks)} knowledge chunks. Generating embeddings...")
    embeddings = embed_texts(texts)
    count = insert_embeddings(embeddings, texts, metadatas)
    print(f"Ingested {count} chunks into Milvus.")

    seen = set()
    for c in chunks:
        s = c["section"]
        if s and s not in seen:
            print(f"  [{s}] ({len(c['text'])} chars)")
            seen.add(s)


if __name__ == "__main__":
    ingest()
