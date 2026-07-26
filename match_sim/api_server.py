#!/usr/bin/env python
"""FastAPI server for the match simulation module.

Provides:
  - GET /match-sim/teams          — list all teams
  - GET /match-sim/teams/{id}     — team detail with players
  - POST /match-sim/match/create  — create a new match
  - GET /match-sim/match/{session_id}/events — SSE stream of match events
  - GET /match-sim/match/{session_id}/state  — current match state (REST)
  - POST /match-sim/match/{session_id}/adjust — make a tactical adjustment
  - POST /match-sim/match/{session_id}/pause  — pause match
  - POST /match-sim/match/{session_id}/resume — resume match
  - POST /match-sim/match/{session_id}/stop   — stop match
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

# Ensure match_sim is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_all_teams, get_team, get_team_players, get_team_starters, get_team_subs, get_match_by_session, init_db
from models import Player
from seed_data import seed_all as seed_all_teams
from match_engine import MatchEngine

logger = logging.getLogger("match_sim.api_server")

# ── In-memory stores ────────────────────────────────────────────────────

# Active match engines keyed by session_id
active_matches: Dict[str, MatchEngine] = {}

# SSE subscriber queues keyed by session_id
sse_clients: Dict[str, list] = {}


# ── SSE helpers ─────────────────────────────────────────────────────────

def _sse_payload(event_type: str, data: dict) -> str:
    """Format an SSE message."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _broadcast(session_id: str, event_type: str, data: dict):
    """Push an SSE message to all subscribers of a match session.

    This is passed as the emit callback to MatchEngine.
    """
    if session_id not in sse_clients:
        return
    payload = _sse_payload(event_type, data)
    dead: list = []
    for queue in sse_clients[session_id]:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(queue)
    for q in dead:
        if q in sse_clients.get(session_id, []):
            sse_clients[session_id].remove(q)


# ── App lifecycle ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    logger.info("Match Sim API starting...")
    init_db()
    seed_all_teams()
    logger.info("Database initialized and seeded")
    yield
    # Shutdown: stop all running matches
    for session_id, engine in list(active_matches.items()):
        engine.stop()
    active_matches.clear()
    sse_clients.clear()
    logger.info("Match Sim API shut down")


