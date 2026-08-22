"""Match mechanics that turn tactical choices into scoring chances.

The LLM supplies commentary and event variety. This module owns the football
probabilities so outcomes remain plausible when the LLM is conservative or
temporarily unavailable.
"""

import math
import random
from typing import Dict, List, Optional, Tuple

from event_types import USER_TACTICAL_ADJUSTMENTS
from models import MatchEvent, MatchState, Player


FORMATION_PROFILES: Dict[str, Tuple[float, float]] = {
    "4-3-3": (1.08, 0.98),
    "4-4-2": (1.02, 1.02),
    "3-5-2": (1.07, 0.96),
    "4-2-3-1": (1.01, 1.07),
    "3-4-3": (1.14, 0.90),
    "5-3-2": (0.91, 1.14),
    "4-1-4-1": (0.96, 1.10),
    "4-3-2-1": (1.05, 1.00),
}

TEMPO_FACTORS = {
    "very_slow": 0.58,
    "slow": 0.78,
    "balanced": 1.0,
    "high": 1.15,
    "very_high": 1.38,
}

ATTACKING_POSITIONS = {"ST", "CF", "LW", "RW", "CAM", "LM", "RM"}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _lineup_quality(players: List[Player]) -> float:
    """Return a modest quality multiplier from the active XI."""
    if not players:
        return 1.0
    overall = sum(p.rating for p in players) / len(players)
    attackers = [p.rating for p in players if p.position in ATTACKING_POSITIONS]
    attacking = sum(attackers) / len(attackers) if attackers else overall
    weighted_rating = overall * 0.55 + attacking * 0.45
    return _clamp(weighted_rating / 82.0, 0.82, 1.18)


class MatchDynamics:
    """Calculate team threat and independently resolve scoring opportunities."""

    BASE_GOAL_PROBABILITY = 0.115  # per five-minute event tick

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    def threat_scores(self, state: MatchState) -> Dict[str, float]:
        home_form_attack, home_form_defense = FORMATION_PROFILES.get(
            state.home_formation, (1.0, 1.0)
        )
        away_form_attack, away_form_defense = FORMATION_PROFILES.get(
            state.away_formation, (1.0, 1.0)
        )

        home_attack = _clamp(state.home_attack_modifier, 0.3, 2.2)
        away_attack = _clamp(state.away_attack_modifier, 0.3, 2.2)
        home_defense = _clamp(state.home_defense_modifier, 0.3, 2.2)
        away_defense = _clamp(state.away_defense_modifier, 0.3, 2.2)

        home = (
            home_attack
            * home_form_attack
            * _lineup_quality(state.active_players_home)
            * (0.85 + 0.30 * _clamp(state.home_morale, 0.0, 1.0))
            / math.sqrt(away_defense * away_form_defense)
        )
        away = (
            away_attack
            * away_form_attack
            * _lineup_quality(state.active_players_away)
            * (0.85 + 0.30 * _clamp(state.away_morale, 0.0, 1.0))
            / math.sqrt(home_defense * home_form_defense)
        )

        home *= 0.78 ** state.stats.home_reds
        away *= 0.78 ** state.stats.away_reds
        home *= 1.16 ** state.stats.away_reds
        away *= 1.16 ** state.stats.home_reds

        if state.match_minute >= 65:
            if state.home_score < state.away_score:
                home *= 1.12 if state.match_minute < 80 else 1.24
            elif state.away_score < state.home_score:
                away *= 1.12 if state.match_minute < 80 else 1.24

        # Recent instructions get a short response window. Persistent effects
        # are represented by modifiers, formation and the active lineup.
        for adjustment in state.tactical_adjustments:
            age = state.match_minute - adjustment.match_minute
            if 0 <= age <= 10:
                if adjustment.team == "home":
                    home *= 1.08
                elif adjustment.team == "away":
                    away *= 1.08

        return {"home": _clamp(home, 0.20, 3.5), "away": _clamp(away, 0.20, 3.5)}

    def goal_probability(self, state: MatchState) -> float:
        threat = self.threat_scores(state)
        openness = _clamp((threat["home"] + threat["away"]) / 2.0, 0.55, 2.0)
        tempo = TEMPO_FACTORS.get(state.match_tempo, 1.0)
        probability = self.BASE_GOAL_PROBABILITY * openness * tempo

        if state.match_minute >= 65 and state.home_score == state.away_score:
            probability *= 1.14
        if state.match_minute >= 70 and state.home_score == state.away_score == 0:
            probability *= 1.18

        return _clamp(probability, 0.045, 0.30)

    def maybe_build_goal(self, state: MatchState) -> Optional[MatchEvent]:
        probability = self.goal_probability(state)
        if self.rng.random() >= probability:
            return None

        threat = self.threat_scores(state)
        total = threat["home"] + threat["away"]
        team = "home" if self.rng.random() < threat["home"] / total else "away"
        players = state.active_players_home if team == "home" else state.active_players_away
        actor = self._choose_scorer(players)
        team_name = state.home_team_name if team == "home" else state.away_team_name
        influence = self._recent_tactical_influence(state, team)

        lead_in = (
            f"{team_name}刚才的{influence}迅速收到成效，"
            if influence
            else f"{team_name}连续组织攻势后撕开防线，"
        )
        actor_name = actor.name if actor else team_name
        description = (
            f"{lead_in}{actor_name}在禁区内抓住机会冷静完成射门，"
            "皮球越过门将飞入球网！"
        )

        return MatchEvent(
            event_type="goal",
            event_subtype="goal_open_play",
            team=team,
            actor_name=actor.name if actor else None,
            description=description,
            match_minute=state.match_minute,
            half=state.match_half,
            importance=5,
            position="禁区内",
            extra={
                "match_minute_advance": 5,
                "score": (
                    f"{state.home_score + (1 if team == 'home' else 0)}-"
                    f"{state.away_score + (1 if team == 'away' else 0)}"
                ),
                "goal_probability": round(probability, 4),
                "home_threat": round(threat["home"], 3),
                "away_threat": round(threat["away"], 3),
                "tactical_influence": influence,
            },
        )

    def _choose_scorer(self, players: List[Player]) -> Optional[Player]:
        if not players:
            return None
        weights = [
            max(1.0, p.rating - 60) * (2.2 if p.position in ATTACKING_POSITIONS else 0.55)
            for p in players
        ]
        return self.rng.choices(players, weights=weights, k=1)[0]

    @staticmethod
    def _recent_tactical_influence(state: MatchState, team: str) -> str:
        recent = [
            adjustment
            for adjustment in state.tactical_adjustments
            if adjustment.team == team
            and 0 <= state.match_minute - adjustment.match_minute <= 10
        ]
        if not recent:
            return ""
        adjustment = recent[-1]
        if adjustment.adjustment_type == "formation_change":
            return f"变阵至{adjustment.to_value}"
        if adjustment.adjustment_type == "substitution":
            return f"换人调整（{adjustment.to_value}登场）"
        return USER_TACTICAL_ADJUSTMENTS.get(adjustment.adjustment_type, {}).get(
            "label", "战术调整"
        )
