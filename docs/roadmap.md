# 版本路线图（对应 hello-agents 第 16 章 毕业设计）

## v3.0 现状（已发布）
- AI Native 引擎：ReAct/Plan/Reflection + 本地规则路由双模式
- 药剂工具集 6 项（含 ICER 计算器、时限速查）
- 记忆：会话 + 用户画像；评估：30 题集（本地 30/30）
- 三端：桌面应用（tkinter）/ Web / CLI；GitHub 开源

## v4.0 规划
1. **多智能体协作**：Supervisor 调度（药师顾问/合规顾问/企业顾问并行）
2. **MCP 客户端接入**：让 Agent 调用外部 MCP 服务（药典 API、说明书库）
3. **Agentic-RL 微调数据**：基于反馈偏好数据（memory/preferences.json）构造 SFT/GRPO 数据集
4. **评估基准扩展**：200 题行业题库 + LLM 打分器（LLM-as-Judge）
5. **知识库自动更新**：接入法规数据库自动同步

## 贡献指南
- 评估集：examples/qa 下按 JSON 格式扩展，运行 python agent/eval.py --custom 验证
- 新工具：在 agent/tools.py TOOLS 注册表登记即可被双模式自动调用
