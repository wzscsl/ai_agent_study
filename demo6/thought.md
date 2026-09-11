# Destination
- Agent框架会有哪些层
- 工具注册、消息存储、Runtime 执行、业务工具等解耦










# Practice
- 新增一个你自己的 `@tool`
- 给 Runtime 增加一个更严格的循环次数限制
- 观察 `MessageStore` 和 `ToolRegistry` 如果换实现，会影响哪些地方


# Practice 完成记录

## 练习一：新增 @tool

- 在 `builtin_tools.py` 里加了 `delete_text_file(relative_path, missing_ok=False)`，并加进 `register_builtin_file_tools`
- 体会：带默认值的参数会被 `decorators.py` 的 `build_parameters_from_signature` 自动标成 schema 里的**非必填**参数，函数签名即 schema
- 工具返回 `context_updates` 后，runtime 的 `update_state_from_tool_result` 会自动合并进 `shared_context`，工具和状态之间不需要硬编码字段

## 练习二：更严格的循环限制

- `runtime.py` 构造期校验 `max_loops`（非 int 或 < 1 直接 `ValueError`，不合法的配置在创建时暴露，而不是跑到第 N 轮才炸）
- 超时的 `RuntimeError` 带上实际生效的轮数
- `config.py` 的 `MAX_AGENT_LOOPS` 从 8 收紧到 4，`framework_demo.py` 接线进 `create_runtime`——循环上限和会话轮数一样，是"会变化的环境参数"，归 config 管

## 练习三：换 MessageStore / ToolRegistry 实现的影响面

### MessageStore

- 对外契约只有 `append` / `extend` / `snapshot`，`trim` 是内部的（藏在 append 里，所有写入都会经过）
- 使用方只有三处：
  1. `runtime.build_runtime_messages` 用 `snapshot()`
  2. `runtime.run` 用 `append()`（写 assistant 工具意图、tool 结果、最终答复，共 3 处）
  3. `framework_demo` 用 `append(user)`
- 换成 SQLite/Redis 存储、或把"按轮数裁剪"换成"按 token 裁剪"：只要保证 `snapshot()` 仍返回 `list[dict]`、写入后自动裁剪，**runtime 一行都不用改**，裁剪策略也只改 `message_store.py` 一个文件——这就是把消息管理拆出 runtime 的收益
- 真正的破坏点：`framework_demo.py` 异常回滚那两行**直接摸了 `message_store.messages`**（pop、读最后一条的 role）。这是实现细节泄漏，内存列表才有 `.pop()`，换了持久化存储就失效。正确做法是给 MessageStore 补一个 `pop_last_if(role="user")` 之类的公开方法

### ToolRegistry

- 注册侧 API：`register` / `register_many` / `register_tools_from_module`——使用方是 `helpers.create_runtime` 和 `builtin_tools.register_builtin_file_tools`
- 执行侧 API：`build_tools_payload` / `execute_tool_call`——**只有 `runtime.run` 在用**。这是 runtime 和工具层之间最窄的一条缝：哪怕换成远程工具服务（HTTP/MCP 网关），只需要新实现保持这两个方法，runtime 无感
- 换实现必须继续接受两种输入：`ToolDefinition` 对象（`mcp_adapter` 产出的就是它）和带 `__tool_definition__` 的 `@tool` 函数
- 两条不在类型签名里的**隐性契约**，换实现最容易踩：
  1. `execute_tool_call` 对"模型造成的错误"（参数不是合法 JSON、未知工具、缺参数）一律返回 `ok=False` 的 dict 而**不抛异常**——runtime 靠这个把错误喂回模型自我纠正；换成会抛异常的实现，`run()` 主循环直接崩
  2. `register_tools_from_module` 依赖 `decorators.py` 往函数对象上挂 `__tool_definition__` 的约定，换扫描逻辑要连着这个约定一起搬
- 另外 `framework/__init__.py` 导出的是具体类：真要多实现可替换，还差一层抽象基类 / 工厂函数（`create_runtime` 已经是工厂的雏形）

# Question

