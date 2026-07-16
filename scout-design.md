基于 LangChain、LangGraph 和 MCP 的多智能体足球球探系统，模拟职业俱乐部球探部门完成球员搜索、战术适配分析、转会风险评估与球探报告生成。系统结合 RAG 检索、长期 Memory、Tool Calling 和多 Agent Debate 机制，实现面向转会决策的可解释推荐。后端基于 Golang 生态 Gin 实现，AI Agent 层基于 Python 生态 LangGraph、LangChain 实现，前端基于 Next.js 实现。

细节说明：
1. 使用 LangGraph 构建多 Agent 协作工作流，设计 7 个专业 Agent（总球探、数据球探、战术分析师、财务顾问、风险分析师、潜
   力评估师、报告生成 Agent）并行评估候选球员，并通过 Agent Debate 机制对分歧结论进行多轮讨论。
2. 基于 RAG 检索增强生成，构建球员资料、战术知识、转会新闻、伤病报告等多 Collection 向量库，支持对结构化球员数据与非
   结构化球探报告与新闻的混合检索与 Rerank 重排序。
3. 设计用户偏好、俱乐部画像、历史推荐结果、用户反馈四层 Memory 机制，实现跨会话的个性化推荐与长期记忆，支持基于反馈
   动态调整推荐策略。
4. 通过 Tool Calling 接入球员搜索、进阶数据查询、转会估值、伤病记录、相似球员查找等外部工具，实现 Agent 对多数据源的自
   主调用与调度。
5. 封装 MCP Server，向外暴露球员搜索、分析、对比、推荐和报告生成等标准化工具接口，支持客户端直接调用。
6. Go 后端负责用户认证、结构化数据管理与任务调度，通过 HTTP/gRPC 调用 Python Agent Service 执行 LangGraph 工作流，实现
   工程层与 AI 层的解耦。


