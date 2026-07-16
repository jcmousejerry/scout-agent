import json
import logging
import uuid
import random
import string
from typing import TypedDict, Annotated, Sequence, Literal, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from llm_client import chat
from scout_tools import ROLE_SYSTEM_PROMPTS, AGENT_TOOL_MAP, AGENT_NAMES_CN
from rag.retriever import retrieve as rag_retrieve

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("workflow")

AGENT_ROLES = list(AGENT_TOOL_MAP.keys())
DEBATE_AGENTS = ["tactical_analyst", "financial_advisor", "injury_risk_analyst", "potential_evaluator"]
CHIEF_SCOUT = "chief_scout"

MAX_DEBATE_ROUNDS = 10


class ScoutState(TypedDict):
    session_id: str
    original_query: str
    clarified_query: str
    phase: str
    candidate_count: int

    questions: list
    answers: dict
    question_round: int
    clarification_done: bool

    retrieved_docs: list
    retrieved_count: int

    candidates: list
    eliminated: list
    debate_messages: list
    debate_round: int
    debate_done: bool
    last_speaker: Optional[str]
    final_candidate: Optional[dict]

    final_report: str
    error: Optional[str]
    preferences_memory: Optional[str]


def create_initial_state(query: str, candidate_count: int = 3) -> ScoutState:
    return {
        "session_id": uuid.uuid4().hex[:12],
        "original_query": query,
        "clarified_query": query,
        "phase": "clarify",
        "candidate_count": max(2, min(candidate_count, 5)),
        "questions": [],
        "answers": {},
        "question_round": 0,
        "clarification_done": False,
        "retrieved_docs": [],
        "retrieved_count": 0,
        "candidates": [],
        "eliminated": [],
        "debate_messages": [],
        "debate_round": 0,
        "debate_done": False,
        "last_speaker": None,
        "final_candidate": None,
        "final_report": "",
        "error": None,
        "preferences_memory": None,
    }


MAX_CLARIFY_ROUNDS = 2


def generate_clarify_questions(state: ScoutState) -> ScoutState:
    round_num = state["question_round"] + 1
    logger.info(f"Generating clarification questions (round {round_num})")

    if round_num > MAX_CLARIFY_ROUNDS:
        logger.info("Max clarify rounds reached, forcing done")
        return {**state, "questions": [], "clarification_done": True}

    prev = state["answers"]
    prev_context = ""
    if prev:
        prev_context = "用户已提供的答案：\n" + "\n".join(f"- {k}: {v}" for k, v in prev.items())

    prompt = f"""你是一名足球球探需求分析师。请根据用户的球探需求，生成有针对性的澄清问题。

用户初始需求：{state['original_query']}

{prev_context}

重要规则：
- 你最多只能生成1轮问题（最多3个选择题）
- 这是第{round_num}轮提问，如果已经收集了足够信息，必须设置clarification_done=true
- 如果这是第2轮提问，你必须设置clarification_done=true，不再生成新问题
- 问题应当多样化、有创意，从不同维度（战术、财务、年龄、合同、风格等）切入，避免套路化

请以JSON格式返回：
{{
    "clarification_done": true/false,
    "questions": [
        {{
            "id": "q1",
            "question": "问题描述",
            "options": [
                {{"label": "选项A", "value": "option_a"}},
                {{"label": "选项B", "value": "option_b"}}
            ]
        }}
    ]
}}

如果clarification_done=true，则questions数组为空。"""
    nonce = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    messages = [
        {"role": "system", "content": f"你是一个帮助球探系统明确用户需求的助手。每次只生成一轮问题，收集完信息就立即结束。每次提问应从不同角度切入，保持多样性。（会话标识：{nonce}）"},
        {"role": "user", "content": prompt},
    ]
    resp = chat(messages, temperature=0.9)
    content = resp.choices[0].message.content.strip()
    content = content.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse LLM response as JSON: {content[:200]}")
        data = {"clarification_done": True, "questions": []}
    return {
        **state,
        "questions": data.get("questions", []),
        "clarification_done": data.get("clarification_done", round_num >= MAX_CLARIFY_ROUNDS),
    }


