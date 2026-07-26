"""LLM prompt templates for match simulation."""
import json
from typing import List, Optional, Dict, Any
from models import MatchState, Player


def build_match_state_context(state: MatchState) -> dict:
    """Build a context dictionary from the current match state for use in LLM prompts."""
    home_active = state.active_players_home or state.home_players[:11]
    away_active = state.active_players_away or state.away_players[:11]

    return {
        "home_team": state.home_team_name,
        "away_team": state.away_team_name,
        "home_formation": state.home_formation,
        "away_formation": state.away_formation,
        "home_score": state.home_score,
        "away_score": state.away_score,
        "minute": state.match_minute,
        "half": "上半场" if state.match_half == 1 else "下半场",
        "home_lineup": ", ".join(f"{p.name}({p.position})" for p in home_active[:11]),
        "away_lineup": ", ".join(f"{p.name}({p.position})" for p in away_active[:11]),
        "home_possession": round(state.stats.home_possession, 1),
        "away_possession": round(state.stats.away_possession, 1),
        "home_shots": state.stats.home_shots,
        "away_shots": state.stats.away_shots,
        "home_shots_on": state.stats.home_shots_on_target,
        "away_shots_on": state.stats.away_shots_on_target,
        "home_fouls": state.stats.home_fouls,
        "away_fouls": state.stats.away_fouls,
        "home_corners": state.stats.home_corners,
        "away_corners": state.stats.away_corners,
        "home_yellows": state.stats.home_yellows,
        "away_yellows": state.stats.away_yellows,
        "home_reds": state.stats.home_reds,
        "away_reds": state.stats.away_reds,
        "home_attack_mod": round(state.home_attack_modifier, 2),
        "home_defense_mod": round(state.home_defense_modifier, 2),
        "away_attack_mod": round(state.away_attack_modifier, 2),
        "away_defense_mod": round(state.away_defense_modifier, 2),
        "match_tempo": state.match_tempo,
        "home_morale": round(state.home_morale, 2),
        "away_morale": round(state.away_morale, 2),
        "home_subs_used": state.home_substitutions_used,
        "away_subs_used": state.away_substitutions_used,
    }


def build_recent_events(state: MatchState, count: int = 5) -> str:
    """Build a summary of recent events for context."""
    recent = state.events[-count:] if state.events else []
    if not recent:
        return "（比赛刚开始，暂无事件）"
    lines = []
    for e in recent:
        team_label = "主队" if e.team == "home" else "客队"
        lines.append(f"第{e.match_minute}分钟 [{team_label}] {e.description}")
    return "\n".join(lines)


def build_score_context(state: MatchState) -> str:
    """Build score context that influences event generation."""
    diff = state.home_score - state.away_score
    if diff > 0:
        return "\n- 主队领先，客队会加强进攻，主队可能收缩防守"
    elif diff < 0:
        return "\n- 客队领先，主队会加强进攻，客队可能收缩防守"
    else:
        return "\n- 比分持平，双方都在寻求突破口"


# ═══════════════════════════════════════════════════════════════════════
# Event Generation Prompt
# ═══════════════════════════════════════════════════════════════════════

