from __future__ import annotations

from pathlib import Path


WORKSPACE_DIR = Path(__file__).resolve().parent / "project_workspace"
# 步数上限按最长路径推导：
#   classify -> inspect -> plan -> risk_check
#   -> (approval -> revise -> risk_check) x max_revisions(2)
#   -> approval -> apply -> verify -> report
# = 4 + 6 + 4 = 14 步。
# 第一道保险是 HitlWorkflowContext.max_revisions（修订次数上限），
# max_steps 只是防路由成环的兜底，两者缺一不可。
MAX_WORKFLOW_STEPS = 14
