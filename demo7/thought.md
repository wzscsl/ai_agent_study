# Question

- **Q：coding agent 和通用 agent 的核心差异是什么？**
  A：工作流的形状不同。通用 agent 达成目标即可；coding agent 的每次修改都有副作用，所以工作流被固定成"先观察后修改"：list/search 缩小范围 → read 确认内容 → 精确修改 → （理想情况下）验证。工具也按这个形状分成观察型 / 修改型两类。

- **Q：为什么要把工具分成"观察型"和"修改型"两类？**
  A：观察型工具（list_files / search_text / search_files_by_name / read_text_file）无副作用，调用失败零成本，可以随便试；修改型工具（replace_text_in_file / write_text_file）有副作用，必须谨慎。分类把安全边界落在**工具设计**上而不是模型自觉上，同时也是一种行为引导：先用便宜的观察收集事实，再做昂贵的修改。

- **Q：`expected_occurrences` 是干什么的？为什么说它是安全设计？**
  A：模型替换前必须声明"预期旧文本出现几次"，工具实际 `count` 后不匹配就拒绝执行。这是把模型的自述变成**可校验的前置条件**：防止误替换多处相似代码、防止文件实际内容和模型记忆不一致时的盲改。校验成本极低（一次 count），防住的却是整个文件被改坏的事故。

- **Q：为什么同时提供 `replace_text_in_file` 和 `write_text_file`？什么时候用哪个？**
  A：最小改动原则。小而精确的编辑用 replace：diff 最小、可审查、不会波及文件其他部分；创建新文件或确实要整体重写时才用 write。write 更重、风险更大——一次性覆盖整个文件，模型对没读过的部分等于盲写。

- **Q："先观察后修改"是靠什么强制的？只靠系统提示词吗？**
  A：三层。提示词层（明确要求先读后改、没看到工具结果不许声称完成）是最软的；工具层（`old_text` 必须逐字精确匹配，没读过文件几乎不可能拼对）才是硬约束；协议层（tool 结果回传形成 Observe）保证模型每轮都能看到真实反馈。最硬的一道闸其实是 replace 的精确匹配。

- **Q：coding agent 的工作区边界（workspace confinement）是怎么实现的？**
  A：`resolve_safe_path`：拒绝绝对路径、路径 `resolve()` 之后必须仍落在 `WORKSPACE_DIR` 内（挡住 `..` 逃逸）。这是最小权限原则——agent 只拿到完成任务所需的最小文件系统权限。真实产品里对应 sandbox、容器、git worktree 这类隔离手段。

- **Q：`CodingAgentRuntime` 为什么选择继承 `AgentRuntime` 而不是复制一份改？**
  A：这是 demo6 分层的验收：只覆写 3 个方法（coding 系统提示词、`create_state` 注入 workspace、`build_runtime_message` 场景化调度语），主循环、工具执行、消息管理全部复用。反过来讲，如果换一个场景必须复制框架代码，就说明第六课的解耦是失败的。

- **Q：搜索工具为什么重要？让模型把文件全读一遍不行吗？**
  A：上下文经济性。工作区可能很大，全读浪费 token 还可能超出窗口；`search_text` / `search_files_by_name` 先把范围缩到"文件 + 行号"，再精读相关片段。"先缩小范围，再去读具体文件"也是真实 coding agent（grep → read）的标准动作。

- **Q：demo7 的 agent 改完代码后怎么确认改对了？缺什么？**
  A：目前只能靠重读文件（read 回来人工核对）。真实 coding agent 还需要"修改-验证"闭环的另一半：运行测试、语法检查、lint、diff 展示。demo7 有意省掉了这部分，把观察和修改讲清楚先。

- **Q：这个原型和 Claude Code / Cursor 这类产品的差距在哪？**
  A：核心循环同构——search → read → edit，而且 `replace_text_in_file` 的"精确匹配 + 出现次数校验"和 Claude Code 的 Edit 工具（old_string 非唯一即报错、要求补充上下文）是同一个设计思想。产品多出来的是：AST / 语义级理解、diff 审批 UI、测试反馈环、git 集成、分级权限。

# idea

- 我的原始感受：这一章更多是"细化边界能力 + 要求模型更谨慎地调用工具"。
- 复盘后修正：
  1. 两个观察都是真实的设计点，但更大的主线其实是**框架落地**——`CodingAgentRuntime` 只覆写 3 个方法就完成场景化定制，demo6 抽的层在这里被验收
  2. "谨慎"不是提示词**要求**出来的，是工具设计**结构化**出来的：观察型/修改型分类、replace 的逐字精确匹配、`expected_occurrences` 前置校验——没读过文件就改不动，这是硬约束，提示词只是软引导
  3. "细化边界"里真正新的不是路径沙箱（demo5 起就有），而是"模型声明预期、工具校验现实"这种**契约式安全**（expected_occurrences）
  4. coding agent 与通用 agent 的本质差异是工作流形状：先观察后修改 + 最小改动原则
