from __future__ import annotations

from pathlib import Path


WORKSPACE_DIR = Path(__file__).resolve().parent / "project_workspace"
API_URL = "https://open.bigmodel.cn/api/coding/paas/v4/chat/completions"
MODEL_NAME = "glm-5.3"
MAX_COMPLETION_TOKENS = 3000
MAX_HISTORY_TURNS = 6
MAX_AGENT_LOOPS = 10
