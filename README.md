# 💊 LeebertyPharmacyAdministration

药事管理智能 Agent —— 面向**个人 / 医疗机构 / 企业**的药事管理科目服务。

基于本地知识库（14 个专题、112 个知识块）提供知识问答、合规自查与模板导航；可选接入真实大模型（OpenAI 兼容协议，RAG 增强），未配置时自动降级纯本地模式。

## 🚀 快速开始

> 环境：Windows + Python 3.8+（仅标准库，无需 pip 安装）

| 方式 | 命令 |
|---|---|
| **桌面应用（推荐）** | `start_app.bat` 或 `python agent\gui.py` |
| Web 服务 | `start_web.bat` 或 `python agent\server.py` → http://127.0.0.1:8901 |
| 命令行 | `start_cli.bat` 或 `python agent\cli.py` |

## 🤖 接入大模型（可选）

复制 `config.example.json` 为 `config.json`，填写 `api_base` / `api_key` / `model` 并设 `enabled: true`；
或桌面应用菜单"设置 → 大模型 API 设置"。支持 DeepSeek、OpenAI、智谱 GLM、通义千问、Kimi、Ollama 等任意 OpenAI 兼容服务。

> 🔒 `config.json` 含密钥，已被 .gitignore 排除，请勿提交。

## 📚 功能

- **知识问答**：法规体系、药品监督、GMP、GSP、医疗机构药事管理、处方调剂（四查十对）、药学服务、药物警戒、特殊药品、药物经济学、GxP、临床试验 CRA·CRC、QA·QC 等专题
- **合规自查**：GSP、医疗机构药事管理、麻精药品"五专"、不良反应报告 —— 交互式清单，输出通过率与整改项
- **模板服务**：药事管理制度汇编、四查十对记录表、不良反应报告表、年度培训计划

## 📁 结构

```
├── agent/           # 引擎：engine(检索) services(服务) llm(大模型) gui(桌面) cli(命令行) server(Web)
├── knowledge_base/  # 14 篇专题知识库（Markdown，可按需扩展）
├── services/        # 服务档案与制度/记录模板
├── web/             # Web 界面（可选）
└── docs/            # 药事管理调研报告（含来源）
```

## 🧠 Agent 架构（借鉴 Datawhale hello-agents 方法论）

- **范式**：ReAct（默认）/ Plan-and-Solve / Reflection 三档；LLM 模式下执行"思考→工具→观察→回答"循环，最多 4 轮工具调用
- **工具集**（结构化注册，文本协议 `[TOOL_CALL:名称:参数]`）：`kb_search` 知识检索、`icer_calc` 药物经济学 ICER 计算器、`adr_quick` 不良反应时限速查、`law_lookup` 法规速查、`template_list` 模板、`checklist_router` 自查
- **双模式一致**：未配置大模型时由本地规则引擎路由同一套工具（含主题加权检索），回答质量与工具能力保持一致
- **记忆**：短期会话窗口 + 用户画像长期记忆（`memory/profile.json` 跨会话记住身份与关注点）
- **评估**：`python agent/eval.py` 内置 30 题评估集（个人/集体/企业各 10），输出 `examples/eval_report.md`（本地模式：30/30 通过）
- **可观测**：每次问答返回思考轨迹 trace，GUI 状态栏 / CLI / Web API 均可查看推理过程

- **十六章节全面深化**：每章方法论已逐章落地（范式/工具/记忆/上下文/MCP/反馈/评估/研究/多智能体/路线图），见 [docs/hello_agents_16章借鉴与深化对照.md](docs/hello_agents_16章借鉴与深化对照.md) 与 [docs/agent_design.md](docs/agent_design.md)

## ⚠️ 免责声明

知识辅助工具，不构成医疗诊断或法律意见；用药请遵从医师处方与执业药师指导，合规问题以现行有效法规及属地监管部门为准。
