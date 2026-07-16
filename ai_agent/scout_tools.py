import json
from openai import OpenAI
from config import API_KEY, BASE_URL_CHAT, LLM_MODEL

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL_CHAT,
    timeout=300.0,
    max_retries=2,
)

ROLE_SYSTEM_PROMPTS = {
    "data_analyst": """你是一名职业足球数据分析师。你的专长是分析球员的统计数据，包括：
- 进球、助攻、传球成功率、射门转化率等进攻数据
- 抢断、拦截、解围、对抗成功率等防守数据
- 跑动距离、冲刺次数、传球次数等体能和活动数据
请基于搜索到的数据给出定量分析，用数据说话。""",

    "tactical_analyst": """你是一名职业足球战术分析师。你的专长是分析球员的战术适配性，包括：
- 球员在不同阵型（4-3-3、3-5-2、4-4-2等）中的表现
- 球员的战术执行能力、位置感和比赛阅读能力
- 球员与潜在球队现有体系的兼容性
请结合搜索到的战术信息给出分析。""",

    "financial_advisor": """你是一名职业足球财务顾问。你的专长是评估球员的转会价值和经济可行性，包括：
- 球员当前的转会市场估值和合同情况
- 转会费与球员实际表现的性价比分析
- 球员的工资要求与潜在商业价值
- 转会操作对球队薪资结构的潜在影响
请搜索最新的转会市场信息进行分析。""",

    "injury_risk_analyst": """你是一名职业足球伤病风险分析师。你的专长是评估球员的伤病风险和健康状况，包括：
- 球员的历史伤病记录和恢复情况
- 球员当前的身体状况和出勤率
- 基于球员年龄和踢球风格的伤病风险预测
- 球员的医疗记录和康复历史
请搜索球员的伤病相关信息进行分析。""",

    "potential_evaluator": """你是一名职业足球潜力评估分析师。你的专长是评估球员的成长潜力和未来发展，包括：
- 球员的年龄与发展阶段评估
- 技术、身体、心理等多维度潜力评估
- 球员的学习能力和适应性
- 球员在高水平联赛中的发展前景预测
请搜索球员的成长轨迹和潜力评价进行分析。""",

    "chief_scout": """你是一名职业足球俱乐部的总球探（球探主管）。你的职责是综合所有专家分析师的意见，做出最终的球员去留决定。
- 你需要仔细权衡战术分析师、财务顾问、伤病风险分析师、潜力评估分析师的各方观点
- 你的决定必须基于综合考量，而非单一维度
- 你需要明确指出本轮淘汰哪一名候选球员，并给出充分、具体的理由
- 你的发言风格应当权威、果断，像一位经验丰富的球探主管""",
}

AGENT_NAMES_CN = {
    "data_analyst": "数据分析师",
    "tactical_analyst": "战术分析师",
    "financial_advisor": "财务顾问",
    "injury_risk_analyst": "伤病风险分析师",
    "potential_evaluator": "潜力评估分析师",
    "chief_scout": "总球探",
}

AGENT_NAMES_EN = {
    "data_analyst": "Data Analyst",
    "tactical_analyst": "Tactical Analyst",
    "financial_advisor": "Financial Advisor",
    "injury_risk_analyst": "Injury Risk Analyst",
    "potential_evaluator": "Potential Evaluator",
}


def search_as_role(role: str, query: str) -> str:
    messages = [
        {"role": "system", "content": ROLE_SYSTEM_PROMPTS.get(role, "")},
        {"role": "user", "content": f"请搜索以下信息并给出专业分析：{query}"},
    ]
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.7,
        extra_body={"enable_search": True},
    )
    return resp.choices[0].message.content


def search_data_analyst(query: str) -> str:
    return search_as_role("data_analyst", query)


def search_tactical_analyst(query: str) -> str:
    return search_as_role("tactical_analyst", query)


def search_financial_advisor(query: str) -> str:
    return search_as_role("financial_advisor", query)


def search_injury_risk_analyst(query: str) -> str:
    return search_as_role("injury_risk_analyst", query)


def search_potential_evaluator(query: str) -> str:
    return search_as_role("potential_evaluator", query)


def general_web_search(query: str) -> str:
    messages = [
        {"role": "system", "content": "你是一名专业的足球球探助手，请搜索最新的足球相关信息。"},
        {"role": "user", "content": query},
    ]
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.7,
        extra_body={"enable_search": True},
    )
    return resp.choices[0].message.content


AGENT_TOOL_MAP = {
    "data_analyst": search_data_analyst,
    "tactical_analyst": search_tactical_analyst,
    "financial_advisor": search_financial_advisor,
    "injury_risk_analyst": search_injury_risk_analyst,
    "potential_evaluator": search_potential_evaluator,
}