def process_answers(state: ScoutState, new_answers: dict) -> ScoutState:
    merged = {**state["answers"], **new_answers}
    return {
        **state,
        "answers": merged,
        "question_round": state["question_round"] + 1,
    }


def finalize_clarification(state: ScoutState) -> ScoutState:
    combined = state["original_query"]
    if state["answers"]:
        combined += "\n用户详细需求：\n" + "\n".join(f"- {k}: {v}" for k, v in state["answers"].items())
    return {
        **state,
        "clarified_query": combined,
        "phase": "retrieve",
    }


def retrieve_knowledge(state: ScoutState) -> ScoutState:
    logger.info("Retrieving knowledge from RAG...")
    try:
        docs = rag_retrieve(state["clarified_query"], top_k_raw=20, top_k_rerank=10)
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        docs = []
    return {
        **state,
        "retrieved_docs": docs,
        "retrieved_count": len(docs),
        "phase": "candidates",
    }


CANDIDATE_SCHEMA_HINT = """{
    "candidates": [
        {
            "name": "球员姓名",
            "position": "位置",
            "team": "当前球队",
            "age": 年龄,
            "reasoning": "为什么推荐该球员",
            "key_strengths": ["优势1", "优势2", "优势3"]
        }
    ]
}"""


def _parse_candidate(content: str) -> Optional[dict]:
    """解析LLM返回，兼容 ```json 包裹与普通字符串包裹。"""
    content = (content or "").strip()
    content = content.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                return None
        else:
            return None
    cands = data.get("candidates") if isinstance(data, dict) else None
    if isinstance(cands, list) and cands:
        c = cands[0]
        if isinstance(c, dict) and c.get("name"):
            c.setdefault("position", "未知")
            c.setdefault("team", "未知")
            c.setdefault("age", 0)
            c.setdefault("reasoning", "")
            c.setdefault("key_strengths", [])
            return c
    if isinstance(data, dict) and data.get("name"):
        return data
    return None


def _fallback_candidate(index: int) -> dict:
    return {
        "name": f"待确定候选球员{index + 1}",
        "position": "未知", "team": "未知", "age": 0,
        "reasoning": "LLM返回格式异常，已使用占位候选",
        "key_strengths": [],
    }


def generate_candidates_stream(state: ScoutState):
    """逐个生成候选球员，每生成一名就yield一次（含候选字典与"已生成数量"）。"""
    context = "\n\n".join([
        f"[相关度:{d['relevance_score']:.3f}]\n{d['text']}"
        for d in state["retrieved_docs"][:10]
    ]) if state["retrieved_docs"] else "（无相关检索结果）"

    candidates: list = []
    total = state.get("candidate_count", 3)
    for i in range(total):
        already = "\n".join(
            f"- {c['name']} ({c.get('position', '')}, {c.get('team', '')})"
            for c in candidates
        ) if candidates else "（暂无）"

        memory_hint = ""
        if state.get("preferences_memory"):
            memory_hint = f"\n用户历史偏好（请优先考虑）：\n{state['preferences_memory']}\n"

        prompt = f"""你是一名职业足球球探。根据以下用户需求，**仅推荐1名候选球员**（这是第 {i + 1}/{total} 名）。

用户需求：
{state['clarified_query']}

足球理论与战术知识参考（RAG检索结果）：
{context}{memory_hint}
已经选出的候选球员（不要重复，请推荐不同位置/类型的球员）：
{already}

要求：
- 请调用联网搜索获取这名球员的最新信息
- 推荐一名尚未出现在上述列表中的真实球员
- 返回纯JSON，不要附加任何解释文字
- 【重要】禁止使用任何英文术语、标签或代码标识符（如 progressive_pivot、high_fee_long_contract、veteran_leader_28_plus、#8、B2B 等），reasoning 和 key_strengths 中的内容必须全部使用中文自然语言

JSON格式：
{CANDIDATE_SCHEMA_HINT}"""
        messages = [
            {"role": "system", "content": "你是一名专业的足球球探，需要基于数据和搜索推荐球员。只返回 JSON。"},
            {"role": "user", "content": prompt},
        ]
        try:
            resp = chat(messages, temperature=0.7, extra_body={"enable_search": True}, timeout=300.0)
            content = resp.choices[0].message.content
            cand = _parse_candidate(content)
            if not cand:
                logger.warning(f"Failed to parse candidate #{i + 1}: {content[:200]}")
                cand = _fallback_candidate(i)
        except Exception as e:
            logger.error(f"generate_candidates_stream #{i + 1} failed: {e}")
            cand = _fallback_candidate(i)

        candidates.append(cand)
        yield {
            "candidate": cand,
            "index": i,
            "total": total,
            "candidates_so_far": list(candidates),
        }

    new_state = {**state, "candidates": candidates, "phase": "debate"}
    yield {"final_state": new_state}


