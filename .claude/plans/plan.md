# Context

该文件记录了在上一个会话中我已经修复完以下问题的基础上，继续处理的新议题：

**已有修复内容**（无需再改）：
1. 战术冷却时间太长 → cooldown 值改为 3-8 比赛分钟
2. 暂停/继续按钮无反馈 → 前端状态 + toast + 显式禁用/已暂停徽章
3. Ajax 客队无球员 → 补齐 Ajax / Benfica / Porto / Celtic 的球员数据
4. 半场叙事崩溃 → 修复 `{'展望' if ...}` 内联条件导致 KeyError

**本次新议题**：
1. 用户（主队）和 AI（客队）的战术调整应在比赛事件列表中可见
2. 新比赛页面增加历史比赛入口 + 可查看历史比赛的完整详情

# Plan: 战术调整事件 + 历史比赛记录

## 第一部分：战术调整事件

### 后端改动

**1. `match_sim/prompts/event_prompts.py` — 修复 build_opponent_prompt**

当前的 `build_opponent_prompt` 有两个 bug：
- 内部 `from .event_prompts import build_opponent_adjustments` 导入不存在的函数
- 未设置 `ctx["opponent_adjustments"]` 和 team-relative 上下文键，导致 `.format()` → KeyError
- 结果：对手 AI 的战术决策调用一直静默崩溃，从未生效

修复方式：将 `build_opponent_prompt` 重写为包含完整上下文，参照 `build_opponent_prompt_full` 的逻辑（或直接让 `build_opponent_prompt` 调用 `_build_opponent_adjustments` 并设置 team-relative 上下文）。
删除 `build_opponent_prompt_full`（重复函数）。

**2. `match_sim/match_engine.py` — _apply_tactical_adjustment 中生成事件**

在 `_apply_tactical_adjustment()` 末尾，根据调整类型创建 `MatchEvent`，`event_type="tactical_adjustment"`，描述包含：
- 用户调整：`"主队 战术调整：{reason}"`
- AI 调整：`"客队 战术调整：{reason}"`
- 替换/变阵包含详细说明

然后 `append` 到 `self.state.events`。由于引擎循环中 `_run_half` 的步骤 1-2 会生成事件并追加，而战术调整是在步骤 3-4 中应用的，需要确保调整生成的事件也正确持久化和推送。

实现方式：在 `_apply_tactical_adjustment` 中创建 `MatchEvent` 并 append 到 state.events。

### 前端改动

**3. `frontend/pages/match-sim/[session_id].tsx` — EventFeed emoji 映射**

`eventEmoji` 函数增加 `tactical_adjustment` → "📋"（或类似图标）。

## 第二部分：历史比赛入口 + 回看详情

### Go 后端改动

**4. `backend/handlers/match_data.go` — 新增 `MatchDataListMatches`**

查询 `match_sim_matches` 表，按 `finished_at DESC` 排序返回已结束比赛列表。返回字段：`session_id`, `home_team_name`, `away_team_name`, `home_score`, `away_score`, `match_status`, `match_minute`, `created_at`, `finished_at`。

无用户认证（与 match-sim 现有策略一致，公开数据）。

**5. `backend/handlers/match_data.go` — 新增 `MatchDataGetMatchDetail`**

按 `session_id` 查询 `match_sim_matches` 表，返回完整行数据（含 events_json / tactics_json / stats_json 等解析后的结构化数据）。

返回结构：
```json
{
  "match": {
    "session_id": "...",
    "home_team_name": "...", "away_team_name": "...",
    "home_score": 0, "away_score": 0,
    "match_status": "finished", "match_minute": 90,
    "home_formation": "...", "away_formation": "...",
    "stats": { "home_shots": 0, ... },
    "events": [ ... ],  // 从 events_json 解析
    "tactical_adjustments": [ ... ],  // 从 tactics_json 解析
    "home_substitutions_used": 0, "away_substitutions_used": 0,
    "home_tactical_cooldown": 0, "away_tactical_cooldown": 0,
    "home_attack_modifier": 0, "home_defense_modifier": 0,
    "away_attack_modifier": 0, "away_defense_modifier": 0,
    "home_morale": 0, "away_morale": 0,
    "match_tempo": "balanced",
    "active_players_home": [], "active_players_away": [],
    "bench_players_home": [], "bench_players_away": [],
    "created_at": "...", "finished_at": "..."
  }
}
```

注意：已结束的比赛没有活跃的 `MatchEngine` 对象，所以比赛快照无法从 Python `_get_state_snapshot()` 获取。历史数据存储在 `events_json` / `tactics_json` / `stats_json` 中，但没有球员数据（`active_players_home` / `bench_players_away` 等）。有两种方案：

