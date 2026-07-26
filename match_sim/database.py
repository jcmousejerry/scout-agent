"""HTTP-client data access for match simulation.

持久化由 Go 后端统一管理（写入本地 MySQL 的 match_sim_* 表）。
本模块保留原有函数签名，实现改为通过 requests 调用 Go 的内部端点
http://localhost:8080/api/match-data/*。match_engine.py / api_server.py
的调用代码无需改动。

历史：原实现直接写入本地 SQLite（match_sim/data/match_data.db），
现已迁移至 Go 管理的 MySQL。
"""
import json
import logging
import os
from typing import List, Optional, Dict, Any

import requests

from models import MatchState

logger = logging.getLogger("match_sim.database")

# Go 后端数据访问基址
GO_DATA_BASE = os.environ.get("MATCH_DATA_BASE", "http://localhost:8080/api/match-data")
_HTTP_TIMEOUT = 10.0  # 单次请求超时（秒）；热路径每 tick 一次，localhost 通常 <20ms

# ─── Seed 数据缓冲 ──────────────────────────────────────────────────────
# insert_team / insert_player 不再即时落库，而是累积到此结构，
# 由 seed_all() 统一批量 POST 给 Go，减少启动时的 HTTP 往返次数。
_seed_buffer: List[Dict[str, Any]] = []
_seed_current_team: Optional[Dict[str, Any]] = None