def generate_candidates(state: ScoutState) -> ScoutState:
    """一次性生成候选球员（保留作为单步接口；流式版本见 generate_candidates_stream）。"""
    total = state.get("candidate_count", 3)
    logger.info(f"Generating {total} candidate players...")
    final = None
    for event in generate_candidates_stream(state):
        if "final_state" in event:
            final = event["final_state"]
    return final if final else {**state, "candidates": [], "phase": "debate"}


def _build_candidates_info(candidates, eliminated):
    active = [c for c in candidates if c["name"] not in eliminated]
    return "\n".join([
        f"- {c['name']} - {c['position']} - {c['team']} - {c.get('age', '?')}岁\n  推荐理由：{c.get('reasoning', '无')}\n  优势：{', '.join(c.get('key_strengths', []))}"
        for c in active
    ])


def _build_debate_history(messages, limit=8):
    if not messages:
        return "（尚无讨论内容）"
    return "\n".join([
        f"[{AGENT_NAMES_CN.get(m.get('speaker'), m.get('speaker', '未知'))}]: {m['content'][:300]}"
        for m in messages[-limit:]
    ])


def _build_agent_messages(role: str, state: ScoutState) -> list:
    candidates_info = _build_candidates_info(state["candidates"], state["eliminated"])
    debate_history = _build_debate_history(state["debate_messages"])

    system_prompt = ROLE_SYSTEM_PROMPTS.get(role, "") + "\n\n请在分析过程中，如果信息不足，可以调用联网搜索工具获取最新信息。"

    # 注入用户偏好记忆（自然语言段落）
    memory = state.get("preferences_memory")
    if memory:
        system_prompt += f"\n\n## 用户偏好记忆\n{memory}\n请参考以上用户历史偏好，在分析中优先考虑符合用户偏好的球员。"

    # 严禁输出英文术语
    system_prompt += "\n\n【重要输出规范】必须全部使用中文自然语言输出，禁止出现任何英文术语、标签或代码标识符。例如：禁止出现 progressive_pivot、high_fee_long_contract、veteran_leader_28_plus 等英文标识；禁止出现 #8、B2B 等英文缩写；请使用完整的中文语句描述战术角色和球员特征。"

    prompt = f"""当前候选球员：
{candidates_info}

最近的讨论内容：
{debate_history}

你正在参加一场球探团队会议，讨论为球队推荐哪位球员。请基于你的专业领域给出分析意见。
- 你可以同意或反驳其他专家的观点
- 请针对当前仍在候选名单中的球员进行具体分析
- 给出明确的倾向性意见（更推荐谁、不建议选谁）
- 发言控制在200-400字，言简意赅、有理有据"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    search_fn = AGENT_TOOL_MAP.get(role)
    if search_fn:
        try:
            search_result = search_fn(f"请搜索关于以下候选球员的信息以辅助分析：\n\n候选球员：{candidates_info}")
            messages.append({"role": "assistant", "content": f"搜索到的相关信息：\n{search_result[:1500]}"})
            messages.append({"role": "user", "content": "请基于以上搜索信息和你的专业知识给出分析。"})
        except Exception as e:
            logger.error(f"Search call failed for {role}: {e}")
    return messages


def agent_speak(role: str, state: ScoutState) -> str:
    try:
        messages = _build_agent_messages(role, state)
        resp = chat(messages, temperature=0.7)
        return resp.choices[0].message.content
    except Exception as e:
        logger.error(f"Agent call failed for {role}: {e}")
        return f"（{AGENT_NAMES_CN.get(role, role)}暂时无法完成分析。错误：{str(e)}）"


def _build_chief_eliminate_messages(state: ScoutState) -> tuple:
    candidates_info = _build_candidates_info(state["candidates"], state["eliminated"])
    debate_history = _build_debate_history(state["debate_messages"], limit=20)

    active = [c for c in state["candidates"] if c["name"] not in state["eliminated"]]
    active_names = [c["name"] for c in active]

    memory_hint = ""
    if state.get("preferences_memory"):
        memory_hint = f"\n用户历史偏好（请优先考虑）：\n{state['preferences_memory']}\n"

    prompt = f"""你是一名总球探，正在主持球探团队会议。本轮讨论中，各位专家已经发表了各自的意见。{memory_hint}

