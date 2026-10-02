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

## ⚠️ 免责声明

知识辅助工具，不构成医疗诊断或法律意见；用药请遵从医师处方与执业药师指导，合规问题以现行有效法规及属地监管部门为准。
