"""Opponent AI agent — makes tactical decisions during the match.

The OpponentAgent monitors the match and decides, at configurable intervals,
whether the AI-controlled team should make a tactical adjustment
(substitution, formation change, attack/defense shift, etc.).

It also reacts to the user's tactical adjustments with a short delay,
simulating a real managerial chess match.
"""

import asyncio
import json
import logging
from typing import List, Optional, Tuple

from config import LLM_TIMEOUT, TACTICS_TEMPERATURE, OPPONENT_COUNTER_DELAY, SUBSTITUTION_LIMIT
from ai_agent.llm_client import chat as llm_chat
from models import (
    MatchState,
    MatchEvent,
    TacticalAdjustment,
    TacticalAdjustmentType,
)
from prompts.event_prompts import build_opponent_prompt

logger = logging.getLogger("match_sim.opponent_agent")

# Minimum match minutes between opponent tactical evaluations
TACTICAL_EVAL_INTERVAL = 15
# Minimum match minute to make first substitution
FIRST_SUB_MINUTE = 40


class OpponentAgent:
    """AI opponent that makes tactical decisions.

    Usage:
        opponent = OpponentAgent(is_away=True)
        adjustments = await opponent.evaluate(state)
        # or, for a counter-reaction after the user adjusts:
        adjustments = await opponent.counter_adjust(state)

    Both return a list of TacticalAdjustment (possibly empty).
    """

    def __init__(self, is_away: bool = True):
        self.is_away = is_away
        self._last_eval_minute = -TACTICAL_EVAL_INTERVAL  # allow immediate eval at start
        self._pending_adjustments: List[TacticalAdjustment] = []
        self._consecutive_failures = 0

    @property
    def team_prefix(self) -> str:
        return "away" if self.is_away else "home"

    # ── Public API ───────────────────────────────────────────────────────

    async def evaluate(self, state: MatchState) -> List[TacticalAdjustment]:
        """Evaluate the match and decide if the opponent should adjust.

        Returns a (possibly empty) list of TacticalAdjustment.
        """
        # Rate-limit evaluations
        if state.match_minute - self._last_eval_minute < TACTICAL_EVAL_INTERVAL:
            return []

        self._last_eval_minute = state.match_minute

        # Skip if too early for most adjustments (except urgent)
        if state.match_minute < 10:
            return []

        # Call LLM
        prompt = build_opponent_prompt(state, is_away=self.is_away)
        system_msg = {
            "role": "system",
            "content": (
                "你是一名职业足球教练。请根据当前比赛局势做出合理的战术决策。"
                "只返回JSON，不要包含任何其他文字。"
            ),
        }
        user_msg = {"role": "user", "content": prompt}

        logger.debug("Sending opponent tactical prompt to LLM")

        try:
            response = await asyncio.to_thread(
                llm_chat,
                messages=[system_msg, user_msg],
                temperature=TACTICS_TEMPERATURE,
                extra_body={"enable_thinking": True, "thinking_budget": 256},
                timeout=LLM_TIMEOUT,
                max_tokens=500,
                max_retries=0,
            )
            raw_text = response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("Opponent LLM call failed: %s", exc)
            return []

        adjustments = self._parse_adjustments(raw_text, state)
        if not adjustments:
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 0

        return adjustments

    async def counter_adjust(self, user_adjustment: TacticalAdjustment, state: MatchState) -> List[TacticalAdjustment]:
        """React to a user's tactical adjustment.

        The opponent doesn't react immediately — it simulates a 3-tick
        (~15s real-time) observation delay. When the delay expires, it
        evaluates and typically counters with an opposing adjustment.

        Returns a (possibly empty) list of TacticalAdjustment.
        """
        # Schedule a pending counter-reaction
        logger.info(
            "Opponent counter-adjustment scheduled in %d ticks for user adjustment: %s",
            OPPONENT_COUNTER_DELAY,
            user_adjustment.adjustment_type,
        )
        self._pending_adjustments.append(user_adjustment)
        return []

    async def tick_pending(self, state: MatchState) -> List[TacticalAdjustment]:
        """Process pending counter-adjustments — call once per tick.

        Decrements the delay counter; when it reaches zero, fires the
        counter-evaluation.
        """
        if not self._pending_adjustments:
            return []

        # Decrement all pending counters
        # (stored by appending to the list — we re-evaluate when any fires)
        result: List[TacticalAdjustment] = []

        # Process pending: for this simple implementation, just re-evaluate
        # when there are pending adjustments after the delay
        state.opponent_counter_tick += 1
        if state.opponent_counter_tick >= OPPONENT_COUNTER_DELAY:
            state.opponent_counter_tick = 0
            self._pending_adjustments = []
            result = await self._forced_counter_eval(state)

        return result

    # ── Internal logic ───────────────────────────────────────────────────

    async def _forced_counter_eval(self, state: MatchState) -> List[TacticalAdjustment]:
        """A tactical evaluation triggered specifically by a user adjustment.

        This uses a slightly more aggressive prompt to ensure the opponent
        responds rather than staying passive.
        """
        prompt = build_opponent_prompt(state, is_away=self.is_away)
        prompt += (
            "\n\n## 紧急情况\n"
            "对手刚刚进行了战术调整！作为教练你需要立即做出应对。"
            "建议至少选择一个调整来反制对手的战术变化。"
            "如果对手加强了进攻，你可以考虑加强防守或改为防守反击。"
            "如果对手换人，考虑调整阵型或对位调整。"
        )

        system_msg = {
            "role": "system",
            "content": (
                "你是一名职业足球教练。对手刚刚做出了战术调整，你需要快速反制。"
                "只返回JSON，不要包含任何其他文字。"
            ),
        }

        try:
            response = await asyncio.to_thread(
                llm_chat,
                messages=[system_msg, {"role": "user", "content": prompt}],
                temperature=TACTICS_TEMPERATURE,
                extra_body={"enable_thinking": True, "thinking_budget": 256},
                timeout=LLM_TIMEOUT,
                max_tokens=500,
                max_retries=0,
            )
            raw_text = response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("Opponent counter LLM call failed: %s", exc)
            return []

        return self._parse_adjustments(raw_text, state)

    def _parse_adjustments(self, raw_text: str, state: MatchState) -> List[TacticalAdjustment]:
        """Parse the LLM JSON response into TacticalAdjustment list."""
        # Try to extract JSON
        import re

        text = raw_text.strip()
        text = re.sub(r"^```(?:json)?", "", text, flags=re.MULTILINE).strip()
        text = re.sub(r"```$", "", text, flags=re.MULTILINE).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Try to find a JSON object
            brace_match = re.search(r"\{[\s\S]*\}", text)
            if brace_match:
                try:
                    parsed = json.loads(brace_match.group())
                except json.JSONDecodeError:
                    logger.warning("Failed to parse opponent response as JSON: %.200s", raw_text)
                    return []
            else:
                logger.warning("No JSON found in opponent response: %.200s", raw_text)
                return []

        if not parsed.get("need_adjustment"):
            return []

        raw_adjustments = parsed.get("adjustments", [])
        if not raw_adjustments:
            return []

        # Limit to max 2 adjustments
        raw_adjustments = raw_adjustments[:2]

        result = []
        for raw in raw_adjustments:
            adj_type = raw.get("type", "")

            # Validate and possibly adjust player names for substitutions
            if adj_type == TacticalAdjustmentType.SUBSTITUTION:
                adj = self._validate_substitution(raw, state)
                if adj:
                    result.append(adj)
            elif adj_type == TacticalAdjustmentType.FORMATION_CHANGE:
                adj = self._validate_formation_change(raw, state)
                if adj:
                    result.append(adj)
            elif adj_type in (
                TacticalAdjustmentType.ATTACK_BOOST,
                TacticalAdjustmentType.DEFENSE_BOOST,
                TacticalAdjustmentType.POSSESSION_FOCUS,
                TacticalAdjustmentType.COUNTER_ATTACK,
                TacticalAdjustmentType.HIGH_PRESS,
                TacticalAdjustmentType.LOW_BLOCK,
                TacticalAdjustmentType.ALL_OUT_ATTACK,
            ):
                # Simple tactical shift — apply directly
                result.append(self._build_adjustment(adj_type, "", "", raw.get("reason", ""), state))

        return result

    def _validate_substitution(self, raw: dict, state: MatchState) -> Optional[TacticalAdjustment]:
        """Validate a substitution adjustment — ensure player names are real."""
        off_name = raw.get("from_value", "")
        on_name = raw.get("to_value", "")

        # Determine which players are on the opponent's bench
        bench = state.bench_players_away if self.is_away else state.bench_players_home
        active = state.active_players_away if self.is_away else state.active_players_home
        subs_used = state.away_substitutions_used if self.is_away else state.home_substitutions_used

        # Check limits
        if subs_used >= SUBSTITUTION_LIMIT:
            logger.info("Opponent has used all substitutions, skipping sub request")
            return None

        # Find the player to take off — must be active
        player_off = next((p for p in active if p.name == off_name), None)
        if not player_off:
            logger.warning("Opponent sub: player '%s' not on field, selecting alternate", off_name)
            return None

        # Find the player to bring on — must be on bench
        player_on = next((p for p in bench if p.name == on_name), None)
        if not player_on:
            logger.warning("Opponent sub: player '%s' not on bench, selecting alternate", on_name)
            # Auto-select highest-rated bench player
            if bench:
                player_on = max(bench, key=lambda p: p.rating)
                on_name = player_on.name
            else:
                return None

        return self._build_adjustment(
            TacticalAdjustmentType.SUBSTITUTION,
            off_name,
            on_name,
            raw.get("reason", "战术换人"),
            state,
        )

    def _validate_formation_change(self, raw: dict, state: MatchState) -> Optional[TacticalAdjustment]:
        """Validate a formation change — must be a real formation."""
        new_formation = raw.get("to_value", "")

        from event_types import AVAILABLE_FORMATIONS

        if new_formation not in AVAILABLE_FORMATIONS:
            logger.warning("Invalid formation '%s', skipping formation change", new_formation)
            return None

        current_formation = state.away_formation if self.is_away else state.home_formation
        if new_formation == current_formation:
            return None

        return self._build_adjustment(
            TacticalAdjustmentType.FORMATION_CHANGE,
            current_formation,
            new_formation,
            raw.get("reason", "变阵调整"),
            state,
        )

    def _build_adjustment(
        self,
        adj_type: str,
        from_value: str,
        to_value: str,
        reason: str,
        state: MatchState,
    ) -> TacticalAdjustment:
        """Build a TacticalAdjustment record."""
        return TacticalAdjustment(
            adjustment_type=adj_type,
            team=self.team_prefix,
            from_value=from_value or None,
            to_value=to_value or None,
            reason=reason,
            trigger_source="opponent_agent",
            match_minute=state.match_minute,
        )