EVENT_GENERATION_PROMPT = """你是一名专业的足球比赛AI解说员，正在模拟一场真实的足球比赛。

## 比赛背景
主队：{home_team}（阵型：{home_formation}）
客队：{away_team}（阵型：{away_formation}）
当前比分：{home_score} - {away_score}
比赛时间：第{minute}分钟（{half}）
控球率：主队 {home_possession}% - 客队 {away_possession}%

## 主队阵容（场上11人）
{home_lineup}

## 客队阵容（场上11人）
{away_lineup}

## 近期事件（最近5个）
{recent_events}

## 当前战术态势
- 主队进攻倾向评分：{home_attack_mod}（1=防守，10=进攻），防守倾向评分：{home_defense_mod}（1=低位，10=高位）
- 客队进攻倾向评分：{away_attack_mod}（1=防守，10=进攻），防守倾向评分：{away_defense_mod}（1=低位，10=高位）
- 比赛节奏：{match_tempo}
- 主队士气：{home_morale}，客队士气：{away_morale}{score_context}

## 双方数据统计
主队：射门 {home_shots}（射正{home_shots_on}），犯规 {home_fouls}，角球 {home_corners}，黄牌 {home_yellows}，红牌 {home_reds}
客队：射门 {away_shots}（射正{away_shots_on}），犯规 {away_fouls}，角球 {away_corners}，黄牌 {away_yellows}，红牌 {away_reds}

## 任务
请模拟接下来1-2分钟内可能发生的一个事件。事件类型从以下选择：
shot（射门）, goal（进球）, foul（犯规）, corner（角球）, offside（越位）, card（黄牌/红牌）, save（扑救）,
penalty（点球）, free_kick（任意球）, throw_in（界外球）, goal_kick（球门球）, passage_of_play（控球推进）

## 重要规则
- 进球必须符合足球逻辑：需要有射门球员、助攻方式描述
- 犯规地点要合理，黄牌/红牌要有适当的犯规描述
- 角球和任意球要说明是如何获得的
- 比赛节奏要自然：比分接近时更激烈，大比分领先时节奏放缓
- 球员名称必须从阵容中选择，不能虚构球员
- 进球概率：比分落后的球队在最后20分钟会更有进攻性
- 伤停补时在45分钟和90分钟时触发
- 每次只生成一个事件
- 所有描述必须使用中文

## 返回格式
请以JSON格式返回，不要包含任何其他文字：
{{
    "event_type": "事件类型",
    "event_subtype": "shot_on_target/shot_off_target/shot_blocked/shot_woodwork/yellow_card/red_card/goal_open_play/goal_header/goal_penalty/goal_free_kick/goal_own_goal/foul_tactical/foul_professional/foul_handball（没有则填null）",
    "actor_team": "home 或 away",
    "actor_name": "执行球员姓名",
    "target_name": "相关球员（助攻者/犯规对象等，没有则填null）",
    "description": "详细的中文解说描述（50-100字），要生动专业",
    "importance": 1-5（1=普通，5=重大事件如进球/红牌）,
    "position": "事件发生区域（如'禁区前沿'、'左路'、'中场'、'小禁区'等）",
    "match_minute_advance": 3-5（该事件消耗的比赛分钟数）
}}
"""


# ═══════════════════════════════════════════════════════════════════════
# Opponent Tactical Decision Prompt
# ═══════════════════════════════════════════════════════════════════════

OPPONENT_TACTICAL_PROMPT = """你是一名职业足球教练，正在指挥你的球队（{team_name}）进行比赛。

## 当前比赛状态
对手：{opponent_name}
当前比分：{our_score} - {opponent_score}（我们是{team_name}）
比赛时间：第{minute}分钟（{half}）
我们的控球率：{our_possession}%

## 我们的阵容
{our_lineup}

## 对手阵容
{opponent_lineup}

## 数据统计
我们：射门 {our_shots}（射正{our_shots_on}），犯规 {our_fouls}，角球 {our_corners}
对手：射门 {opp_shots}（射正{opp_shots_on}），犯规 {opp_fouls}，角球 {opp_corners}

## 近期关键事件
{recent_events}

## 对手最近的战术调整
{opponent_adjustments}

## 任务
作为教练，你需要决定是否进行战术调整。请分析当前局势并给出决策。

你可以选择以下调整类型（可多选，最多2项）：
- substitution: 换人（需要指定换下和换上的球员）
- formation_change: 变阵（需要指定新阵型，如4-4-2, 3-5-2等）
- attack_boost: 加强进攻（进攻倾向+1）
- defense_boost: 加强防守（防守倾向+1）
- possession_focus: 控制球权，放慢节奏
- counter_attack: 防守反击策略
- high_press: 高位逼抢
- all_out_attack: 全力进攻（通常在落后且时间不多时使用）

## 决策指导
- 领先时：60分钟前保持原战术，60分钟后可考虑加强防守
- 平局时：70分钟后可考虑加强进攻
- 落后时：根据分差和时间决定是否全力进攻
- 换人通常在55-75分钟之间进行
- 不要频繁调整，两次调整之间至少间隔8分钟（比赛时间）

## 返回格式
请以JSON格式返回：
{{
    "need_adjustment": true/false,
    "reasoning": "你的战术分析（中文，50-100字）",
    "adjustments": [
        {{
            "type": "调整类型",
            "from_value": "原值（如原阵型、原球员名）",
            "to_value": "新值（如新阵型、新球员名）",
            "reason": "具体原因（中文，20-40字）"
        }}
    ]
}}
"""


# ═══════════════════════════════════════════════════════════════════════
# Match Narrative Prompt (Half-Time / Full-Time)
# ═══════════════════════════════════════════════════════════════════════

