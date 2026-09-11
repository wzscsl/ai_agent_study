# Question

- **Q：什么场景该用固定 workflow，什么场景该用自由 agent？**
  A：判断标准是"你能否提前写出状态机"。步骤稳定、要求可预测和审计链路的任务（审批流、数据管道、固定套路的代码修改）用 workflow；步骤不定、需要模型自主探索的任务（开放性调试、研究型问题）用 agent。workflow 拿确定性换灵活性，agent 反过来。

- **Q：workflow 和 agent 的本质区别是什么？**
  A：控制流的归属。自由 agent 的控制流在模型手里——每一轮由模型决定下一步调什么工具；workflow 的控制流在程序手里——节点和路由是写死的，模型只在节点内部干活。LLM 从"决策者"降级为"节点内的执行器"。

- **Q：这个 workflow 框架的核心抽象是什么？**
  A：三个：`BaseWorkflowNode`（run 返回 action，route 按 action 找下一跳）、`WorkflowContext`（节点间共享状态）、`Workflow` 执行器（循环 + max_steps 熔断）。合起来就是一个用 LLM 填充节点的有限状态机（FSM）。

- **Q：节点返回 action + route 查表，和直接在节点里 if/else 调下一个节点有什么区别？**
  A：节点只声明"发生了什么"（比如 intent=edit），不直接引用下一个节点对象。路由表集中在编排处（`build_workflow`），节点之间零耦合——同一组节点可以重新编排出不同流程而不改节点代码。这是"控制反转"在流程编排里的形态。

- **Q：为什么每个节点职责要单一？**
  A：可测试（给个 mock context 就能单测一个节点）、可复用（同一节点接进不同流程）、失败可定位（logs 里 `node=xxx` 直接看到卡在哪一步）。

- **Q：`VerifyNode` 的价值在哪？为什么 workflow 能保证验证一定执行，自由 agent 却难保证？**
  A：修改-验证闭环让每个改动都有读回的证据。workflow 里 verify 是编排保证的——apply 之后必跳 verify；自由 agent 的验证靠提示词"劝"，模型心情不好就跳过。确定性来自编排，不来自模型自觉。

- **Q：`WorkflowContext` 为什么分框架层和业务层两层？**
  A：框架层只认 goal / shared / logs；业务字段（intent、patch_plan、verification…）全在 `CodeWorkflowContext` 里，不污染框架。框架层还预留了 `HitlContext`（人工审批）说明同一框架能长出新能力。这和 demo6 的 messages/state 双轨是同一个解耦思想。

- **Q：workflow 的 `max_steps` 和 agent 的 `MAX_AGENT_LOOPS` 都是熔断，区别在哪？**
  A：形式相似，防的东西不同。agent 的循环上限防"模型不收敛"（一直调工具不收尾）；workflow 的 max_steps 防"路由成环"（A→B→A 死循环）。FSM 的节点天然会走完，但路由表配错时没有自然终止条件，靠它兜底。

- **Q：risk check 节点为什么放在 plan 和 apply 之间？硬校验和软评估各自起什么作用？**
  A：门卫位置——计划产生之后、副作用发生之前。硬校验（程序去数 old_text 实际出现次数、对比 expected_occurrences）便宜且确定，拦截"计划和现实不符"；软评估（模型判断改动影响面）处理程序测不出来的语义风险。双层设计是 demo7 `expected_occurrences` 契约式安全的节点化升级：从工具内部的一道闸，升级成流程里独立的一站。

- **Q：demo8 和 LangGraph 是什么关系？**
  A：同构。Node ≈ graph node，connect/route ≈ conditional edge，WorkflowContext ≈ state，max_steps ≈ recursion_limit。LangGraph 多的是持久化 checkpoint、并行分支、streaming。demo8 等于手写了一个最小 LangGraph。

# Practice 完成记录

## 练习一：新增 risk check 节点

- `nodes.py` 新增 `RiskCheckNode`，插在 plan 和 apply 之间；`PlanNode` 的 action 从 `apply` 改为 `risk_check`
- 双层检查：硬校验（目标文件可读、old/new 文本齐全、实际出现次数 == expected_occurrences）+ 软评估（模型输出 risk_level）
- 拦截路由：硬校验不过或 risk_level=high 时直接跳 report，修改不执行；`CodeWorkflowContext` 加 `risk_assessment` 字段
- **踩坑记录**：`MAX_WORKFLOW_STEPS` 必须从 6 提到 7。edit 路径现在最多 7 步，不加的话最后的 report 会被熔断截断——workflow 加节点时，步数预算是隐性联动项

## 练习三：VerifyNode 多做一步结果总结

- 读回文件后先做硬校验：`old_text_gone`（旧文本消失）+ `new_text_present`（新文本出现），写进 `ctx.verification_checks`
- 再用 `ask_llm_text` 生成一段用户可读的验证总结（`verification_summary`），连同硬校验一起进 `ReportNode` 的输入
- 体会：验证也分"程序能确定的"（字符串消失/出现）和"要模型判断的"（改动是否合理），前者先行

## 练习二：自由 agent vs 固定 workflow

- 写了 `compare_free_agent_vs_workflow.py`：同一个任务分别跑 demo7 的 CodingAgentRuntime（自由 agent）和 demo8 的 workflow（各自独立工作区），输出耗时、步骤路径 / 循环数、改动文件、最终答复
- 结论见下面 idea

# idea

- 对比分析（六个维度）：
  - 控制流归属：agent 在模型手里，workflow 在程序手里——这是所有差异的根源
  - 可预测性：同一任务跑三遍，workflow 步骤路径每次一样；agent 的循环数和工具顺序可能每次都变
  - 成本：workflow 的 LLM 调用次数固定（节点数决定），可以预算；agent 的循环数不定，成本是随机变量
  - 能力上限：agent 能处理计划外情况；workflow 只会走编排好的路，计划外输入只能落进 report 兜底
  - 风险控制：agent 靠工具内校验（expected_occurrences）；workflow 能做节点级拦截（risk check 直接阻断）+ 编排保证 verify 必跑
  - 调试：agent 要复盘模型每轮决策；workflow 看 logs 就知道卡在哪个节点
- 两者的关系不是替代，是谱系的两端：确定性要求越高越靠 workflow，探索性越强越靠 agent。真实产品常是混合体——外层 workflow 编排阶段，个别节点内部再嵌一个 mini agent
- 另一个观察：demo8 里的节点大多不是 agent——每个节点只有一次 LLM 调用。workflow 是"把 LLM 当节点里的函数用"，agent 是"把 LLM 当控制流用"
