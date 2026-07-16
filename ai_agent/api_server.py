import os
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GRPC_TRACE"] = ""

# 抑制 MilvusLite gRPC 的 GOAWAY 警告（harmless，不影响功能）
import logging
logging.getLogger("milvus_lite").setLevel(logging.WARNING)
logging.getLogger("grpc").setLevel(logging.ERROR)

import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from agent import create_session, submit_answers, run_full_analysis
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("api")
logging.getLogger("faiss").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from rag.vector_store import get_client
        get_client()
        logger.info("Milvus initialized at startup")
    except Exception as e:
        logger.warning(f"Milvus init at startup failed (will retry on first request): {e}")
    yield


app = FastAPI(title="Scout Agent API v2", lifespan=lifespan)


class StartRequest(BaseModel):
    query: str
    candidate_count: int = 3


class AnswerRequest(BaseModel):
    session_id: str
    answers: dict
    candidate_count: int = 3


class AnalyzeRequest(BaseModel):
    session_id: str
    preferences_memory: Optional[str] = None


class StartResponse(BaseModel):
    session_id: str
    questions: list
    clarification_done: bool


class AnswerResponse(BaseModel):
    session_id: str
    questions: list
    clarification_done: bool
    answers: dict


@app.post("/api/scout/start", response_model=StartResponse)
async def scout_start(req: StartRequest):
    logger.info(f"Start session: {req.query[:80]}")
    result = create_session(req.query, candidate_count=req.candidate_count)
    return StartResponse(**result)


@app.post("/api/scout/answer", response_model=AnswerResponse)
async def scout_answer(req: AnswerRequest):
    logger.info(f"Answer for session {req.session_id}: {req.answers}")
    result = submit_answers(req.session_id, req.answers, candidate_count=req.candidate_count)
    return AnswerResponse(**result)


@app.post("/api/scout/analyze")
async def scout_analyze(req: AnalyzeRequest):
    logger.info(f"Analyze session {req.session_id}")

    def event_generator():
        try:
            for event in run_full_analysis(req.session_id, preferences_memory=req.preferences_memory):
                etype = event["event"]
                data = event["data"] if isinstance(event["data"], dict) else event.get("data", {})
                yield f"event: {etype}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


@app.get("/api/scout/session_query")
async def scout_session_query(session_id: str):
    """供 Go 后端反查某会话的用户原始查询文本，用于归档历史记录。"""
    from agent import get_session
    state = get_session(session_id)
    if not state:
        return {"session_id": session_id, "query": ""}
    return {"session_id": session_id, "query": state.get("original_query", "")}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
