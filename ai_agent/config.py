import os

from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

load_dotenv(os.path.join(PROJECT_DIR, ".env"))

API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
WORKSPACE_ID = os.getenv("DASHSCOPE_WORKSPACE_ID", "").strip()

if not API_KEY:
    raise RuntimeError("DASHSCOPE_API_KEY is not configured. Copy .env.example to .env and set it.")
if not WORKSPACE_ID:
    raise RuntimeError("DASHSCOPE_WORKSPACE_ID is not configured. Copy .env.example to .env and set it.")

API_HOST = os.getenv(
    "DASHSCOPE_API_HOST",
    f"{WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com",
).strip()
BASE_URL_CHAT = os.getenv(
    "DASHSCOPE_OPENAI_BASE_URL",
    f"https://{API_HOST}/compatible-mode/v1",
).strip().rstrip("/")
BASE_URL_RERANK = os.getenv(
    "DASHSCOPE_RERANK_BASE_URL",
    f"https://{API_HOST}/compatible-api/v1",
).strip().rstrip("/")

LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.7-max-preview").strip()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v4").strip()
EMBEDDING_DIMENSION = 1024
RERANK_MODEL = os.getenv("RERANK_MODEL", "qwen3-rerank").strip()

MILVUS_URI = os.path.join(BASE_DIR, "rag", "scout_knowledge.db")
COLLECTION_NAME = "football_theory"

KNOWLEDGE_DIR = os.path.join(PROJECT_DIR, "kb")
KNOWLEDGE_FILES = (
    os.path.join(KNOWLEDGE_DIR, "足球通识知识库.md"),
    os.path.join(KNOWLEDGE_DIR, "足球战术进阶知识库.md"),
)