- **Q：一个最小 Agent 框架通常分哪几层？为什么要分层？**
  A：五层——模型调用（`llm.py`）、工具注册（`ToolRegistry` + `@tool`）、消息存储（`MessageStore`）、Runtime 执行（主循环）、业务工具（`builtin_tools.py`）。分层的回报是实现可替换、可单测：runtime 只依赖 ToolRegistry 的两个方法，工具层完全不知道 runtime 的存在。

- **Q：`@tool` 装饰器的实现原理是什么？**
  A：`inspect.signature` + `get_type_hints` 读函数签名，把类型注解自动映射成 JSON Schema（str→string、int→integer，带默认值的参数自动非必填），再把生成的 `ToolDefinition` 挂到函数的 `__tool_definition__` 属性上。收益：**函数签名即 schema**，不用手写重复的工具定义。

- **Q：`ToolRegistry` 的职责是什么？没有它会怎样？**
  A：三件事——发现（register / register_many / 扫描模块）、翻译（`build_tools_payload` 把 Python 工具定义转成 LLM 协议格式）、执行（`execute_tool_call` 按 name 分发 + 参数解析 + 错误兜底）。没有它，工具分发和错误处理会散进 runtime 主循环，每加一个工具都要动循环代码。

- **Q：把 `MessageStore` 从 runtime 拆出来，价值在哪？**
  A：所有写入收拢到 `append` 并自动 trim，换裁剪策略（按轮数→按 token）只改一个文件；对外只暴露 `snapshot()` 快照，将来换持久化后端（内存→SQLite/Redis）runtime 无感。

- **Q：runtime 每轮的调度消息为什么用 `role=user`，而不是中途插一条 system？**
  A：协议实践上中途插入的 system 不可靠——多数模型服务只在对话开头认真对待 system 消息；而最后一条 user 消息是模型的"工作焦点"，把状态放在末尾，模型天然会优先基于最新状态决策。

- **Q：工具怎么把信息回写给任务状态？为什么设计 `context_updates` 约定？**
  A：工具结果里带 `context_updates` 字段，runtime 统一 merge 进 `shared_context`。这是工具与状态之间的通用通信面：工具想暴露什么就写什么键，runtime 不需要为每个工具硬编码状态字段——**加新工具不用改 runtime**。

- **Q：`execute_tool_call` 遇到参数非法、未知工具时为什么不抛异常？**
  A：隐性契约：模型侧的错误一律返回 `ok=False` 的 dict，让主循环把错误作为观察喂回模型自我纠正；换成会抛异常的实现，`run()` 主循环直接崩。本质是"错误也是数据"的接口设计思想。

- **Q：一个新的工具源（比如 MCP server）如何接入这个框架？**
  A：`load_mcp_tools` 把远端工具转成本地 `ToolDefinition`，走同一条 `register` 通道；对 runtime 来说本地函数和远端工具无差别——这就是注册中心抽象带来的回报。

- **Q：这个自写框架和 LangChain / LangGraph 的核心抽象怎么对应？**
  A：`ToolRegistry` ≈ Tools/Toolkit；`MessageStore` ≈ Memory / Checkpoint；`AgentRuntime` ≈ AgentExecutor / Graph 的节点循环；`create_runtime` ≈ 装配工厂。自己写一遍的意义，就是理解这些框架的抽象为什么长成这样。

- **Q：如果要支持异步 / 并行工具调用，框架要动哪里？**
  A：`ToolRegistry.execute_tool_call` 提供 async 版本；runtime 对一次 assistant 消息里的多个 tool_calls 并发执行，再按原 tool_calls 顺序统一回写 role=tool 消息（协议靠 tool_call_id 配对）。MessageStore 若换异步后端，还要考虑写入的顺序性。

# idea
- framework通过_init_.py 导出必要的模块, 每个模块都有自己的职责, 互不干扰.

- 在runtime.py中，build_runtime_message函数的role参数是"user",原因是协议实践上，中途插入 system 不可靠。多数模型服务（DeepSeek、OpenAI 等）只在对话开头认真对待 system 消息，夹在中间的 system 消息可能被弱化或忽略。
注意力分布上，最后一条 user 消息是模型的“工作焦点”。状态作为最新的 user 消息出现在末尾，模型天然会优先基于它决策——这正是 runtime 想要的：每轮循环让模型“看一眼最新状态再走下一步”。

