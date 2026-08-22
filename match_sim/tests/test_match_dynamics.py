import asyncio
import json
import os
import random
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


MATCH_SIM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(MATCH_SIM_DIR)
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, MATCH_SIM_DIR)

from event_generator import EventGenerator
from match_dynamics import MatchDynamics
from match_engine import MatchEngine
from models import MatchState, MatchStats, MatchStatus, Player, TacticalAdjustment
from prompts.event_prompts import _build_opponent_adjustments


POSITIONS = ["GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST"]


def make_players(prefix: str, rating: int = 84):
    return [
        Player(i, 1, f"{prefix}{i}", position, i, 25, "测试", rating, {}, True)
        for i, position in enumerate(POSITIONS)
    ]


def make_state(home_rating: int = 84, away_rating: int = 84):
    home = make_players("H", home_rating)
    away = make_players("A", away_rating)
    return MatchState(
        session_id="test",
        home_team_name="主队",
        away_team_name="客队",
        active_players_home=home,
        active_players_away=away,
        home_players=home,
        away_players=away,
        stats=MatchStats(),
    )


def simulate(seed: int, home_attack_after_half: bool = False):
    state = make_state()
    dynamics = MatchDynamics(random.Random(seed))
    for minute in range(1, 91, 5):
        state.match_minute = minute
        if minute >= 46 and home_attack_after_half and not state.tactical_adjustments:
            state.home_attack_modifier = 1.35
            state.home_defense_modifier = 0.92
            state.match_tempo = "high"
            state.tactical_adjustments.append(
                TacticalAdjustment(
                    adjustment_type="attack_boost",
                    team="home",
                    match_minute=46,
                )
            )
        event = dynamics.maybe_build_goal(state)
        if event and event.team == "home":
            state.home_score += 1
        elif event:
            state.away_score += 1
    return state.home_score, state.away_score


class MatchDynamicsTests(unittest.TestCase):
    def test_balanced_matches_have_realistic_goal_distribution(self):
        scores = [simulate(seed) for seed in range(2000)]
        zero_zero_rate = sum(score == (0, 0) for score in scores) / len(scores)
        average_goals = sum(home + away for home, away in scores) / len(scores)
        self.assertLess(zero_zero_rate, 0.10)
        self.assertGreater(average_goals, 2.1)
        self.assertLess(average_goals, 2.8)

    def test_attack_adjustment_increases_home_scoring(self):
        baseline = [simulate(seed) for seed in range(1500)]
        attacking = [simulate(seed, home_attack_after_half=True) for seed in range(1500)]
        baseline_home = sum(score[0] for score in baseline) / len(baseline)
        attacking_home = sum(score[0] for score in attacking) / len(attacking)
        self.assertGreater(attacking_home, baseline_home + 0.15)

    def test_formation_lineup_and_defence_change_threat(self):
        state = make_state()
        dynamics = MatchDynamics(random.Random(1))
        baseline = dynamics.threat_scores(state)

        state.home_formation = "3-4-3"
        attacking_formation = dynamics.threat_scores(state)
        self.assertGreater(attacking_formation["home"], baseline["home"])

        state.home_formation = "5-3-2"
        defensive_formation = dynamics.threat_scores(state)
        self.assertLess(defensive_formation["away"], attacking_formation["away"])

        state.active_players_home = make_players("Elite", 91)
        elite_lineup = dynamics.threat_scores(state)
        self.assertGreater(elite_lineup["home"], defensive_formation["home"])

        state.home_defense_modifier = 1.4
        reinforced = dynamics.threat_scores(state)
        self.assertLess(reinforced["away"], elite_lineup["away"])

    def test_engine_adjustments_feed_the_probability_model(self):
        engine = MatchEngine("主队", "客队", 1, 2, make_players("H"), make_players("A"))
        dynamics = MatchDynamics(random.Random(1))
        baseline = dynamics.threat_scores(engine.state)

        engine._apply_tactical_adjustment(
            TacticalAdjustment(
                adjustment_type="attack_boost",
                team="home",
                trigger_source="user",
                match_minute=30,
            )
        )
        after_attack = dynamics.threat_scores(engine.state)
        self.assertGreater(after_attack["home"], baseline["home"])
        self.assertGreater(after_attack["away"], baseline["away"])

        engine._apply_tactical_adjustment(
            TacticalAdjustment(
                adjustment_type="defense_boost",
                team="away",
                trigger_source="opponent_agent",
                match_minute=35,
            )
        )
        after_counter = dynamics.threat_scores(engine.state)
        self.assertLess(after_counter["home"], after_attack["home"])

    def test_recent_adjustment_is_visible_in_goal_commentary(self):
        state = make_state()
        state.match_minute = 60
        state.tactical_adjustments.append(
            TacticalAdjustment(
                adjustment_type="formation_change",
                team="home",
                to_value="3-4-3",
                match_minute=55,
            )
        )
        dynamics = MatchDynamics(random.Random(31))
        event = dynamics.maybe_build_goal(state)
        self.assertIsNotNone(event)
        if event.team == "home":
            self.assertIn("变阵至3-4-3", event.description)

    def test_llm_goal_is_gated_by_mechanics(self):
        state = make_state()
        payload = {
            "event_type": "goal",
            "event_subtype": "goal_open_play",
            "actor_team": "home",
            "actor_name": "H10",
            "target_name": None,
            "description": "射门得分",
            "importance": 5,
            "position": "禁区内",
            "match_minute_advance": 5,
        }
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False)))]
        )
        generator = EventGenerator(random.Random(0))  # first roll is above goal probability
        with patch("event_generator.llm_chat", return_value=response):
            event, stats = asyncio.run(generator.generate(state))
        self.assertEqual(event.event_type, "shot")
        self.assertEqual(event.event_subtype, "shot_on_target")
        self.assertEqual(stats.home_shots_on_target, 1)

    def test_opponent_prompt_reads_user_adjustments(self):
        state = make_state()
        state.tactical_adjustments.extend([
            TacticalAdjustment(team="home", reason="主队加强进攻", match_minute=20),
            TacticalAdjustment(team="away", reason="客队加强防守", match_minute=25),
        ])
        summary = _build_opponent_adjustments(state, "home")
        self.assertIn("主队加强进攻", summary)
        self.assertNotIn("客队加强防守", summary)

    def test_full_engine_reaches_full_time_with_generated_events(self):
        players_home = make_players("H")
        players_away = make_players("A")
        engine = MatchEngine("主队", "客队", 1, 2, players_home, players_away)
        engine.event_generator = EventGenerator(random.Random(7))

        async def generated_event(state):
            return engine.event_generator._fallback(state)

        async def no_adjustments(state):
            return []

        async def no_save():
            return None

        async def narrative(state, period):
            return f"{period}结束"

        async def no_sleep(_seconds):
            return None

        engine.event_generator.generate = generated_event
        engine.event_generator.generate_narrative = narrative
        engine.opponent_agent.evaluate = no_adjustments
        engine.opponent_agent.tick_pending = no_adjustments
        engine._save_state = no_save

        with patch("match_engine.asyncio.sleep", new=no_sleep):
            asyncio.run(engine.run(lambda *_args: None))

        self.assertEqual(engine.state.match_status, MatchStatus.FINISHED)
        self.assertGreaterEqual(engine.state.match_minute, 90)
        self.assertGreaterEqual(len(engine.state.events), 18)
        self.assertEqual(
            engine.state.home_score + engine.state.away_score,
            sum(event.event_type == "goal" for event in engine.state.events),
        )


if __name__ == "__main__":
    unittest.main()
