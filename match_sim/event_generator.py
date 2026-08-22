"""Event generator — calls LLM to produce match events.

The EventGenerator is the creative engine of the simulation. It takes the
current MatchState, builds a prompt, calls the LLM, parses the JSON response,
and updates both the event log and the aggregate stats. On timeout or parse
failure it falls back to a sensible filler event so the match never stalls.
"""

import asyncio
import json
import re
import logging
import random
from typing import Optional, Tuple

from config import LLM_TIMEOUT, EVENT_TEMPERATURE
from ai_agent.llm_client import chat as llm_chat
from match_dynamics import MatchDynamics
from models import MatchState, MatchEvent, MatchStats
from prompts.event_prompts import build_event_prompt, build_narrative_prompt

logger = logging.getLogger("match_sim.event_generator")


# ─── Filler events (used when the LLM call fails) ────────────────────────

def _build_filler_event(state: MatchState) -> MatchEvent:
    """Build a safe fallback event when the LLM is unreachable or returns garbage."""
    team = "home" if state.stats.home_possession >= 50 else "away"
    player_pool = (
        state.active_players_home if team == "home" else state.active_players_away
    )
    actor = player_pool[len(state.events) % len(player_pool)] if player_pool else None
    return MatchEvent(
        event_type="passage_of_play",
        event_subtype=None,
        team=team,
        actor_name=actor.name if actor else None,
        target_name=None,
        description=(
            f"{actor.name if actor else '双方球员'}在中场展开拼抢，"
            f"{state.home_team_name}试图组织进攻"
            if team == "home"
            else f"{actor.name if actor else '双方球员'}在中场展开拼抢，"
                 f"{state.away_team_name}试图组织进攻"
        ),
        match_minute=state.match_minute,
        half=state.match_half,
        importance=1,
        position="中场",
    )


# ─── Stats helpers ───────────────────────────────────────────────────────

def _apply_event_stats(event: MatchEvent, stats: MatchStats):
    """Update match stats based on the generated event type."""
    et = event.event_type
    est = event.event_subtype
    team = event.team

    if et == "goal":
        if team == "home":
            stats.home_shots += 1
            stats.home_shots_on_target += 1
        else:
            stats.away_shots += 1
            stats.away_shots_on_target += 1
    elif et == "shot":
        if team == "home":
            stats.home_shots += 1
            if est == "shot_on_target":
                stats.home_shots_on_target += 1
        else:
            stats.away_shots += 1
            if est == "shot_on_target":
                stats.away_shots_on_target += 1
    elif et == "foul":
        if team == "home":
            stats.home_fouls += 1
        else:
            stats.away_fouls += 1
    elif et == "corner":
        if team == "home":
            stats.home_corners += 1
        else:
            stats.away_corners += 1
    elif et == "offside":
        if team == "home":
            stats.home_offsides += 1
        else:
            stats.away_offsides += 1
    elif et == "card":
        if est == "red_card" or est == "second_yellow":
            if team == "home":
                stats.home_reds += 1
            else:
                stats.away_reds += 1
        else:
            if team == "home":
                stats.home_yellows += 1
            else:
                stats.away_yellows += 1
    elif et == "save":
        # A save implies a shot was on target
        if team == "home":
            stats.away_shots += 1
            stats.away_shots_on_target += 1
        else:
            stats.home_shots += 1
            stats.home_shots_on_target += 1
    elif et == "penalty":
        # Penalty implies a foul in box, tracked as foul
        if team == "home":
            stats.away_fouls += 1
        else:
            stats.home_fouls += 1


def _recalculate_possession(state: MatchState):
    """Recalculate possession based on modifiers and recent events.

    Simple heuristic: the more attack-minded side gets more possession
    unless the other side is playing possession_focus.
    """
    home_attack = state.home_attack_modifier or 1.0
    away_attack = state.away_attack_modifier or 1.0
    total = home_attack + away_attack
    state.stats.home_possession = (home_attack / total) * 100
    state.stats.away_possession = (away_attack / total) * 100


# ─── JSON parsing helpers ────────────────────────────────────────────────

