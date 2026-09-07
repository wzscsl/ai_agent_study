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

