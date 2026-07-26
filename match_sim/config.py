import os
import sys

# Add parent dir to path to import ai_agent modules
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, PROJECT_DIR)

# Reuse shared config from ai_agent
from ai_agent.config import API_KEY, BASE_URL_CHAT, LLM_MODEL

# 持久化由 Go 后端统一管理（写入本地 MySQL 的 match_sim_* 表），
# Python 经 http://localhost:8080/api/match-data/* 读写，不再使用本地 SQLite。
# Go 数据端点基址（可通过环境变量覆盖）
GO_DATA_BASE = os.environ.get("MATCH_DATA_BASE", "http://localhost:8080/api/match-data")

# Match simulation settings
TICK_INTERVAL = 0.5            # 每 tick 的真实秒数（配合 5 分钟推进，全场比赛 ≈ 45 秒）
MATCH_MINUTES = 90             # 常规比赛分钟数
HALF_TIME_LENGTH = 45          # 每半场分钟
INJURY_TIME_PER_HALF = 1       # 每半场补时分钟
SUBSTITUTION_LIMIT = 5         # 每队最大换人次数
TACTICAL_ADJUSTMENT_COOLDOWN = 0  # 战术冷却（0=无冷却，可连续调整）
OPPONENT_COUNTER_DELAY = 2     # 对手反制延迟（tick 数）

# LLM settings
EVENT_TEMPERATURE = 0.8
TACTICS_TEMPERATURE = 0.7
NARRATIVE_TEMPERATURE = 0.7
LLM_TIMEOUT = 15.0             # Max seconds for LLM calls