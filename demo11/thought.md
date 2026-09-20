# Question

- **Q：MCP 是什么？解决什么问题？**
  A：Model Context Protocol，模型上下文协议——把"工具/数据源怎么接入 Agent"标准化。没有它，每个 Agent × 每个工具都是一次点对点集成（N×M 问题）；有了它，工具方写一次 MCP Server，所有支持 MCP 的客户端（Claude Code、Cursor、各类框架）都能用。常被类比成"AI 的 USB-C"。

- **Q：MCP 有哪几类原语？demo11 用了哪种？**
  A：三类——**tools**（模型可主动调用的动作）、**resources**（应用侧读取的上下文数据）、**prompts**（预置的提示模板）。demo11 只用了 tools（query_weather / list_supported_cities / get_clothing_advice），这也是目前生态里最常用的一类。

- **Q：stdio / SSE / HTTP 传输怎么选？**
  A：stdio：Server 作为本地子进程，通过标准输入输出通信——零网络配置、天然隔离，适合本机工具（demo 用这个）。SSE / Streamable HTTP：Server 是远程服务，可共享、可鉴权、可多租户，适合团队/生产环境。

- **Q：MCP Server、Agent Runtime、adapter 三方的职责边界？**
  A：Server 对协议负责（按 MCP 暴露工具），Runtime 对循环负责（只认本地 ToolDefinition），adapter 把两边翻译给对方。demo11 的关键：**接入一个全新工具生态，demo6 的 Runtime 一行代码没改**——这就是第六课分层的验收。

- **Q：adapter 具体做了哪些转换？**
  A：四件事——`list_tools` 拉取协议侧工具清单；工具名加 server 前缀（`weather_query_weather`）解决命名空间；MCP 的 `inputSchema` 直接当框架的 parameters（协议采用了 OpenAI 风格 schema，天然兼容）；MCP 的结构化结果对象转成框架约定的 `{"ok", "content"}` dict（`isError` 映射到 `ok` 字段——demo6 那条"错误也是数据"的隐性契约在这里延续）。

- **Q：为什么暴露给模型的工具名要加 server 前缀？**
  A：多 server 接入时避免同名工具冲突（两个 server 都可能有 `search`）。前缀就是最朴素的命名空间方案。

- **Q：demo 里每次工具调用都新起一个 stdio 会话，有什么代价？真实客户端怎么做？**
  A：每次调用 = spawn 子进程 + initialize 握手 + call + 断开，开销大且浪费。教学上换来的是代码极简（每步独立、好读）。生产客户端保持长连接、复用会话、做断线重连和并发控制——这就是"教学简化 vs 生产差距"的典型样本。

- **Q：MCP 和 function calling 是什么关系？**
  A：不同层次的东西，不是竞争。function calling 是**模型/API 层的能力**（模型怎么表达"我要调工具"）；MCP 是**工具分发协议**（工具从哪里来、怎么描述、怎么传输）。MCP 工具最终仍然通过 function calling 被模型调用——demo 里 adapter 产出的 ToolDefinition 走的正是 demo6 原有的 tools payload。

- **Q：MCP 有什么安全风险？**
  A：`McpServerConfig(command=...)` 意味着**任意命令执行入口**——装一个恶意 MCP server 等于给对面代码执行权；工具描述文本本身可能携带提示注入；远程模式还有鉴权与多租户问题。生产要做来源审批、命令白名单、沙箱、最小权限——本质上就是 demo9 HITL 思想在"接入外部工具"上的延伸。

- **Q：adapter 的 handler 里用默认参数绑定循环变量，解决什么问题？**
  A：`def handler(_tool_name: str = original_name, ...)`——Python 闭包是**晚绑定**，循环里定义的函数引用循环变量时拿到的是最后一次的值；用默认参数在定义时**早绑定**当前值。这是 Python 面试高频题，这段 adapter 是绝佳的正面教材。

# Practice 完成记录

## 前置：环境坑（mcp 2.x 与教程代码不兼容）

- 本机 pip 装到的 `mcp 2.2.0` 已把 `FastMCP` 改名为 `MCPServer`，教程的 1.x 写法直接 import 报错
- 处理：降到 `mcp 1.30.0`，并给 `requirements.txt` 的 `mcp>=1.9.0` 补上 `<2` 上界——**不带上界的依赖声明是时间炸弹**，教程作者写代码时的版本约定会悄悄过期

## 练习一：WEATHER_DATA 新增城市（成都）

- 加一条数据即可查询，**工具代码零改动**——数据与工具逻辑分离的直接收益

## 练习二：新增 get_clothing_advice 工具

- 不维护独立的建议表，而是**基于 query_weather 同一份 WEATHER_DATA 推导**（温度档位 + 降雨/晴的叠加提示）——演示 MCP 工具之间共享业务数据
- 模型为"去杭州出差穿什么"自主选择了 `weather_get_clothing_advice`；adapter 自动发现并注册（带前缀），框架侧零改动

## 练习三：去掉"优先调用工具"约束的行为对比（--neutral 开关）

给 demo 加了 `--neutral` 参数（中性提示词，工具仍注册可见），做了两组对照：

- **直白问题**（"杭州天气怎么样？"、"南京天气怎么样？"）：中性模式下模型**照样主动调用工具**，不支持的城市照样如实回传、不编造——工具描述本身就是足够强的信号，系统提示词约束更像冗余保险
- **间接问题**（"我下周要去成都旅游，需要带伞吗？"）：两种模式都调了工具；中性模式反而多调用了穿衣建议工具（样本量 n=1，不作过度解读）
- 结论：对 glm-5.3 这类工具倾向强的模型，约束在简单场景是冗余的；它真正值钱的场景是——工具倾向弱的模型、提问方式模糊、以及对抗"凭训练记忆直接回答事实"的惯性。**工具描述质量 > 系统提示词措辞**，这是本次实测最实用的收获

# idea

- 全教程主线在这里收束：demo6 抽的框架层（ToolRegistry / ToolDefinition），到 demo11 接入一个全新工具生态时**一行未改**——分层设计的最终验收不是"能跑"，而是"能不改地扩展"
- "协议世界 ↔ 框架世界"的翻译层是系统集成永恒的主题：命名空间（前缀）、格式适配（inputSchema→parameters）、错误语义映射（isError→ok=False）。认出这个模式后，看任何 adapter（数据库驱动、云 SDK、消息中间件）都是同一套骨架
- 教学简化 vs 生产差距清单（demo11 版）：短连接 vs 长连接会话、无鉴权、无超时重试、stdio 单机 vs 远程多租户——每一条都是"如果要做生产"的 TODO
- 软约束的定量认识（练习三）：工具描述质量 > 提示词约束 > 模型自觉，三层都软；硬的仍然只有工具边界本身（demo7 的沙箱、demo9 的审批）。安全设计永远要有一条不依赖模型"听话"的底线
- 至此 11 个 demo 的能力地图完整了：模型调用（1）→ 记忆（2）→ 工具（3）→ 规划（4）→ 自主循环（5）→ 框架化（6）→ 场景化（7-8）→ 安全（9）→ 外部记忆（10）→ 外部工具生态（11）
