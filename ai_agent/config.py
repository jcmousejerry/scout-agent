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

BASE_URL_CHAT = f"https://{WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
BASE_URL_RERANK = f"https://{WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/compatible-api/v1"

LLM_MODEL = "deepseek-v4-flash"
EMBEDDING_MODEL = "text-embedding-v4"
EMBEDDING_DIMENSION = 1024
RERANK_MODEL = "qwen3-rerank"

MILVUS_URI = os.path.join(BASE_DIR, "rag", "scout_knowledge.db")
COLLECTION_NAME = "football_theory"

KNOWLEDGE_FILE = os.path.join(PROJECT_DIR, "足球通识知识库.md")
