"""Core match engine — state machine and event loop for match simulation.

The MatchEngine is the central orchestrator:
  - Manages match lifecycle (CREATED → FIRST_HALF → ... → FINISHED)
  - Runs the tick loop (~5s per minute of match time)
  - Delegates event generation to EventGenerator
  - Delegates opponent tactical decisions to OpponentAgent
  - Applies tactical adjustments to the match state
  - Emits events via an async callback so the API server can SSE-broadcast
"""

import asyncio
import copy
import json
import logging
import time
import uuid
from typing import AsyncIterator, Callable, List, Optional, Tuple

from config import (
    TICK_INTERVAL,
    MATCH_MINUTES,
    HALF_TIME_LENGTH,
    INJURY_TIME_PER_HALF,
    SUBSTITUTION_LIMIT,
    TACTICAL_ADJUSTMENT_COOLDOWN,
)
from database import create_match_record, update_match_state, init_db
from event_generator import EventGenerator
from event_types import (
    EventType,
    TacticalAdjustmentType,
    USER_TACTICAL_ADJUSTMENTS,
    AVAILABLE_FORMATIONS,
)
from models import (
    MatchState,
    MatchStats,
    MatchEvent,
    MatchStatus,
    TacticalAdjustment,
    Player,
    Team,
)
from opponent_agent import OpponentAgent

logger = logging.getLogger("match_sim.match_engine")


# ─── Event emitter type ──────────────────────────────────────────────────

# Callback signature: async (event_type: str, data: dict) -> None
EventEmitter = Callable[[str, dict], None]


# ─── Match Engine ────────────────────────────────────────────────────────

