# 是如何在灵活性和可控性之间找平衡的
1. 灵活性：由模型来决定的，
2. 可用性：由程序来决定的，

# run_react_agent(api_key,user_goal,messages) -> str:
1. 函数如何驱动agent执行任务

# build_runtime_messages
为什么既需要messages又需要state？
1. messages 负责会话记忆和工具历史
2. state 负责结构化任务状态
messages 中包含 system 消息，用于传递任务状态摘要。,为什么messages不能够结构化任务状态？


state 中包含多个字段，用于存储任务状态。
为什么需要state？
state 中包含多个字段，用于存储任务状态。

# update_state_from_tool_result
工具是直接将result插入messages中返回给agent的，并且每次通过result更新state


# Test 
1. 让 Agent 先生成文件，再自己读出来检查
2. 让 Agent 列出已有文件，再挑一个继续修改或总结
3. 尝试增加一个工具，观察主循环是否还能稳定工作

# Question

- **Q：什么是 ReAct？它和普通 function calling 有什么区别？**
  A：ReAct = Reasoning + Acting，把"思考 → 调工具 → 观察结果 → 再思考"组织成循环。function calling 是单次能力：模型返回一次工具调用就结束；ReAct 把单次调用循环化，并把工具结果作为观察（Observe）喂回模型，由模型自主决定下一步做什么、何时收尾。

- **Q：Agent 主循环怎么知道该结束？怎么防死循环？**
  A：两条终止路径——模型某轮不再返回 tool_calls（自然完成，该轮文本即最终答复）；或超过 `MAX_AGENT_LOOPS` 熔断抛错。防死循环三件套：循环上限兜底、系统提示词约束（没看到 tool 结果不许声称完成）、工具错误如实回传让模型有机会换路。

- **Q：工具结果为什么必须写成 `role=tool` 的消息回传？`tool_call_id` 起什么作用？**
  A：这是 ReAct 的 Observe 环节——下一轮模型据此看到真实世界的反馈。`tool_call_id` 把结果和对应的调用意图配对，一次返回多个 tool_calls 时模型才能分清哪条结果对应哪次调用，这是 chat 协议的硬性要求。

- **Q：demo5 为什么同时维护 messages 和 state 两份状态？**
  A：职责不同。messages 是给模型看的自然语言会话记忆（跨轮持久、会被裁剪）；state 是给程序看的结构化事实（current_goal / last_tool_name / completed / loop_count，任务级、每次新建）。一个服务模型决策，一个服务程序控制流和熔断判断。

- **Q：为什么每个循环都要把 state 摘要拼进请求消息？**
  A：模型本身无状态，每轮请求都要重新"告诉它现在到哪一步"。状态摘要保证即使历史被裁剪、或某次工具结果很长，关键事实（目标、最近一次工具、是否完成）始终对模型可见。

- **Q：工具执行失败时，为什么返回 `ok=False` 而不是直接抛异常？**
  A：返回结构化错误 = 把失败作为观察喂回模型，模型可以自我纠正（改路径、换参数、换工具）；抛异常会中断整个循环，剥夺纠正机会。只有环境级错误（网络、API 挂了）才向上抛给调用方。

- **Q：为什么要裁剪历史消息？这个 demo 的裁剪策略是什么？**
  A：控制上下文窗口占用和 token 成本，也避免陈旧上下文干扰决策。策略：一轮完整交互约 4 条消息（user → assistant(tool_call) → tool → assistant），按 `max_turns * 4` 只保留最近的，system 消息不参与裁剪。

- **Q：`tool_choice="auto"` 意味着什么？**
  A：由模型自主决定本轮返回纯文本还是发起工具调用——这是 ReAct 自主性的开关。对比 `"none"`（禁用工具）和指定具体函数（强制模型必须调某个工具）。

- **Q：temperature 为什么设成 0.2 这么低？**
  A：Agent 场景要的是确定性：工具名、参数格式、文件路径都不能随机发挥。低温度减少"发挥"，也让最终答复更稳定。

- **Q：这个手写循环和生产框架（LangChain Agent 等）差在哪？**
  A：核心循环等价：组装消息 → 调模型 → 执行工具 → 回写结果。生产框架多的是工程件：重试与超时、流式输出、并行工具调用、结构化输出校验、可观测性（tracing）、沙箱与权限控制。