**方案 A**：在存储 `events_json` 时，也用 JSON 存储阵容快照。需要修改 `update_match_state` 和 `_save_state()`，额外传入阵容 JSON。
**方案 B**：详情页只展示能展示的数据（比分、统计、事件、战术调整），球员阵容直接从 `match_sim_players` 按 `home_team_id` / `away_team_id` 读取开赛时的阵容（但无法区分首发和替补在比赛中的变化）。
**方案 C**：在 `match_sim_matches` 加 `lineup_json` 列，存储比赛过程中每次保存时的阵容。

方案 C 改动最小、数据最准。在现有 `update_match_state` 的 PUT 请求中增加 `lineup_json` 字段，写入 `match_sim_matches.lineup_json`。Go 的 schema 中加这个列。Python 的 `_get_state_snapshot()` 和 DB 的 `update_match_state` 都传这份数据。

选方案 C，因为：
- 改动集中在已有热路径上（每个 tick 已经写库）
- 不需要专门为详情存新表
- 数据真实反映比赛过程中的阵容（含换人后的变化）

**6. Go Schema 升级**

`backend/database/db.go` 的 `createTables` 中，`match_sim_matches` 建表改为包含 `lineup_json LONGTEXT NULL` 列。

**7. Python `database.py` — update_match_state 增加 lineup_json**

写入 `body["lineup_json"] = ...`。

**8. Python `match_engine.py` — _save_state 携带阵容**

在 `_save_state()` 调用 `update_match_state()` 前构建 `lineup_json`。

**9. 注册路由**

`backend/main.go` 中注册：
```
data.GET("/matches", handlers.MatchDataListMatches)
data.GET("/match/:session/detail", handlers.MatchDataGetMatchDetail)
```

### 前端改动

**10. `frontend/pages/match-sim/index.tsx` — 增加历史入口**

在页面顶部 header 或 VS Banner 下方增加一个"📋 历史记录"按钮/链接，点击跳转到 `/match-sim/history`。

**11. `frontend/pages/match-sim/history.tsx` — 新页面：历史比赛列表**

从 `API_BASE + "/match-sim/matches"`（代理到 Go `/api/match-data/matches`）获取列表。每行显示：
- 日期时间（created_at）
- 主队名 vs 客队名
- 比分
- 状态（已结束/已停止）
- 点击进入 `/match-sim/review/{session_id}` 详情

**12. `frontend/pages/match-sim/review/[session_id].tsx` — 新页面：比赛详情回看**

从 `API_BASE + "/match-sim/match/{session}/detail"`（代理到 Go `/api/match-data/match/{session}/detail`）获取完整数据。展示：
- Scoreboard（复用组件，传 `finished=true`）
- Tabs: 事件 / 数据 / 阵容
- EventFeed
- StatsPanel
- LineupPanel
- 无暂停/继续/战术按钮
- 无 SSE
- 返回按钮

组件复用策略：将 `[session_id].tsx` 中的 `Scoreboard`, `EventFeed`, `StatsPanel`, `LineupPanel`, `TeamLineup`, `ModifierBar`, `stateLabel` 等组件提取到 `frontend/components/match-sim-components.tsx`，两个页面都引用。或者更简单：`review/[session_id].tsx` 直接从 `[session_id].tsx` import 这些内部组件。

## 修改文件清单

| 文件 | 改动 |
|---|---|
| `match_sim/prompts/event_prompts.py` | 修复 `build_opponent_prompt`（补全上下文 + 导入修复）；删除 `build_opponent_prompt_full` |
| `match_sim/match_engine.py` | `_apply_tactical_adjustment` 中创建 MatchEvent 追加到 events |
| `backend/database/db.go` | match_sim_matches 表增加 `lineup_json` 列 |
| `backend/handlers/match_data.go` | 新增 `MatchDataListMatches`、`MatchDataGetMatchDetail` |
| `backend/main.go` | 注册新路由 |
| `match_sim/database.py` | `update_match_state` 增加 lineup_json |
| `match_sim/match_engine.py` | `_save_state` 中构建 lineup_json |
| `frontend/pages/match-sim/[session_id].tsx` | eventEmoji 加 tactical_adjustment 映射 |
| `frontend/pages/match-sim/index.tsx` | 加历史入口按钮 |
| `frontend/pages/match-sim/history.tsx` | 新页面 |
| `frontend/pages/match-sim/review/[session_id].tsx` | 新页面 |

## 验证方法

1. 重启所有服务
2. 创建比赛，进行战术调整 → 事件列表中应出现"📋 主队 战术调整：加强进攻"
3. 等待客队 AI 响应（约 3 ticks 后）→ 事件列表中应出现"📋 客队 AI 战术调整：加强防守"
4. 让比赛踢到完场
5. 回到 /match-sim 页面 → 能看到"📋 历史记录"入口
6. 点击进入历史列表 → 能看到刚结束的比赛
7. 点击进入详情回看 → 计分板、阵容、数据、事件完整展示