def _extract_json(text: str) -> Optional[dict]:
    """Try to extract a JSON object from LLM output."""
    # Attempt 1: try parsing the whole thing
    text = text.strip()
    # Remove markdown code fences if present
    text = re.sub(r"^```(?:json)?", "", text, flags=re.MULTILINE).strip()
    text = re.sub(r"```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: find first { … } block
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        candidate = brace_match.group()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Attempt 3: try to fix common issues — trailing commas, single quotes
    fixed = re.sub(r",\s*}", "}", text)
    fixed = re.sub(r",\s*\]", "]", fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    return None


def _validate_event(raw: dict, state: MatchState) -> Tuple[bool, str]:
    """Validate a parsed event dict against basic business rules.

    Returns (valid, error_reason).
    """
    if not isinstance(raw, dict):
        return False, "Response is not a dict"
    if "event_type" not in raw:
        return False, "Missing event_type"

    et = raw["event_type"]

    # Actor must be a real player on the field
    actor = raw.get("actor_name")
    if actor:
        all_players = state.active_players_home + state.active_players_away
        if not any(p.name == actor for p in all_players):
            return False, f"Actor '{actor}' is not on the field"

    # Goal requires an actor
    if et == "goal" and not actor:
        return False, "Goal event missing actor_name"

    return True, ""


# ─── Main generator class ────────────────────────────────────────────────

class EventGenerator:
    """Generates match events via LLM calls.

    Usage:
        generator = EventGenerator()
        event, updated_stats = await generator.generate(state)
    """

    def __init__(self, rng: Optional[random.Random] = None):
        self._consecutive_failures = 0
        self.dynamics = MatchDynamics(rng)

    async def generate(self, state: MatchState) -> Tuple[MatchEvent, MatchStats]:
        """Generate the next match event.

        Calls the LLM, parses the response, updates stats, and returns both
        the event and the updated stats object.

        On failure the counter increments; after 3 consecutive failures we
        emit an important event (goal chance) to re-engage the story.
        """
        prompt = build_event_prompt(state)
        system_msg = {
            "role": "system",
            "content": "你是一名专业的足球比赛AI解说员。请严格按照要求的JSON格式返回比赛事件数据。只返回JSON，不要包含任何其他文字。",
        }
        user_msg = {"role": "user", "content": prompt}
        messages = [system_msg, user_msg]

        logger.debug("Sending event generation prompt to LLM")

        try:
            response = await asyncio.to_thread(
                llm_chat,
                messages=messages,
                temperature=EVENT_TEMPERATURE,
                extra_body={"enable_thinking": True, "thinking_budget": 256},
                timeout=LLM_TIMEOUT,
                max_tokens=350,
                max_retries=0,
            )
            raw_text = response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("LLM event call failed: %s", exc)
            return self._fallback(state, is_error=True)

        parsed = _extract_json(raw_text)
        if not parsed:
            logger.warning("Failed to parse LLM output as JSON: %.200s", raw_text)
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                logger.info("3+ consecutive failures — injecting important event")
                self._consecutive_failures = 0
                return self._build_goal_chance(state)
            return self._fallback(state)

        valid, reason = _validate_event(parsed, state)
        if not valid:
            logger.warning("Event validation failed: %s — raw: %.200s", reason, raw_text)
            self._consecutive_failures += 1
            return self._fallback(state)

        self._consecutive_failures = 0
        resolved_goal = self.dynamics.maybe_build_goal(state)
        if resolved_goal:
            stats = state.stats
            _apply_event_stats(resolved_goal, stats)
            return resolved_goal, stats

        # The LLM may propose a goal for narrative variety, but the mechanics
        # layer owns the result. A failed goal roll becomes a saved shot.
        if parsed.get("event_type") == "goal":
            parsed = dict(parsed)
            parsed["event_type"] = "shot"
            parsed["event_subtype"] = "shot_on_target"
            actor = parsed.get("actor_name") or "进攻球员"
            parsed["description"] = f"{actor}完成了一次极具威胁的射门，但被门将奋力扑出。"
            parsed["importance"] = 4
        return self._build_event_from_parsed(parsed, state)

    async def generate_narrative(self, state: MatchState, period: str = "上半场") -> str:
        """Generate a half-time or full-time narrative summary."""
        fallback = f"{period}比赛结束，当前比分 {state.home_score} - {state.away_score}。"
        try:
            prompt = build_narrative_prompt(state, period)
        except Exception as exc:
            logger.warning("Narrative prompt build failed: %s", exc)
            return fallback
        system_msg = {
            "role": "system",
            "content": "你是一名专业的足球比赛评论员。请生成一段流畅的中文比赛总结。",
        }
        user_msg = {"role": "user", "content": prompt}

        try:
            response = await asyncio.to_thread(
                llm_chat,
                messages=[system_msg, user_msg],
                temperature=0.7,
                extra_body={"enable_thinking": True, "thinking_budget": 256},
                timeout=LLM_TIMEOUT,
                max_tokens=600,
                max_retries=0,
            )
            return response.choices[0].message.content or fallback
        except Exception as exc:
            logger.warning("LLM narrative call failed: %s", exc)
            return fallback

    # ── Internal helpers ────────────────────────────────────────────────

    def _fallback(self, state: MatchState, is_error: bool = False) -> Tuple[MatchEvent, MatchStats]:
        """Return a filler event when the LLM call fails."""
        event = self.dynamics.maybe_build_goal(state) or _build_filler_event(state)
        event.match_minute = state.match_minute
        event.half = state.match_half
        stats = state.stats
        _apply_event_stats(event, stats)
        return event, stats

    def _build_goal_chance(self, state: MatchState) -> Tuple[MatchEvent, MatchStats]:
        """Build a high-importance fallback event (goal chance)."""
        # Pick the team that's behind, or random if tied
        if state.home_score < state.away_score:
            team = "home"
        elif state.away_score < state.home_score:
            team = "away"
        else:
            team = "home" if state.stats.home_possession >= 50 else "away"

        player_pool = (
            state.active_players_home if team == "home" else state.active_players_away
        )
        actors = [p for p in player_pool if p.position in ("ST", "LW", "RW", "CAM")]
        actor = actors[state.match_minute % len(actors)] if actors else player_pool[0]
        team_name = state.home_team_name if team == "home" else state.away_team_name

        event = MatchEvent(
            event_type="shot",
            event_subtype="shot_on_target",
            team=team,
            actor_name=actor.name,
            target_name=None,
            description=(
                f"{actor.name}在禁区前沿接到传球后一脚劲射，"
                f"皮球直奔球门死角！{team_name}获得了一次绝佳机会！"
            ),
            match_minute=state.match_minute,
            half=state.match_half,
            importance=4,
            position="禁区前沿",
        )
        stats = state.stats
        _apply_event_stats(event, stats)
        return event, stats

    def _build_event_from_parsed(
        self, parsed: dict, state: MatchState
    ) -> Tuple[MatchEvent, MatchStats]:
        """Convert a validated parsed dict into a MatchEvent + updated stats."""
        # Determine actor's team
        actor_name = parsed.get("actor_name")
        team = parsed.get("actor_team", "")
        if not team and actor_name:
            if any(p.name == actor_name for p in state.active_players_home):
                team = "home"
            elif any(p.name == actor_name for p in state.active_players_away):
                team = "away"

        # Advance minute
        advance = max(3, min(int(parsed.get("match_minute_advance", 5)), 5))

        event = MatchEvent(
            event_type=parsed["event_type"],
            event_subtype=parsed.get("event_subtype"),
            team=team,
            actor_name=actor_name,
            target_name=parsed.get("target_name"),
            description=parsed.get("description", ""),
            match_minute=state.match_minute + advance - 1,  # event happens at this minute
            half=state.match_half,
            importance=int(parsed.get("importance", 3)),
            position=parsed.get("position"),
            extra={
                "match_minute_advance": advance,
                "score": (
                    f"{state.home_score + (1 if parsed['event_type'] == 'goal' and team == 'home' else 0)}"
                    f"-"
                    f"{state.away_score + (1 if parsed['event_type'] == 'goal' and team == 'away' else 0)}"
                ),
            },
        )

        stats = state.stats
        _apply_event_stats(event, stats)
        return event, stats
