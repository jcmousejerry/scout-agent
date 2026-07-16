-- ============================================================
-- Scout Agent 数据库建表语句
-- 适用数据库: MySQL 8.0+
-- ============================================================

CREATE DATABASE IF NOT EXISTS scout_agent
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE scout_agent;

-- -----------------------------------------------------------
-- 1. 用户表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,  -- 用户唯一标识，自增主键
    username      VARCHAR(100) NOT NULL UNIQUE,     -- 登录用户名，全局唯一
    password_hash VARCHAR(255) NOT NULL,            -- 密码的 bcrypt 哈希值，不存明文
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 注册时间
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 2. 用户偏好记忆表
-- 以自然语言文本存储，每次用户完成澄清后更新，
-- 后续对话可读取作为 LLM 上下文。
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_preferences (
    id         INT AUTO_INCREMENT PRIMARY KEY,  -- 记录唯一标识，自增主键
    user_id    INT NOT NULL,                     -- 所属用户 ID，关联 users.id
    pref_key   VARCHAR(255) NOT NULL,            -- 偏好键名（固定值 'memory'，预留扩展）
    pref_value TEXT NOT NULL,                    -- 偏好值（自然语言段落，描述用户战术/引援/年龄偏好）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,          -- 首次创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- 最后更新时间，每次修改自动更新
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE KEY uk_user_pref (user_id, pref_key)  -- 每个用户每种偏好键只能有一条记录
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 3. 查询历史表
-- 保存每次完整分析会话的最终结果记录，用于前端【历史】功能展示。
-- 仅在分析完成（收到 event: result）后写入，过程中不写入此表。
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS query_history (
    id                   INT AUTO_INCREMENT PRIMARY KEY,  -- 记录唯一标识，自增主键
    user_id              INT NOT NULL,                     -- 发起查询的用户 ID，关联 users.id
    query                TEXT NOT NULL,                    -- 用户输入的原始查询文本（如"找一名速度快的前锋"）
    report               LONGTEXT NULL,                    -- 最终球探报告（Markdown 格式，含推荐理由和分析）
    retrieved_count      INT DEFAULT 0,                    -- RAG 检索到的知识库条目数
    candidates_json      LONGTEXT NULL,                    -- 5 名候选球员的 JSON 数组（含姓名、位置、球队、年龄、评分理由、关键优势）
    debate_json          LONGTEXT NULL,                    -- 完整多轮辩论消息的 JSON 数组（每条含发言人、角色、内容、轮次）
    final_candidate_json LONGTEXT NULL,                    -- 最终推荐球员的 JSON 对象（含详细推荐分析）
    eliminated_json      LONGTEXT NULL,                    -- 被淘汰球员姓名列表的 JSON 数组（如 ["张三","李四"]）
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 记录创建时间（即分析完成时间）
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 索引：按用户查询历史（倒序），加速前端历史列表加载
CREATE INDEX idx_query_history_user ON query_history(user_id, created_at DESC);

-- -----------------------------------------------------------
-- 4. 分析会话表（递增持久化）
-- 在复杂分析（/api/scout/analyze）过程中，实时保存每个阶段的中间状态。
-- 分析开始时创建记录（status='running'），
-- 候选球员生成、辩论完成时逐步更新，
-- 最终结果到达后写入全部字段并标记 status='completed'。
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id                   INT AUTO_INCREMENT PRIMARY KEY,  -- 记录唯一标识，自增主键
    user_id              INT NOT NULL,                     -- 发起分析的用户 ID，关联 users.id
    session_id           VARCHAR(64) NOT NULL UNIQUE,      -- 会话唯一标识（由 ai_agent 生成，用于关联澄清阶段和分析阶段）
    original_query       TEXT NOT NULL,                    -- 用户原始查询文本（与 query_history.query 相同）
    candidates_json      LONGTEXT NULL,                    -- 当前候选球员列表的 JSON 数组（分析过程中逐步更新，最终为 5 人）
    debate_json          LONGTEXT NULL,                    -- 当前辩论消息的 JSON 数组（每轮辩论完成后追加更新）
    final_candidate_json LONGTEXT NULL,                    -- 最终推荐球员的 JSON 对象（仅在收到 event: result 时写入）
    final_report         LONGTEXT NULL,                    -- 最终球探报告（Markdown，仅在收到 event: result 时写入）
    eliminated_json      LONGTEXT NULL,                    -- 被淘汰球员姓名列表的 JSON 数组（每轮淘汰后实时更新）
    status               VARCHAR(20) DEFAULT 'running',    -- 会话状态：running（处理中）/ completed（已完成）
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,          -- 分析开始时间
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- 最后更新时间（每次 SSE 事件更新时自动刷新）
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;