from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from demo8.example_context import CodeWorkflowContext
from demo8.framework import HitlContext


@dataclass
class HitlWorkflowContext(HitlContext, CodeWorkflowContext):
    """
    这里是代码修改workflow才需要的文件快照。
    """

    before_snapshot: dict[str, Any] = field(default_factory=dict) # 保存文件之前的内容

    # 练习一：修改意见重试的状态。
    # revision_count 由 ApprovalNode 在用户选择重试时递增；
    # 达到 max_revisions 后再选重试会被视为拒绝，防止无限循环。
    revision_count: int = 0
    max_revisions: int = 2
