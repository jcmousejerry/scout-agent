"""MCP Server exposing role-specific football scout web search tools.

Each tool wraps the Bailian (Alibaba Cloud) web search API with a role-specific
system prompt, enabling agents to search the web from their unique perspective.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scout_tools import (
    search_data_analyst, search_tactical_analyst,
    search_financial_advisor, search_injury_risk_analyst,
    search_potential_evaluator, general_web_search,
    AGENT_NAMES_CN, AGENT_NAMES_EN,
)

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


TOOL_DEFINITIONS = [
    {
        "name": "search_data_analyst",
        "description": f"以{AGENT_NAMES_CN['data_analyst']}({AGENT_NAMES_EN['data_analyst']})的角色搜索球员统计数据相关信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询，如'姆巴佩 2024赛季 进球 助攻 射门转化率'"},
            },
            "required": ["query"],
        },
        "handler": search_data_analyst,
    },
    {
        "name": "search_tactical_analyst",
        "description": f"以{AGENT_NAMES_CN['tactical_analyst']}({AGENT_NAMES_EN['tactical_analyst']})的角色搜索球员战术适配性相关信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询，如'贝林厄姆 战术特点 最佳位置 阵型适配'"},
            },
            "required": ["query"],
        },
        "handler": search_tactical_analyst,
    },
    {
        "name": "search_financial_advisor",
        "description": f"以{AGENT_NAMES_CN['financial_advisor']}({AGENT_NAMES_EN['financial_advisor']})的角色搜索球员转会估值和经济信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询，如'哈兰德 转会估值 身价 德转 合同'"},
            },
            "required": ["query"],
        },
        "handler": search_financial_advisor,
    },
    {
        "name": "search_injury_risk_analyst",
        "description": f"以{AGENT_NAMES_CN['injury_risk_analyst']}({AGENT_NAMES_EN['injury_risk_analyst']})的角色搜索球员伤病风险相关信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询，如'内马尔 伤病历史 2024 出勤率'"},
            },
            "required": ["query"],
        },
        "handler": search_injury_risk_analyst,
    },
    {
        "name": "search_potential_evaluator",
        "description": f"以{AGENT_NAMES_CN['potential_evaluator']}({AGENT_NAMES_EN['potential_evaluator']})的角色搜索球员潜力评估相关信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询，如'亚马尔 潜力评估 成长前景 未来发展'"},
            },
            "required": ["query"],
        },
        "handler": search_potential_evaluator,
    },
    {
        "name": "search_general",
        "description": "通用足球信息搜索，不限定角色视角",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询"},
            },
            "required": ["query"],
        },
        "handler": general_web_search,
    },
]

TOOL_NAME_MAP = {t["name"]: t for t in TOOL_DEFINITIONS}


def run_mcp_server():
    """Run MCP server via stdio transport."""
    if not HAS_MCP:
        print("MCP package not installed. Install with: pip install mcp", file=sys.stderr)
        sys.exit(1)

    app = Server("scout-agent-tools")

    @app.list_tools()
    async def list_tools():
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOL_DEFINITIONS
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list:
        tool = TOOL_NAME_MAP.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        query = arguments.get("query", "")
        result = tool["handler"](query)
        return [TextContent(type="text", text=result)]

    import asyncio
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())

    asyncio.run(main())


if __name__ == "__main__":
    run_mcp_server()
