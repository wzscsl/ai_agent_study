from __future__ import annotations

from pathlib import Path


# 第六课的配置保持尽量简单：
# - 不把这些常量塞回 runtime 里
# - 也不做复杂配置系统
# 这样读代码时，大家可以先把“会变化的环境参数”集中看完。
API_URL = "https://open.bigmodel.cn/api/coding/paas/v4/chat/completions"
MODEL_NAME = "glm-5.3"
MAX_COMPLETION_TOKENS = 3000
# 练习二：把默认的 8 收紧到 4。
# demo 的典型任务（建文件 -> 读回来核对）2~3 轮循环即可完成，
# 4 轮足够走完正常路径，又能更早拦住“反复调工具不收敛”的模型。
MAX_AGENT_LOOPS = 4
MAX_HISTORY_TURNS = 6
GENERATED_FILES_DIR = Path(__file__).resolve().parent / "generated_files"