当前仍在候选名单中的球员：
{candidates_info}

本轮各专家的讨论意见：
{debate_history}

请你综合所有专家的分析意见，做出本轮的淘汰决定。

重要规则：
- 你必须从当前候选名单中淘汰且仅淘汰1名球员
- 候选球员姓名必须严格从以下列表中选择：{active_names}
- 你需要引用各位专家的具体观点来支撑你的决定
- 如果专家意见有分歧，你需要做出权威的权衡判断

【重要输出规范】eliminate_reason 和 round_summary 必须全部使用中文自然语言输出，禁止出现任何英文术语、标签或代码标识符（如 progressive_pivot、high_fee_long_contract、veteran_leader_28_plus 等）。

请以JSON格式返回：
{{
    "eliminate_candidate": "要淘汰的球员姓名（必须从候选列表中选择）",
    "eliminate_reason": "详细的淘汰理由，需引用各专家观点",
    "round_summary": "本轮讨论小结，概括各位专家的主要观点和你的决定"
}}"""
    messages = [
        {"role": "system", "content": ROLE_SYSTEM_PROMPTS.get("chief_scout", "你是总球探。")},
        {"role": "user", "content": prompt},
    ]
    return messages, active_names


def _parse_chief_decision(content: str, active_names: list) -> dict:
    content = content.strip().replace("```json", "").replace("```", "").strip()
    try:
        decision = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse chief_scout JSON: {content[:200]}")
        decision = {
            "eliminate_candidate": active_names[0] if active_names else "",
            "eliminate_reason": "综合评估后决定淘汰。",
            "round_summary": "本轮讨论结束，综合各专家意见做出淘汰决定。",
        }
    if decision.get("eliminate_candidate") not in active_names:
        decision["eliminate_candidate"] = active_names[0] if active_names else ""
    return decision


def chief_scout_eliminate(state: ScoutState) -> dict:
    messages, active_names = _build_chief_eliminate_messages(state)
    resp = chat(messages, temperature=0.5)
    return _parse_chief_decision(resp.choices[0].message.content, active_names)


def generate_final_report(state: ScoutState) -> ScoutState:
    logger.info("Generating final report...")
    final = state.get("final_candidate")
    if not final:
        return {**state, "final_report": "未能确定最终的推荐球员。"}

    all_debate = "\n\n".join([
        f"### {m.get('role', m.get('speaker', '未知'))} ({m.get('type', '讨论')})\n{m['content']}"
        for m in state["debate_messages"]
    ])

    eliminated_info = []
    for e_name in state["eliminated"]:
        cand = next((c for c in state["candidates"] if c["name"] == e_name), None)
        if cand:
            eliminated_info.append(f"- {cand['name']} ({cand['position']}, {cand['team']})")

    prompt = f"""你是一名职业足球球探主管。经过多轮专家辩论，已经确定了最终推荐球员。

