from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from demo6.framework import get_api_key
from demo8.framework import Workflow

from demo9.config import MAX_WORKFLOW_STEPS, WORKSPACE_DIR
from demo9.hitl_context import HitlWorkflowContext
from demo9.nodes import (
    ApprovalNode,
    ClassifyNode,
    HitlReportNode,
    InspectNode,
    PlanNode,
    RevisePlanNode,
    SafeApplyNode,
    VerifyNode,
)
from demo8.nodes import RiskCheckNode


def build_workflow() -> Workflow:
    """
    构造带 HITL 的代码修改 workflow。

    相比第八课，这里插了两道门：
    - plan -> risk_check：机器门（demo8 的硬校验 + 风险评估）
    - risk_check -> approval：人工门（人看完 diff 才放行）
    修订后的计划也要重新过这两道门。
    """
    classify = ClassifyNode(name="classify")
    inspect = InspectNode(name="inspect")
    plan = PlanNode(name="plan")
    risk_check = RiskCheckNode(name="risk_check")
    approval = ApprovalNode(name="approval")
    revise = RevisePlanNode(name="revise")
    apply_node = SafeApplyNode(name="apply")
    verify = VerifyNode(name="verify")
    report = HitlReportNode(name="report")

    classify.connect("inspect", inspect)
    inspect.connect("plan", plan)
    inspect.connect("report", report)
    plan.connect("risk_check", risk_check)
    risk_check.connect("apply", approval)
    # 机器门没过：不浪费人的注意力，直接汇报拦截原因。
    risk_check.connect("report", report)
    approval.connect("approved", apply_node)
    approval.connect("rejected", report)
    # 练习一：人工修改意见 -> 修订计划 -> 重新过机器门和人工门。
    approval.connect("revise", revise)
    revise.connect("revised", risk_check)
    apply_node.connect("verify", verify)
    verify.connect("report", report)

    return Workflow(start_node=classify, max_steps=MAX_WORKFLOW_STEPS)


def main() -> None:
    """程序入口。"""
    _ = get_api_key()
    print("HITL Demo 已启动。输入 exit 或 quit 结束。")
    print("你可以试试：帮我找到 utils.py 里的 greet_user，并把空名字处理改得更友好。")
    print(f"工作区目录：{WORKSPACE_DIR}")
    print("写操作前会请求人工审批：yes 执行 / r 按修改意见重试（最多 2 轮）/ 其他取消。")

    workflow = build_workflow()

    while True:
        goal = input("\n你：").strip()

        if not goal:
            print("请输入任务目标。")
            continue

        if goal.lower() in {"exit", "quit"}:
            print("对话结束。")
            break

        ctx = HitlWorkflowContext(goal=goal, workspace_dir=WORKSPACE_DIR)
        try:
            result = workflow.run(ctx)
        except Exception as exc:
            print(f"\n执行失败：{exc}")
            continue

        print("\n--- Workflow Logs ---")
        for line in result.logs:
            print(line)
        print("\n--- Result ---")
        print(result.report or "任务完成。")


if __name__ == "__main__":
    main()