MATCH_NARRATIVE_PROMPT = """你是一名专业的足球比赛评论员。请为以下比赛生成{period}总结。

## 比赛信息
{home_team} vs {away_team}
当前比分：{home_score} - {away_score}
比赛时间：第{minute}分钟
主队阵型：{home_formation}
客队阵型：{away_formation}

## 数据统计
主队：射门 {home_shots}（射正{home_shots_on}），犯规 {home_fouls}，角球 {home_corners}，黄牌 {home_yellows}，红牌 {home_reds}
客队：射门 {away_shots}（射正{away_shots_on}），犯规 {away_fouls}，角球 {away_corners}，黄牌 {away_yellows}，红牌 {away_reds}
控球率：主队 {home_possession}% - 客队 {away_possession}%

## 进球记录
{goals_list}

## 关键事件
{key_events}

## 任务
请生成一段{period}总结（中文，150-250字），包括：
- 总体比赛态势
- 关键球员表现
- 战术分析
- {outlook_label}
"""


# ═══════════════════════════════════════════════════════════════════════
# Build prompt functions
# ═══════════════════════════════════════════════════════════════════════

def build_event_prompt(state: MatchState) -> str:
    """Build the event generation prompt from current match state."""
    ctx = build_match_state_context(state)
    ctx["recent_events"] = build_recent_events(state)
    ctx["score_context"] = build_score_context(state)
    return EVENT_GENERATION_PROMPT.format(**ctx)


def build_opponent_prompt(state: MatchState, is_away: bool = True) -> str:
    """Build the opponent tactical decision prompt with full team-relative context."""
    ctx = build_match_state_context(state)
    ctx["recent_events"] = build_recent_events(state, 8)
    ctx["opponent_adjustments"] = _build_opponent_adjustments(state)

    if is_away:
        ctx["team_name"] = ctx["away_team"]
        ctx["opponent_name"] = ctx["home_team"]
        ctx["our_score"] = ctx["away_score"]
        ctx["opponent_score"] = ctx["home_score"]
        ctx["our_lineup"] = ctx["away_lineup"]
        ctx["opponent_lineup"] = ctx["home_lineup"]
        ctx["our_possession"] = ctx["away_possession"]
        ctx["our_shots"] = ctx["away_shots"]
        ctx["our_shots_on"] = ctx["away_shots_on"]
        ctx["our_fouls"] = ctx["away_fouls"]
        ctx["our_corners"] = ctx["away_corners"]
        ctx["opp_shots"] = ctx["home_shots"]
        ctx["opp_shots_on"] = ctx["home_shots_on"]
        ctx["opp_fouls"] = ctx["home_fouls"]
        ctx["opp_corners"] = ctx["home_corners"]
    else:
        ctx["team_name"] = ctx["home_team"]
        ctx["opponent_name"] = ctx["away_team"]
        ctx["our_score"] = ctx["home_score"]
        ctx["opponent_score"] = ctx["away_score"]
        ctx["our_lineup"] = ctx["home_lineup"]
        ctx["opponent_lineup"] = ctx["away_lineup"]
        ctx["our_possession"] = ctx["home_possession"]
        ctx["our_shots"] = ctx["home_shots"]
        ctx["our_shots_on"] = ctx["home_shots_on"]
        ctx["our_fouls"] = ctx["home_fouls"]
        ctx["our_corners"] = ctx["home_corners"]
        ctx["opp_shots"] = ctx["away_shots"]
        ctx["opp_shots_on"] = ctx["away_shots_on"]
        ctx["opp_fouls"] = ctx["away_fouls"]
        ctx["opp_corners"] = ctx["away_corners"]

    return OPPONENT_TACTICAL_PROMPT.format(**ctx)


def build_narrative_prompt(state: MatchState, period: str = "上半场") -> str:
    """Build the half-time/full-time narrative prompt."""
    ctx = build_match_state_context(state)
    ctx["period"] = period
    ctx["goals_list"] = _build_goals_list(state)
    ctx["key_events"] = build_recent_events(state, 10)
    # 半场→「下半场展望」，全场→「全场总结」
    ctx["outlook_label"] = "下半场展望" if period == "上半场" else "全场总结"
    return MATCH_NARRATIVE_PROMPT.format(**ctx)


def _build_goals_list(state: MatchState) -> str:
    """Build a list of goals from match events."""
    goals = [e for e in state.events if e.event_type == "goal"]
    if not goals:
        return "（暂无进球）"
    return "\n".join(
        f"- 第{e.match_minute}分钟 {'主队' if e.team == 'home' else '客队'} {e.actor_name}：{e.description}"
        for e in goals
    )


def _build_opponent_adjustments(state: MatchState) -> str:
    """Build a summary of recent opponent tactical adjustments."""
    adjustments = [a for a in state.tactical_adjustments if a.team != "home"]
    if not adjustments:
        return "（暂无对手战术调整）"
    lines = []
    for a in adjustments[-5:]:
        lines.append(f"- 第{a.match_minute}分钟：{a.reason or a.adjustment_type}")
    return "\n".join(lines)
