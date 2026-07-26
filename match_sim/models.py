"""Data models for the match simulation module."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class MatchStatus(str, Enum):
    CREATED = "created"
    FIRST_HALF = "first_half"
    HALF_TIME = "half_time"
    SECOND_HALF = "second_half"
    FINISHED = "finished"


class EventType(str, Enum):
    # Core gameplay
    SHOT = "shot"
    GOAL = "goal"
    SAVE = "save"
    FOUL = "foul"
    CORNER = "corner"
    OFFSIDE = "offside"
    THROW_IN = "throw_in"
    GOAL_KICK = "goal_kick"
    FREE_KICK = "free_kick"
    PENALTY = "penalty"
    # Disciplinary
    CARD = "card"
    # Squad
    SUBSTITUTION = "substitution"
    INJURY = "injury"
    # Tactical
    FORMATION_CHANGE = "formation_change"
    TACTICAL_ADJUSTMENT = "tactical_adjustment"
    # Match control
    KICK_OFF = "kick_off"
    HALF_TIME = "half_time"
    SECOND_HALF_KICK_OFF = "second_half_kick_off"
    FULL_TIME = "full_time"
    INJURY_TIME = "injury_time"
    # Narrative
    PASSAGE_OF_PLAY = "passage_of_play"
    COMMENTARY = "commentary"


class EventSubtype(str, Enum):
    # Shot
    SHOT_ON_TARGET = "shot_on_target"
    SHOT_OFF_TARGET = "shot_off_target"
    SHOT_BLOCKED = "shot_blocked"
    SHOT_WOODWORK = "shot_woodwork"
    # Goal
    GOAL_OPEN_PLAY = "goal_open_play"
    GOAL_HEADER = "goal_header"
    GOAL_PENALTY = "goal_penalty"
    GOAL_FREE_KICK = "goal_free_kick"
    GOAL_OWN_GOAL = "goal_own_goal"
    GOAL_VOLLEY = "goal_volley"
    GOAL_LONG_SHOT = "goal_long_shot"
    # Card
    YELLOW_CARD = "yellow_card"
    RED_CARD = "red_card"
    SECOND_YELLOW = "second_yellow"
    # Foul
    FOUL_TACTICAL = "foul_tactical"
    FOUL_PROFESSIONAL = "foul_professional"
    FOUL_HAND_BALL = "foul_handball"
    FOUL_DANGEROUS = "foul_dangerous"


class TacticalAdjustmentType(str, Enum):
    SUBSTITUTION = "substitution"
    FORMATION_CHANGE = "formation_change"
    ATTACK_BOOST = "attack_boost"
    DEFENSE_BOOST = "defense_boost"
    POSSESSION_FOCUS = "possession_focus"
    COUNTER_ATTACK = "counter_attack"
    HIGH_PRESS = "high_press"
    LOW_BLOCK = "low_block"
    ALL_OUT_ATTACK = "all_out_attack"
    TIME_WASTING = "time_wasting"


@dataclass
class Team:
    id: int
    name: str
    short_name: str
    league: str
    country: str
    strength_rating: int
    default_formation: str


@dataclass
class Player:
    id: int
    team_id: int
    name: str
    position: str
    shirt_number: int
    age: int
    nationality: str
    rating: int
    stats_json: dict
    is_starter: bool = True


@dataclass
class MatchEvent:
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    event_type: str = ""
    event_subtype: Optional[str] = None
    team: str = ""  # "home" or "away"
    actor_name: Optional[str] = None
    target_name: Optional[str] = None
    description: str = ""
    match_minute: int = 0
    half: int = 1
    importance: int = 3  # 1-5
    position: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TacticalAdjustment:
    adjustment_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    adjustment_type: str = ""
    team: str = ""  # "home" or "away"
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    reason: Optional[str] = None
    trigger_source: str = ""  # "user" or "opponent_agent"
    match_minute: int = 0


@dataclass
class MatchStats:
    home_shots: int = 0
    away_shots: int = 0
    home_shots_on_target: int = 0
    away_shots_on_target: int = 0
    home_fouls: int = 0
    away_fouls: int = 0
    home_corners: int = 0
    away_corners: int = 0
    home_offsides: int = 0
    away_offsides: int = 0
    home_yellows: int = 0
    away_yellows: int = 0
    home_reds: int = 0
    away_reds: int = 0
    home_possession: float = 50.0
    away_possession: float = 50.0


@dataclass
class MatchState:
    session_id: str
    match_id: Optional[int] = None
    home_team: Optional[Team] = None
    away_team: Optional[Team] = None
    home_team_name: str = ""
    away_team_name: str = ""
    home_score: int = 0
    away_score: int = 0
    match_minute: int = 0
    match_half: int = 1  # 1 = first half, 2 = second half
    match_status: MatchStatus = MatchStatus.CREATED
    home_formation: str = "4-3-3"
    away_formation: str = "4-3-3"
    home_players: List[Player] = field(default_factory=list)
    away_players: List[Player] = field(default_factory=list)
    active_players_home: List[Player] = field(default_factory=list)
    active_players_away: List[Player] = field(default_factory=list)
    bench_players_home: List[Player] = field(default_factory=list)
    bench_players_away: List[Player] = field(default_factory=list)
    events: List[MatchEvent] = field(default_factory=list)
    tactical_adjustments: List[TacticalAdjustment] = field(default_factory=list)
    home_substitutions_used: int = 0
    away_substitutions_used: int = 0
    stats: MatchStats = field(default_factory=MatchStats)
    home_attack_modifier: float = 1.0
    home_defense_modifier: float = 1.0
    away_attack_modifier: float = 1.0
    away_defense_modifier: float = 1.0
    home_morale: float = 0.5  # 0.0 to 1.0
    away_morale: float = 0.5
    match_tempo: str = "balanced"
    home_tactical_cooldown: int = 0
    away_tactical_cooldown: int = 0
    opponent_counter_pending: bool = False
    opponent_counter_tick: int = 0