用户需求：{state['clarified_query']}

最终推荐球员：{json.dumps(final, ensure_ascii=False)}

淘汰球员：
{chr(10).join(eliminated_info)}

完整辩论过程：
{all_debate}

请生成一份完整的球探分析报告，包括：
1. 推荐球员概览（基本信息、当前表现）
2. 各专家分析摘要
3. 为什么其他候选被淘汰
4. 最终推荐理由和风险评估
5. 转会建议

【重要输出规范】必须全部使用中文自然语言输出，禁止出现任何英文术语、标签或代码标识符（如 progressive_pivot、high_fee_long_contract、veteran_leader_28_plus、#8、B2B 等）。"""
    messages = [
        {"role": "system", "content": "你是一名职业足球俱乐部的球探总监，需要汇总专家意见生成最终报告。所有输出必须使用中文自然语言，禁止使用任何英文术语或标签。"},
        {"role": "user", "content": prompt},
    ]
    resp = chat(messages, temperature=0.7)
    report = resp.choices[0].message.content
    return {**state, "final_report": report, "phase": "report"}


def _debate_round_node(state: ScoutState) -> ScoutState:
    result = {**state, "debate_round": state["debate_round"] + 1}
    for role in DEBATE_AGENTS:
        content = agent_speak(role, result)
        result["debate_messages"].append({
            "speaker": role,
            "role": AGENT_NAMES_CN.get(role, role),
            "content": content,
            "round": result["debate_round"],
            "type": "discussion",
        })
    decision = chief_scout_eliminate(result)
    target = decision.get("eliminate_candidate", "")
    if target and target not in result["eliminated"]:
        result["eliminated"].append(target)
    result["debate_messages"].append({
        "speaker": CHIEF_SCOUT,
        "role": AGENT_NAMES_CN.get(CHIEF_SCOUT, "总球探"),
        "content": f"【本轮淘汰决定】淘汰 {target}。\n理由：{decision.get('eliminate_reason', '综合评估后决定')}\n\n本轮小结：{decision.get('round_summary', '')}",
        "round": result["debate_round"],
        "type": "elimination",
    })
    active_after = [c for c in result["candidates"] if c["name"] not in result["eliminated"]]
    if len(active_after) <= 1 or result["debate_round"] >= MAX_DEBATE_ROUNDS:
        result["debate_done"] = True
        result["final_candidate"] = active_after[0] if active_after else None
    return result


def build_scout_graph():
    workflow = StateGraph(ScoutState)

    workflow.add_node("retrieve_knowledge", retrieve_knowledge)
    workflow.add_node("generate_candidates", generate_candidates)
    workflow.add_node("debate_round", _debate_round_node)
    workflow.add_node("generate_final_report", generate_final_report)

    workflow.set_entry_point("retrieve_knowledge")

    workflow.add_edge("retrieve_knowledge", "generate_candidates")
    workflow.add_edge("generate_candidates", "debate_round")

    def debate_router(state: ScoutState) -> str:
        if state.get("debate_done"):
            return "generate_final_report"
        return "debate_round"

    workflow.add_conditional_edges(
        "debate_round",
        debate_router,
        {"debate_round": "debate_round", "generate_final_report": "generate_final_report"},
    )

    workflow.add_edge("generate_final_report", END)

    return workflow.compile(checkpointer=MemorySaver())


scout_graph = build_scout_graph()