def _post(path: str, json_body: Any) -> Dict[str, Any]:
    """POST JSON 到 Go 数据端点，返回解析后的 JSON 字典。"""
    resp = requests.post(GO_DATA_BASE + path, json=json_body, timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _put(path: str, json_body: Any) -> Dict[str, Any]:
    """PUT JSON 到 Go 数据端点，返回解析后的 JSON 字典。"""
    resp = requests.put(GO_DATA_BASE + path, json=json_body, timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _get(path: str) -> Any:
    """GET Go 数据端点，返回解析后的 JSON。"""
    resp = requests.get(GO_DATA_BASE + path, timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ─── Schema 初始化 ──────────────────────────────────────────────────────

def init_db():
    """No-op：表结构由 Go 后端启动时在 MySQL 中创建。

    保留此函数以兼容 match_engine.py / seed_data.py 的调用。
    """
    # 可选：ping Go 确认数据服务可达
    try:
        requests.get(GO_DATA_BASE + "/teams", timeout=2.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("init_db: Go data endpoint not reachable yet: %s", exc)


# ─── Team / Player 读取 ─────────────────────────────────────────────────

def get_all_teams() -> List[dict]:
    """列出全部球队（按实力评分降序）。"""
    data = _get("/teams")
    return data.get("teams", [])


def get_team(team_id: int) -> Optional[dict]:
    """获取单个球队详情（含 starters / substitutes）。

    Go 的 /teams/:id 返回 {team, starters, substitutes}；这里取 team 字段。
    """
    try:
        data = _get(f"/teams/{team_id}")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        raise
    return data.get("team")


def get_team_players(team_id: int) -> List[dict]:
    """获取球队全部球员（首发在前，评分降序）。

    Go 的 /teams/:id 已按 starters+substitutes 拆分，这里合并成单一列表，
    并补齐 is_starter 字段，保持与原 SQLite 返回结构一致。
    """
    try:
        data = _get(f"/teams/{team_id}")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return []
        raise
    starters = data.get("starters", [])
    subs = data.get("substitutes", [])
    return starters + subs


def get_team_starters(team_id: int) -> List[dict]:
    data = _get(f"/teams/{team_id}")
    return data.get("starters", [])


def get_team_subs(team_id: int) -> List[dict]:
    data = _get(f"/teams/{team_id}")
    return data.get("substitutes", [])


# ─── Match 写入 / 读取 ──────────────────────────────────────────────────

def create_match_record(session_id: str, home_id: int, away_id: int,
                        home_name: str, away_name: str,
                        home_formation: str, away_formation: str) -> int:
    """创建比赛记录，返回 match_id。"""
    body = {
        "session_id": session_id,
        "home_team_id": home_id,
        "away_team_id": away_id,
        "home_team_name": home_name,
        "away_team_name": away_name,
        "home_formation": home_formation,
        "away_formation": away_formation,
    }
    data = _post("/match", body)
    return int(data.get("match_id", 0))


def update_match_state(state: MatchState):
    """更新比赛状态（热路径：每个 tick 调用一次）。

    在 Python 侧组装 stats_json / events_json / tactics_json / lineup_json 字符串，
    PUT 给 Go，由 Go 写入 MySQL。
    """
    stats_json = json.dumps({
        "shots": {"home": state.stats.home_shots, "away": state.stats.away_shots},
        "shots_on_target": {"home": state.stats.home_shots_on_target, "away": state.stats.away_shots_on_target},
        "fouls": {"home": state.stats.home_fouls, "away": state.stats.away_fouls},
        "corners": {"home": state.stats.home_corners, "away": state.stats.away_corners},
        "offsides": {"home": state.stats.home_offsides, "away": state.stats.away_offsides},
        "yellows": {"home": state.stats.home_yellows, "away": state.stats.away_yellows},
        "reds": {"home": state.stats.home_reds, "away": state.stats.away_reds},
        "possession": {"home": state.stats.home_possession, "away": state.stats.away_possession},
    }, ensure_ascii=False)
    events_json = json.dumps([{
        "event_id": e.event_id, "event_type": e.event_type, "event_subtype": e.event_subtype,
        "team": e.team, "actor_name": e.actor_name, "target_name": e.target_name,
        "description": e.description, "match_minute": e.match_minute, "half": e.half,
        "importance": e.importance, "position": e.position,
        "score": e.extra.get("score"),
    } for e in state.events], ensure_ascii=False)
    tactics_json = json.dumps([{
        "adjustment_id": a.adjustment_id, "adjustment_type": a.adjustment_type,
        "team": a.team, "from_value": a.from_value, "to_value": a.to_value,
        "reason": a.reason, "trigger_source": a.trigger_source, "match_minute": a.match_minute,
    } for a in state.tactical_adjustments], ensure_ascii=False)
    lineup_json = json.dumps({
        "active_players_home": [
            {"name": p.name, "position": p.position, "shirt_number": p.shirt_number, "rating": p.rating}
            for p in state.active_players_home
        ],
        "active_players_away": [
            {"name": p.name, "position": p.position, "shirt_number": p.shirt_number, "rating": p.rating}
            for p in state.active_players_away
        ],
        "bench_players_home": [
            {"name": p.name, "position": p.position, "shirt_number": p.shirt_number, "rating": p.rating}
            for p in state.bench_players_home
        ],
        "bench_players_away": [
            {"name": p.name, "position": p.position, "shirt_number": p.shirt_number, "rating": p.rating}
            for p in state.bench_players_away
        ],
        "home_substitutions_used": state.home_substitutions_used,
        "away_substitutions_used": state.away_substitutions_used,
        "home_tactical_cooldown": max(0, state.home_tactical_cooldown),
        "away_tactical_cooldown": max(0, state.away_tactical_cooldown),
        "home_attack_modifier": round(state.home_attack_modifier, 2),
        "home_defense_modifier": round(state.home_defense_modifier, 2),
        "away_attack_modifier": round(state.away_attack_modifier, 2),
        "away_defense_modifier": round(state.away_defense_modifier, 2),
        "home_morale": round(state.home_morale, 2),
        "away_morale": round(state.away_morale, 2),
        "match_tempo": state.match_tempo,
    }, ensure_ascii=False)

    body = {
        "home_score": state.home_score,
        "away_score": state.away_score,
        "match_status": state.match_status.value,
        "match_minute": state.match_minute,
        "stats_json": stats_json,
        "events_json": events_json,
        "tactics_json": tactics_json,
        "lineup_json": lineup_json,
        "winner": "",
    }
    _put(f"/match/{state.session_id}", body)


def get_match_by_session(session_id: str) -> Optional[dict]:
    """按 session_id 取比赛记录。"""
    try:
        data = _get(f"/match/{session_id}")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        raise
    return data.get("match")


# ─── Seed 数据收集（批量提交）──────────────────────────────────────────

def insert_team(name: str, short_name: str, league: str, country: str,
                rating: int, formation: str) -> int:
    """将球队加入种子缓冲区，返回临时 team_id（占位，落库后由 Go 生成真实 id）。

    注意：此处返回的 id 仅用于 seed_data.py 中关联球员调用 insert_player；
    真正的 team_id 在 Go 写入 MySQL 后生成。批量提交时 Go 按 name 解析真实 id。
    因此本返回值不可用于后续的真实外键引用——seed 流程之外不应调用本函数。
    """
    global _seed_current_team
    team = {
        "name": name,
        "short_name": short_name,
        "league": league,
        "country": country,
        "strength_rating": rating,
        "default_formation": formation,
        "players": [],
    }
    _seed_buffer.append(team)
    _seed_current_team = team
    # 返回缓冲区中的序号（1-based）作为占位 id
    return len(_seed_buffer)


def insert_player(team_id: int, name: str, position: str, number: int,
                  age: int, nationality: str, rating: int, stats: dict,
                  is_starter: int = 1):
    """将球员追加到当前球队的 players 列表（team_id 为 insert_team 返回的占位序号）。"""
    # 定位目标球队：insert_team 返回的是 1-based 序号
    idx = team_id - 1
    if idx < 0 or idx >= len(_seed_buffer):
        # 兜底：追加到最近一个球队
        if not _seed_buffer:
            return
        idx = len(_seed_buffer) - 1
    _seed_buffer[idx]["players"].append({
        "name": name,
        "position": position,
        "shirt_number": number,
        "age": age,
        "nationality": nationality,
        "rating": rating,
        "stats_json": json.dumps(stats, ensure_ascii=False),
        "is_starter": bool(is_starter),
    })


def flush_seed() -> dict:
    """将累积的种子数据批量 POST 给 Go，返回 Go 的响应。"""
    global _seed_buffer, _seed_current_team
    if not _seed_buffer:
        return {"ok": True, "teams": 0, "players": 0}
    body = {"teams": _seed_buffer}
    result = _post("/seed", body)
    _seed_buffer = []
    _seed_current_team = None
    return result
