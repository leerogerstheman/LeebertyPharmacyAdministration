# hello-agents 十六章 × LeebertyPharmacyAdministration 深化对照

> 依据 Datawhale《Hello-Agents（从零开始构建智能体）》(https://github.com/datawhalechina/hello-agents) 逐章落地。
> 实现状态：✅ 已完成 | 🔧 增强中 | 📖 文档化

| 章 | 核心方法论 | 本项目深化 | 位置 | 状态 |
|---|---|---|---|---|
| 1 初识智能体 | Agent=LLM+规划+记忆+工具；能力边界 | 智能体构成文档、双模式架构说明 | docs/agent_design.md、《README》 | ✅ |
| 2 智能体发展史 | 从符号主义到 LLM 原生智能体 | 发展脉络简史（含本项目定位） | docs/agent_design.md | ✅ |
| 3 大语言模型基础 | 熵/温度/能力边界/幻觉 | 模型选择与参数指南、防幻觉 SYSTEM 约束 | docs/agent_design.md、llm.py | ✅ |
| 4 经典范式 | ReAct / Plan-and-Solve / Reflection | 三范式引擎 + CLI/API/GUI 可切换 + adaptive 自动选择 | agent/agent_core.py、cli/gui/server | ✅ |
| 5 低代码平台 | Dify/Coze/n8n 软件工程式 Agent | 暴露 OpenAPI schema，可被低代码平台调用 | agent/server.py /api/openapi.json | ✅ |
| 6 框架开发实践 | 主流框架取舍 | 自研标准库框架对比论述 | docs/agent_design.md | 📖 |
| 7 构建自己的 Agent 框架 | LLM/Tool/Memory/Agent 组件化 | llm.py/tools.py/memory.py/agent_core.py 四组件 | agent/*.py | ✅ |
| 8 记忆与检索 | 短期/长期记忆、RAG | 会话窗口 + 用户画像 + 主题加权检索 + 会话摘要 | agent/memory.py、tools.py | ✅ |
| 9 上下文工程 | 上下文结构、预算、few-shot | SYSTEM 工厂（角色/工具/画像/示例）、长度预算裁剪 | agent/agent_core.py | ✅ |
| 10 通信协议 | MCP、A2A | 最小 MCP stdio 服务器（initialize/tools/list/call） | agent/tools_mcp.py | ✅ |
| 11 Agentic-RL | SFT→GRPO 训练 | 用户反馈数据收集（偏好记录），为训练备料 | agent/memory.py、web/gui | ✅ |
| 12 性能评估 | 基准、指标、回归 | 30 题评估集 + 多模式对比 + 主题统计 + 自定义集 | agent/eval.py、examples/eval_report.md | ✅ |
| 13 智能旅行助手 | 多工具综合案例 | 药企综合案例 demo（身份+法规+自查+ICER+模板） | examples/demo_workflow.md | 📖 |
| 14 深度研究智能体 | 多步检索、报告生成 | research 深度研究模式（多关键词检索+结构化报告） | agent/agent_core.py | ✅ |
| 15 赛博小镇 | 多智能体仿真 | 虚拟药事委员会（患者/药师/合规官三角色会谈） | agent/multi_agent.py | ✅ |
| 16 毕业设计 | 综合工程 | 版本路线图（v3.0 现状 → v4.0 规划） | docs/roadmap.md | ✅ |

## 快速验证命令

```bat
python agent\eval.py --mode local            :: 第12章：30题评估
python agent\cli.py                          :: 输入 paradigm plan 切换范式（第4章）
python agent\cli.py                          :: 输入 "深度研究 GSP合规"（第14章）
python agent\tools_mcp.py                    :: 第10章：MCP stdio 服务器（可接 Claude Desktop/Cursor）
python agent\multi_agent.py                  :: 第15章：虚拟药事委员会会谈
:: 第5章：GET http://127.0.0.1:8901/api/openapi.json
```
