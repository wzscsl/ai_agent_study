# AGENTS.md — 项目上下文说明

> 本文件是给 AI 编程助手（如 ZCode）看的项目背景说明。在任何新设备、新会话中打开本项目时，请先读完本文件再开始工作，可以避免重复沟通。
>
> 最后更新：2026-09-06

## 1. 这是什么项目

一个循序渐进的 **AI Agent 中文教程仓库**（源自 ljx1230/agent-tutorial），demo1–11 用纯 Python 手写、不依赖 LangChain 等框架，逐步搭出完整的 Agent：

| Demo | 主题 |
|---|---|
| demo1 | 最小 LLM 调用（Hello World） |
| demo2 | 多轮对话记忆 |
| demo3 | Tool Calling |
| demo4 | Planning（显式状态机） |
| demo5 | ReAct 循环（messages + state 双状态） |
| demo6 | 最小 Agent 框架（ToolRegistry / MessageStore / Runtime / @tool 装饰器） |
| demo7 | Coding Agent（先观察后修改，受限工作区） |
| demo8 | Workflow 编排（节点 + action 路由） |
| demo9 | HITL 人工审批（plan → approval → apply） |
| demo10 | RAG（智谱 embedding-3 + PostgreSQL pgvector） |
| demo11 | MCP（FastMCP 天气服务 + stdio 接入） |

所有者（学习者）已完成全部 demo 的学习，并进入下一阶段。

## 2. 已完成的工作（2026-09-06 会话产出）

- **7 份交互式思维导图**：`demo5/mindmap.html` ~ `demo11/mindmap.html`，各自总结对应 demo 的结构。特性：点击节点折叠/展开、SVG 贝塞尔连线按分支着色、加载后自动滚动到根节点、顶部可跳转相邻 demo。
- **26 周进阶学习计划表**：根目录 `STUDY_PLAN.html`。42 项可勾选任务、进度存 localStorage（键 `agent-plan-progress`）、阶段 0 准备 → 阶段 1 工程化（trace/eval/记忆/安全）→ 阶段 2 主流生态（LangGraph/MCP/源码）→ 阶段 3 毕业项目（可部署 coding agent）→ 阶段 4 求职。
- **demo1 已由学习者本人切换到智谱 API**：端点 `open.bigmodel.cn/api/coding/paas/v4`、模型 `glm-5.3`、环境变量 `API_KEY`。注意 demo5–11 仍用 DeepSeek（`DEEPSEEK_API_KEY`），两者配置不一致是已知状态。
- `GETTING_STARTED.md` 为学习者自己编写的上手指南。

## 3. Git 与环境事实（跨设备最容易踩的坑）

- **远程结构**：`origin` = https://github.com/wzscsl/ai_agent_study.git（学习者本人仓库，推这里）；`upstream` = https://github.com/ljx1230/agent-tutorial.git（原作者，只用来 `git pull upstream main` 拉教程更新，**不要推**）。
- **提交身份**：`wzscsl <1049750526@qq.com>`（全局配置）。
- **网络**：本机直连 `github.com` 会被重置，git 已配置仅对 github.com 走本地代理 `http://127.0.0.1:7897`（Clash Verge 混合端口）。**推送失败先确认代理软件在运行**；解除依赖：`git config --global --unset http.https://github.com.proxy`。
- **Python**：Git Bash 里的 `python` 是 Microsoft Store 占位符，不可用；运行项目请用 IDE 或实际安装的解释器。Node.js 可用。
- 平台：Windows + Git Bash + PowerShell（README 示例按 PowerShell 语法编写）。
- 日常同步三步：`git add .` → `git commit` → `git push`。

## 4. 学习进度与下一步

- 计划表当前处于**阶段 0（第 1 周）**：整理仓库与学习日志——本文件与 git 同步的完成即覆盖了其中大部分任务。
- 下一步（阶段 1 起点）：给 demo6 Runtime 接入 Langfuse 做 trace，然后为 demo10 建评估测试集（详见 `STUDY_PLAN.html` 第 2–7 周）。
- 各阶段配套阅读推荐：Anthropic《Building Effective Agents》、Lilian Weng《LLM Powered Autonomous Agents》、DeepLearning.AI《AI Agents in LangGraph》、Datawhale《Hello-Agents》（中文对照）、Chip Huyen《AI Engineering》。
- 建议建立 `docs/journal.md` 每周学习日志（计划中的贯穿习惯），持续沉淀上下文到仓库。

## 5. 产出物约定（保持一致性）

- **HTML 文档风格**：中文、微软雅黑、浅色点阵背景、白色卡片 + 彩色左边框、圆角、无任何外部依赖（完全内联，离线可用）。
- **思维导图模板**：沿用 `demo5/mindmap.html` 的结构（根节点居左、分支右展、SVG 连线、可折叠）；每个 demo 配色各异。
- **提交信息**：中文、描述性（说明改了什么、为什么）。
- 新增文档优先考虑放仓库内随 git 同步，而不是只留在会话里。
