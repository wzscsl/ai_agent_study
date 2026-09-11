from __future__ import annotations

from pathlib import Path


WORKSPACE_DIR = Path(__file__).resolve().parent / "project_workspace"
# 练习一：加入 risk_check 后，edit 路径最多 7 步
# （classify -> inspect -> plan -> risk_check -> apply -> verify -> report），
# 步数上限必须同步 +1，否则最后的 report 会被截断。
MAX_WORKFLOW_STEPS = 7