class MatchEngine:
    """Runs a full match simulation from kickoff to final whistle.

    Usage:
        engine = MatchEngine(home_team, away_team, home_id, away_id)
        await engine.init()
        asyncio.create_task(engine.run(emit_event))
    """

    def __init__(
        self,
        home_team_name: str,
        away_team_name: str,
        home_team_id: int,
        away_team_id: int,
        home_players: List[Player],
        away_players: List[Player],
        home_formation: str = "4-3-3",
        away_formation: str = "4-3-3",
        session_id: Optional[str] = None,
    ):
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.home_team_name = home_team_name
        self.away_team_name = away_team_name
        self.home_team_id = home_team_id
        self.away_team_id = away_team_id

        # State
        self.state = self._build_initial_state(
            home_players, away_players, home_formation, away_formation,
        )

        # Sub-modules
        self.event_generator = EventGenerator()
        self.opponent_agent = OpponentAgent(is_away=True)

        # Runtime
        self._running = False
        self._paused = False
        self._tick_task: Optional[asyncio.Task] = None
        self._db_initialized = False
        self._emit_callback: Optional[EventEmitter] = None

    def _build_initial_state(
        self,
        home_players: List[Player],
        away_players: List[Player],
        home_formation: str,
        away_formation: str,
    ) -> MatchState:
        """Build the initial MatchState from player lists."""
        # Separate starters from bench
        home_starters = [p for p in home_players if p.is_starter][:11]
        away_starters = [p for p in away_players if p.is_starter][:11]
        home_bench = [p for p in home_players if not p.is_starter]
        away_bench = [p for p in away_players if not p.is_starter]

        # Fill with remaining if starters < 11
        if len(home_starters) < 11:
            remaining = [p for p in home_players if p not in home_starters]
            home_starters.extend(remaining[: 11 - len(home_starters)])
        if len(away_starters) < 11:
            remaining = [p for p in away_players if p not in away_starters]
            away_starters.extend(remaining[: 11 - len(away_starters)])

        return MatchState(
            session_id=self.session_id,
            home_team_name=self.home_team_name,
            away_team_name=self.away_team_name,
            home_score=0,
            away_score=0,
            match_minute=0,
            match_half=1,
            match_status=MatchStatus.CREATED,
            home_formation=home_formation,
            away_formation=away_formation,
            home_players=home_starters + home_bench,
            away_players=away_starters + away_bench,
            active_players_home=home_starters[:],
            active_players_away=away_starters[:],
            bench_players_home=home_bench[:],
            bench_players_away=away_bench[:],
            events=[],
            tactical_adjustments=[],
            stats=MatchStats(),
            home_attack_modifier=1.0,
            home_defense_modifier=1.0,
            away_attack_modifier=1.0,
            away_defense_modifier=1.0,
            home_morale=0.5,
            away_morale=0.5,
            match_tempo="balanced",
        )

    # ── Match lifecycle ──────────────────────────────────────────────────

    async def init(self):
        """Prepare the engine and persist the initial match record."""
        if not self._db_initialized:
            init_db()
            self._db_initialized = True

        # Default formations
        home_f = self.state.home_formation or "4-3-3"
        away_f = self.state.away_formation or "4-3-3"

        match_id = create_match_record(
            session_id=self.session_id,
            home_id=self.home_team_id,
            away_id=self.away_team_id,
            home_name=self.home_team_name,
            away_name=self.away_team_name,
            home_formation=home_f,
            away_formation=away_f,
        )
        self.state.match_id = match_id
        logger.info("Match %s created (ID=%s)", self.session_id, match_id)

    async def run(self, emit: EventEmitter):
        """Run the full match simulation.

        Args:
            emit: Async callback to push events to connected clients.
                  Signature: async (event_type: str, data: dict) -> None
        """
        if self._running:
            logger.warning("Match %s is already running", self.session_id)
            return

        self._emit_callback = emit
        self._running = True
        logger.info("Match %s started: %s vs %s", self.session_id, self.home_team_name, self.away_team_name)

        try:
            # ── Kickoff ──
            self.state.match_status = MatchStatus.FIRST_HALF
            self.state.match_minute = 1
            await self._emit_state(emit)
            await self._save_state()

            # ── First half ──
            await self._run_half(emit, half=1)

            # 若已被 stop()，保存最终状态并干净退出
            if not self._running:
                self.state.match_status = MatchStatus.FINISHED
                await self._save_state()
                return

            # ── Half-time ──
            self.state.match_status = MatchStatus.HALF_TIME
            self.state.match_minute = HALF_TIME_LENGTH
            await self._emit_half_time(emit)
            await self._save_state()

            # 短暂中场休息
            await asyncio.sleep(1)

            if not self._running:
                self.state.match_status = MatchStatus.FINISHED
                await self._save_state()
                return

            # ── Second half ──
            self.state.match_status = MatchStatus.SECOND_HALF
            self.state.match_half = 2
            self.state.match_minute = HALF_TIME_LENGTH + 1
            # Swap sides — possession resets slightly
            self.state.stats.home_possession = 50.0
            self.state.stats.away_possession = 50.0
            await self._emit_state(emit)
            await self._save_state()

            await self._run_half(emit, half=2)

            if not self._running:
                self.state.match_status = MatchStatus.FINISHED
                await self._save_state()
                return

            # ── Full-time ──
            self.state.match_status = MatchStatus.FINISHED
            await self._emit_full_time(emit)
            await self._save_state()

        except asyncio.CancelledError:
            logger.info("Match %s cancelled", self.session_id)
            self.state.match_status = MatchStatus.FINISHED
            await self._save_state()
        except Exception as exc:
            logger.exception("Match %s error: %s", self.session_id, exc)
            self.state.match_status = MatchStatus.FINISHED
            await self._save_state()
        finally:
            self._running = False

    def stop(self):
        """Stop the match simulation."""
        self._running = False
        if self._tick_task and not self._tick_task.done():
            self._tick_task.cancel()
        logger.info("Match %s stopped", self.session_id)

    def pause(self):
        """Pause the match (user can still make adjustments)."""
        self._paused = True
        logger.info("Match %s paused", self.session_id)

    def resume(self):
        """Resume a paused match."""
        self._paused = False
        logger.info("Match %s resumed", self.session_id)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ── Half simulation ─────────────────────────────────────────────────

    async def _run_half(self, emit: EventEmitter, half: int):
        """Run one half of the match (first or second)."""
        half_end = HALF_TIME_LENGTH + (0 if half == 1 else HALF_TIME_LENGTH)
        injury_time = INJURY_TIME_PER_HALF
        goal_events_this_half = sum(1 for e in self.state.events if e.event_type == "goal")

        while self._running and self.state.match_minute < half_end + injury_time:
            if self._paused:
                await asyncio.sleep(1)
                continue

            tick_start = time.monotonic()

            # ── 1. Generate event ──
            event, stats = await self.event_generator.generate(self.state)
            event.half = half
            self.state.stats = stats

            # ── 2. Queue event (defer score/morale update until emission) ──
            self.state.events.append(event)
            advance = event.extra.get("match_minute_advance", 5) if isinstance(event.extra, dict) else 5
            advance = max(advance, 5)  # 至少推进 5 分钟，保证全场比赛 ≈ 45 秒
            self.state.match_minute += advance

            # Update possession each tick
            self._recalculate_possession()

            # ── 3. Check for opponent tactical adjustment ──
            pre_adj_evt_count = len(self.state.events)
            opp_adjustments = await self.opponent_agent.evaluate(self.state)
            for adj in opp_adjustments:
                self._apply_tactical_adjustment(adj)

            # ── 4. Process pending opponent counter-adjustments ──
            pending_adj = await self.opponent_agent.tick_pending(self.state)
            for adj in pending_adj:
                self._apply_tactical_adjustment(adj)

            # ── 5. Emit any tactical adjustment events that were just added ──
            for te in self.state.events[pre_adj_evt_count:]:
                if te.event_type == "tactical_adjustment" and not getattr(te, '_pushed', False):
                    te._pushed = True
                    await self._emit_event(emit, te)

            # ── 6. Tick cooldowns ──
            if self.state.home_tactical_cooldown > 0:
                self.state.home_tactical_cooldown -= advance
            if self.state.away_tactical_cooldown > 0:
                self.state.away_tactical_cooldown -= advance

            # ── 7. Apply goal/morale (NOW, right before emission) ──
            # Deferred from step 2 so polling state doesn't see score before SSE event
            if event.event_type == "goal" and event.team == "home":
                self.state.home_score += 1
                goal_events_this_half += 1
                self.state.home_morale = min(1.0, self.state.home_morale + 0.1)
                self.state.away_morale = max(0.0, self.state.away_morale - 0.05)
            elif event.event_type == "goal" and event.team == "away":
                self.state.away_score += 1
                goal_events_this_half += 1
                self.state.away_morale = min(1.0, self.state.away_morale + 0.1)
                self.state.home_morale = max(0.0, self.state.home_morale - 0.05)

            # ── 8. Emit event (score & event arrive together) ──
            await self._emit_event(emit, event)
            await self._save_state()

            # ── 9. Sleep until next tick ──
            elapsed = time.monotonic() - tick_start
            sleep_time = max(0.5, TICK_INTERVAL - elapsed)
            await asyncio.sleep(sleep_time)

            # ── 10. Check half-end ──
            # At minute 45 or 90, we add injury time
            if half == 1 and self.state.match_minute >= half_end:
                if self.state.match_minute < half_end + injury_time:
                    # Still in injury time — keep going
                    continue
                else:
                    break
            elif half == 2 and self.state.match_minute >= half_end:
                if self.state.match_minute < half_end + injury_time:
                    continue
                else:
                    break

    # ── Tactical adjustments ─────────────────────────────────────────────

    async def apply_user_adjustment(
        self, adjustment_type: str, from_value: Optional[str] = None,
        to_value: Optional[str] = None, reason: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Apply a tactical adjustment requested by the user (home team).

        Returns (success: bool, message: str).
        """
        # 无冷却限制，可连续调整

        # Validate based on type
        adj_type = adjustment_type

        if adj_type == TacticalAdjustmentType.SUBSTITUTION:
            ok, msg = self._validate_user_substitution(from_value, to_value)
            if not ok:
                return False, msg
        elif adj_type == TacticalAdjustmentType.FORMATION_CHANGE:
            if to_value not in AVAILABLE_FORMATIONS:
                return False, f"无效阵型：{to_value}"
            if to_value == self.state.home_formation:
                return False, "已经是该阵型"
        elif adj_type == TacticalAdjustmentType.ALL_OUT_ATTACK:
            # Can only use when trailing
            if self.state.home_score >= self.state.away_score:
                return False, "全力进攻仅在落后时可用"
        elif adj_type == TacticalAdjustmentType.TIME_WASTING:
            # Can only use when leading
            if self.state.home_score <= self.state.away_score:
                return False, "拖延时间仅在领先时可用"

        # Create adjustment
        adj = TacticalAdjustment(
            adjustment_type=adj_type,
            team="home",
            from_value=from_value or "",
            to_value=to_value or "",
            reason=reason or "",
            trigger_source="user",
            match_minute=self.state.match_minute,
        )

        # Apply to state
        self._apply_tactical_adjustment(adj)

        # Emit the adjustment event to SSE clients (mark _pushed so
        # _run_half step 5 won't re-emit the same event)
        if self._emit_callback and self.state.events and self.state.events[-1].event_type == "tactical_adjustment":
            self.state.events[-1]._pushed = True
            await self._emit_event(self._emit_callback, self.state.events[-1])

        # Set cooldown
        cooldown_info = USER_TACTICAL_ADJUSTMENTS.get(adj_type, {})
        self.state.home_tactical_cooldown = cooldown_info.get("cooldown", TACTICAL_ADJUSTMENT_COOLDOWN)

        # Trigger opponent counter
        await self.opponent_agent.counter_adjust(adj, self.state)

        return True, "战术调整已执行"

    def _validate_user_substitution(self, off_name: Optional[str], on_name: Optional[str]) -> Tuple[bool, str]:
        """Validate a user substitution request."""
        if not off_name or not on_name:
            return False, "请选择换下和换上球员"
        if off_name == on_name:
            return False, "换下和换上球员不能相同"
        if self.state.home_substitutions_used >= SUBSTITUTION_LIMIT:
            return False, "换人次数已用完（最多5次）"
        # Check player is active
        if not any(p.name == off_name for p in self.state.active_players_home):
            return False, f"{off_name}不在场上"
        # Check player is on bench
        if not any(p.name == on_name for p in self.state.bench_players_home):
            return False, f"{on_name}不在替补席"
        return True, ""

    def _apply_tactical_adjustment(self, adj: TacticalAdjustment):
        """Apply a tactical adjustment to the match state and emit an event."""
        self.state.tactical_adjustments.append(adj)

        is_home = adj.team == "home"
        adj_type = adj.adjustment_type
        team_label = "主队" if is_home else "客队"

        if adj_type == TacticalAdjustmentType.SUBSTITUTION:
            self._apply_substitution(adj, is_home)
        elif adj_type == TacticalAdjustmentType.FORMATION_CHANGE:
            if is_home:
                self.state.home_formation = adj.to_value or self.state.home_formation
            else:
                self.state.away_formation = adj.to_value or self.state.away_formation
        elif adj_type == TacticalAdjustmentType.ATTACK_BOOST:
            if is_home:
                self.state.home_attack_modifier = min(2.0, self.state.home_attack_modifier + 0.3)
            else:
                self.state.away_attack_modifier = min(2.0, self.state.away_attack_modifier + 0.3)
        elif adj_type == TacticalAdjustmentType.DEFENSE_BOOST:
            if is_home:
                self.state.home_defense_modifier = min(2.0, self.state.home_defense_modifier + 0.3)
            else:
                self.state.away_defense_modifier = min(2.0, self.state.away_defense_modifier + 0.3)
        elif adj_type == TacticalAdjustmentType.POSSESSION_FOCUS:
            if is_home:
                self.state.home_defense_modifier = min(1.5, self.state.home_defense_modifier + 0.15)
                self.state.match_tempo = "slow"
            else:
                self.state.away_defense_modifier = min(1.5, self.state.away_defense_modifier + 0.15)
                self.state.match_tempo = "slow"
        elif adj_type == TacticalAdjustmentType.COUNTER_ATTACK:
            if is_home:
                self.state.home_attack_modifier = max(0.7, self.state.home_attack_modifier - 0.1)
                self.state.home_defense_modifier = min(1.5, self.state.home_defense_modifier + 0.2)
            else:
                self.state.away_attack_modifier = max(0.7, self.state.away_attack_modifier - 0.1)
                self.state.away_defense_modifier = min(1.5, self.state.away_defense_modifier + 0.2)
        elif adj_type == TacticalAdjustmentType.HIGH_PRESS:
            if is_home:
                self.state.home_attack_modifier = min(1.8, self.state.home_attack_modifier + 0.2)
                self.state.home_defense_modifier = min(1.8, self.state.home_defense_modifier + 0.2)
            else:
                self.state.away_attack_modifier = min(1.8, self.state.away_attack_modifier + 0.2)
                self.state.away_defense_modifier = min(1.8, self.state.away_defense_modifier + 0.2)
        elif adj_type == TacticalAdjustmentType.LOW_BLOCK:
            if is_home:
                self.state.home_defense_modifier = max(0.5, self.state.home_defense_modifier - 0.2)
            else:
                self.state.away_defense_modifier = max(0.5, self.state.away_defense_modifier - 0.2)
        elif adj_type == TacticalAdjustmentType.ALL_OUT_ATTACK:
            if is_home:
                self.state.home_attack_modifier = 2.0
                self.state.home_defense_modifier = 0.3
            else:
                self.state.away_attack_modifier = 2.0
                self.state.away_defense_modifier = 0.3
            self.state.match_tempo = "very_high"
        elif adj_type == TacticalAdjustmentType.TIME_WASTING:
            self.state.match_tempo = "very_slow"

        # ── Generate a match event for this tactical adjustment ──
        # Build a human-readable description
        if adj_type == TacticalAdjustmentType.SUBSTITUTION:
            desc = f"{team_label}换人：{adj.from_value} ↓，{adj.to_value} ↑"
        elif adj_type == TacticalAdjustmentType.FORMATION_CHANGE:
            desc = f"{team_label}变阵：{adj.from_value or '原阵型'} → {adj.to_value}"
        else:
            # Use the USER_TACTICAL_ADJUSTMENTS label if available, else the type name
            from event_types import USER_TACTICAL_ADJUSTMENTS
            label = USER_TACTICAL_ADJUSTMENTS.get(adj_type, {}).get("label", adj_type)
            source = "AI " if adj.trigger_source != "user" else ""
            desc = f"{team_label}{source}战术调整：{label}"
            if adj.reason:
                desc += f"（{adj.reason}）"

        evt = MatchEvent(
            event_type="tactical_adjustment",
            event_subtype=adj_type,
            team=adj.team,
            actor_name=adj.reason or adj.adjustment_type,
            description=desc,
            match_minute=self.state.match_minute,
            half=self.state.match_half,
            importance=4,
            extra={"adjustment_type": adj_type, "trigger_source": adj.trigger_source},
        )
        self.state.events.append(evt)

        logger.info("Tactical adjustment applied: %s for %s team", adj_type, adj.team)

    def _apply_substitution(self, adj: TacticalAdjustment, is_home: bool):
        """Execute a substitution — swap a player."""
        active = self.state.active_players_home if is_home else self.state.active_players_away
        bench = self.state.bench_players_home if is_home else self.state.bench_players_away

        player_off = next((p for p in active if p.name == adj.from_value), None)
        player_on = next((p for p in bench if p.name == adj.to_value), None)

        if player_off and player_on:
            active.remove(player_off)
            bench.remove(player_on)
            active.append(player_on)
            bench.append(player_off)

            if is_home:
                self.state.home_substitutions_used += 1
            else:
                self.state.away_substitutions_used += 1

            # Morale boost for making a sub
            if is_home:
                self.state.home_morale = min(1.0, self.state.home_morale + 0.05)
            else:
                self.state.away_morale = min(1.0, self.state.away_morale + 0.05)

            logger.info("Substitution: %s OFF, %s ON (%s)", adj.from_value, adj.to_value, adj.team)

    def _recalculate_possession(self):
        """Recalculate possession based on modifiers."""
        ha = max(0.3, self.state.home_attack_modifier or 1.0)
        aa = max(0.3, self.state.away_attack_modifier or 1.0)
        total = ha + aa
        self.state.stats.home_possession = round((ha / total) * 100, 1)
        self.state.stats.away_possession = round((aa / total) * 100, 1)

    # ── State persistence ───────────────────────────────────────────────

    async def _save_state(self):
        """Persist current match state to the database."""
        try:
            update_match_state(self.state)
        except Exception as exc:
            logger.error("Failed to save match state: %s", exc)

    # ── Event emission ──────────────────────────────────────────────────

    async def _emit_event(self, emit: EventEmitter, event: MatchEvent):
        """Emit a single match event to connected clients."""
        data = {
            "type": "match_event",
            "session_id": self.session_id,
            "data": {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "event_subtype": event.event_subtype,
                "team": event.team,
                "actor_name": event.actor_name,
                "target_name": event.target_name,
                "description": event.description,
                "match_minute": event.match_minute,
                "half": event.half,
                "importance": event.importance,
                "position": event.position,
                "score": event.extra.get("score") if isinstance(event.extra, dict) else None,
                "home_score": self.state.home_score,
                "away_score": self.state.away_score,
            },
        }
        try:
            emit("match_event", data)
        except Exception as exc:
            logger.warning("Event emission failed: %s", exc)

    async def _emit_state(self, emit: EventEmitter):
        """Emit full match state."""
        data = {
            "type": "match_state",
            "session_id": self.session_id,
            "data": self._get_state_snapshot(),
        }
        try:
            emit("match_state", data)
        except Exception as exc:
            logger.warning("State emission failed: %s", exc)

    async def _emit_half_time(self, emit: EventEmitter):
        """Emit half-time state + narrative."""
        narrative = await self.event_generator.generate_narrative(self.state, "上半场")
        data = {
            "type": "half_time",
            "session_id": self.session_id,
            "data": {
                **self._get_state_snapshot(),
                "narrative": narrative,
            },
        }
        try:
            emit("half_time", data)
        except Exception as exc:
            logger.warning("Half-time emission failed: %s", exc)

    async def _emit_full_time(self, emit: EventEmitter):
        """Emit full-time state + narrative."""
        narrative = await self.event_generator.generate_narrative(self.state, "全场")
        data = {
            "type": "full_time",
            "session_id": self.session_id,
            "data": {
                **self._get_state_snapshot(),
                "narrative": narrative,
            },
        }
        try:
            emit("full_time", data)
        except Exception as exc:
            logger.warning("Full-time emission failed: %s", exc)

    def _get_state_snapshot(self) -> dict:
        """Get a JSON-serializable snapshot of the current match state."""
        return {
            "session_id": self.session_id,
            "match_id": self.state.match_id,
            "home_team": self.state.home_team_name,
            "away_team": self.state.away_team_name,
            "home_score": self.state.home_score,
            "away_score": self.state.away_score,
            "match_minute": self.state.match_minute,
            "match_half": self.state.match_half,
            "match_status": self.state.match_status.value,
            "is_paused": self._paused,
            "home_formation": self.state.home_formation,
            "away_formation": self.state.away_formation,
            "home_attack_modifier": round(self.state.home_attack_modifier, 2),
            "home_defense_modifier": round(self.state.home_defense_modifier, 2),
            "away_attack_modifier": round(self.state.away_attack_modifier, 2),
            "away_defense_modifier": round(self.state.away_defense_modifier, 2),
            "home_morale": round(self.state.home_morale, 2),
            "away_morale": round(self.state.away_morale, 2),
            "match_tempo": self.state.match_tempo,
            "home_substitutions_used": self.state.home_substitutions_used,
            "away_substitutions_used": self.state.away_substitutions_used,
            "home_tactical_cooldown": max(0, self.state.home_tactical_cooldown),
            "away_tactical_cooldown": max(0, self.state.away_tactical_cooldown),
            "stats": {
                "home_shots": self.state.stats.home_shots,
                "away_shots": self.state.stats.away_shots,
                "home_shots_on_target": self.state.stats.home_shots_on_target,
                "away_shots_on_target": self.state.stats.away_shots_on_target,
                "home_fouls": self.state.stats.home_fouls,
                "away_fouls": self.state.stats.away_fouls,
                "home_corners": self.state.stats.home_corners,
                "away_corners": self.state.stats.away_corners,
                "home_offsides": self.state.stats.home_offsides,
                "away_offsides": self.state.stats.away_offsides,
                "home_yellows": self.state.stats.home_yellows,
                "away_yellows": self.state.stats.away_yellows,
                "home_reds": self.state.stats.home_reds,
                "away_reds": self.state.stats.away_reds,
                "home_possession": self.state.stats.home_possession,
                "away_possession": self.state.stats.away_possession,
            },
            "active_players_home": [
                {"name": p.name, "position": p.position, "shirt_number": p.shirt_number, "rating": p.rating}
                for p in self.state.active_players_home
            ],
            "active_players_away": [
                {"name": p.name, "position": p.position, "shirt_number": p.shirt_number, "rating": p.rating}
                for p in self.state.active_players_away
            ],
            "bench_players_home": [
                {"name": p.name, "position": p.position, "shirt_number": p.shirt_number, "rating": p.rating}
                for p in self.state.bench_players_home
            ],
            "bench_players_away": [
                {"name": p.name, "position": p.position, "shirt_number": p.shirt_number, "rating": p.rating}
                for p in self.state.bench_players_away
            ],
        }