app = FastAPI(
    title="Scout Agent - Match Simulation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Team endpoints ──────────────────────────────────────────────────────

@app.get("/match-sim/teams")
async def list_teams():
    """List all available teams."""
    teams = get_all_teams()
    return {"teams": teams}


@app.get("/match-sim/teams/{team_id}")
async def team_detail(team_id: int):
    """Get team detail with players."""
    team = get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    players = get_team_players(team_id)
    starters = [p for p in players if p.get("is_starter")]
    subs = [p for p in players if not p.get("is_starter")]
    return {
        "team": team,
        "starters": starters,
        "substitutes": subs,
    }


# ── Match creation ──────────────────────────────────────────────────────

@app.post("/match-sim/match/create")
async def create_match(request: Request):
    """Create a new match and start simulation."""
    body = await request.json()
    home_team_id = body.get("home_team_id")
    away_team_id = body.get("away_team_id")
    home_formation = body.get("home_formation", "4-3-3")
    away_formation = body.get("away_formation", "4-3-3")

    if not home_team_id or not away_team_id:
        raise HTTPException(status_code=400, detail="home_team_id and away_team_id are required")

    home_team = get_team(home_team_id)
    away_team = get_team(away_team_id)
    if not home_team:
        raise HTTPException(status_code=404, detail=f"Home team (id={home_team_id}) not found")
    if not away_team:
        raise HTTPException(status_code=404, detail=f"Away team (id={away_team_id}) not found")

    # Build Player objects
    home_players_raw = get_team_players(home_team_id)
    away_players_raw = get_team_players(away_team_id)

    def _to_player(p: dict) -> Player:
        return Player(
            id=p["id"],
            team_id=p["team_id"],
            name=p["name"],
            position=p["position"],
            shirt_number=p.get("shirt_number", 0),
            age=p.get("age", 25),
            nationality=p.get("nationality", ""),
            rating=p.get("rating", 75),
            stats_json={},
            is_starter=bool(p.get("is_starter", 1)),
        )

    home_players = [_to_player(p) for p in home_players_raw]
    away_players = [_to_player(p) for p in away_players_raw]

    # Create engine
    session_id = uuid.uuid4().hex[:12]
    engine = MatchEngine(
        home_team_name=home_team["name"],
        away_team_name=away_team["name"],
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_players=home_players,
        away_players=away_players,
        home_formation=home_formation,
        away_formation=away_formation,
        session_id=session_id,
    )

    await engine.init()
    active_matches[session_id] = engine
    sse_clients[session_id] = []

    # Start match in background
    asyncio.create_task(engine.run(lambda e_type, data: _broadcast(session_id, e_type, data)))

    return {
        "session_id": session_id,
        "match_id": engine.state.match_id,
        "home_team": home_team["name"],
        "away_team": away_team["name"],
        "message": "比赛已创建并开始",
    }


# ── SSE event stream ────────────────────────────────────────────────────

@app.get("/match-sim/match/{session_id}/events")
async def match_events(session_id: str):
    """SSE stream of match events."""
    if session_id not in active_matches:
        raise HTTPException(status_code=404, detail="Match not found")

    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    sse_clients.setdefault(session_id, []).append(queue)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Send initial state
            engine = active_matches.get(session_id)
            if engine:
                initial = _sse_payload("match_state", {
                    "type": "match_state",
                    "session_id": session_id,
                    "data": engine._get_state_snapshot(),
                })
                yield initial

            # Stream events
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield payload
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            # Cleanup
            clients = sse_clients.get(session_id, [])
            if queue in clients:
                clients.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Match state ─────────────────────────────────────────────────────────

@app.get("/match-sim/match/{session_id}/state")
async def match_state(session_id: str):
    """Get current match state via REST."""
    if session_id not in active_matches:
        # Try database
        record = get_match_by_session(session_id)
        if record:
            return {"match": dict(record)}
        raise HTTPException(status_code=404, detail="Match not found")

    engine = active_matches[session_id]
    return {"match": engine._get_state_snapshot()}


# ── Tactical adjustment ─────────────────────────────────────────────────

@app.post("/match-sim/match/{session_id}/adjust")
async def tactical_adjustment(session_id: str, request: Request):
    """Make a tactical adjustment (home team)."""
    if session_id not in active_matches:
        raise HTTPException(status_code=404, detail="Match not found or already finished")

    engine = active_matches[session_id]
    body = await request.json()

    adj_type = body.get("type", "")
    from_value = body.get("from_value")
    to_value = body.get("to_value")
    reason = body.get("reason")

    if not adj_type:
        raise HTTPException(status_code=400, detail="type is required")

    success, message = await engine.apply_user_adjustment(adj_type, from_value, to_value, reason)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Broadcast the tactical adjustment event
    _broadcast(session_id, "tactical_adjustment", {
        "type": "tactical_adjustment",
        "session_id": session_id,
        "data": {
            "adjustment_type": adj_type,
            "from_value": from_value,
            "to_value": to_value,
            "reason": reason,
            "trigger_source": "user",
            "match_minute": engine.state.match_minute,
        },
    })

    return {"success": True, "message": message}


# ── Match control (pause / resume / stop) ──────────────────────────────

@app.post("/match-sim/match/{session_id}/pause")
async def pause_match(session_id: str):
    """Pause the match simulation."""
    if session_id not in active_matches:
        raise HTTPException(status_code=404, detail="Match not found")
    engine = active_matches[session_id]
    engine.pause()
    _broadcast(session_id, "match_paused", {"type": "match_paused", "session_id": session_id})
    return {"message": "比赛已暂停"}


@app.post("/match-sim/match/{session_id}/resume")
async def resume_match(session_id: str):
    """Resume the match simulation."""
    if session_id not in active_matches:
        raise HTTPException(status_code=404, detail="Match not found")
    engine = active_matches[session_id]
    engine.resume()
    _broadcast(session_id, "match_resumed", {"type": "match_resumed", "session_id": session_id})
    return {"message": "比赛已继续"}


@app.post("/match-sim/match/{session_id}/stop")
async def stop_match(session_id: str):
    """Stop the match simulation."""
    if session_id not in active_matches:
        raise HTTPException(status_code=404, detail="Match not found")
    engine = active_matches[session_id]
    engine.stop()
    if session_id in active_matches:
        del active_matches[session_id]
    if session_id in sse_clients:
        del sse_clients[session_id]
    return {"message": "比赛已停止"}


# ── Main ────────────────────────────────────────────────────────────────

def start():
    """Entry point for launching the server."""
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    start()
