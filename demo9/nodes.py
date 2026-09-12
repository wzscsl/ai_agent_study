from __future__ import annotations

import difflib
from dataclasses import dataclass

from demo8.framework import BaseWorkflowNode
from demo8.nodes import ClassifyNode, InspectNode, PlanNode, VerifyNode
from demo8.tools import read_text_file, replace_text_in_file, write_text_file
from demo6.framework import ask_llm_json, ask_llm_text

from demo9.hitl_context import HitlWorkflowContext


def _preview_text(value: str, max_length: int = 500) -> str:
    """让终端确认信息更短一点，避免一大段代码直接糊满屏幕。"""
    if len(value) <= max_length:
        return value
    return value[:max_length] + "\n...省略..."


def _format_diff_preview(old_text: str, new_text: str, max_lines: int = 60) -> str:
    """
    练习二：把旧内容/新内容渲染成 unified diff，方便人工审阅。

    人审的时候最关心“到底变了哪几行”，diff 比整段贴出旧文和新文
    的认知负荷低得多；纯新增文件（没有旧文本）时退回预览新内容。
    """
    if not old_text:
        return "（新增内容，无旧文本可对比）\n" + _preview_text(new_text)

    diff_lines = list(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile="当前内容",
            tofile="修改后",
            lineterm="",
        )
    )
    if not diff_lines:
        return "（新旧内容相同，无差异）"

    if len(diff_lines) > max_lines:
        hidden = len(diff_lines) - max_lines
        return "\n".join(diff_lines[:max_lines]) + f"\n...另有 {hidden} 行差异未展示..."
    return "\n".join(diff_lines)


@dataclass
class ApprovalNode(BaseWorkflowNode):
    """
    人工确认节点。

    这个节点是第九课的核心：
    - 模型可以给出修改计划
    - 但真正写文件之前，必须先给人看
    - 人工同意后，workflow 才能进入 apply 节点

    练习一之后多了一条分支：
    - yes：批准，进入 apply
    - r：按“修改意见”修订计划后重新走检查和审批（有次数上限）
    - 其他：拒绝，直接进报告
    """

    def run(self, ctx: HitlWorkflowContext) -> str:
        if not ctx.approval_required:
            ctx.approved = True
            ctx.logs.append("approval skipped")
            return "approved"

        if ctx.intent == "summary":
            ctx.logs.append("approval skipped for summary task")
            return "approved"

        relative_path = str(ctx.patch_plan.get("relative_path") or ctx.target_file or "")
        old_text = str(ctx.patch_plan.get("old_text") or "")
        new_text = str(ctx.patch_plan.get("new_text") or "")
        rationale = str(ctx.patch_plan.get("rationale") or "模型没有提供修改理由。")
        expected = ctx.patch_plan.get("expected_occurrences")

        # 练习二：按“人工审阅”重排展示信息——
        # 先看结论（改哪个文件、为什么、第几轮），再看 diff，最后给核对数据。
        print("\n" + "=" * 46)
        if ctx.revision_count:
            print(f"待确认的修改计划（第 {ctx.revision_count} 轮修订后）")
        else:
            print("待确认的修改计划")
        print("=" * 46)
        print(f"目标文件：{relative_path}")
        print(f"修改理由：{rationale}")

        print("\n内容变化（unified diff）：")
        print(_format_diff_preview(old_text, new_text))

        # 给人一个可核对的安全性数据：旧文本当前实际出现几次，
        # 和计划声明的 expected_occurrences 是否一致。
        actual: int | None = None
        if old_text:
            current = read_text_file(str(ctx.workspace_dir), relative_path)
            if current.get("ok"):
                actual = str(current.get("content") or "").count(old_text)
                marker = "一致" if actual == expected else "不一致，需要留意"
                print(f"\n出现次数核对：实际 {actual} 次 / 计划预期 {expected} 次（{marker}）")

        print("\n操作：输入 yes 执行 / r 按修改意见重试 / 其他任意内容取消")
        answer = input("你的选择：").strip().lower()

        if answer in {"yes", "y"}:
            ctx.approved = True
            ctx.approval_note = "human approved"
            ctx.logs.append("approval=approved")
            return "approved"

        if answer in {"r", "revise", "retry"}:
            if ctx.revision_count >= ctx.max_revisions:
                ctx.rejected = True
                ctx.approval_note = "rejected: revision budget exhausted"
                ctx.human_feedback = input("已达修订次数上限，只能取消。可输入取消原因，直接回车跳过：").strip()
                ctx.logs.append("approval=rejected, reason=revision_budget_exhausted")
                return "rejected"

            feedback = input("请输入修改意见（直接回车视为取消）：").strip()
            if not feedback:
                ctx.rejected = True
                ctx.approval_note = "rejected: no feedback given"
                ctx.logs.append("approval=rejected, reason=empty_feedback")
                return "rejected"

            ctx.revision_count += 1
            ctx.human_feedback = feedback
            ctx.logs.append(f"approval=revise, round={ctx.revision_count}, feedback={feedback!r}")
            return "revise"

        ctx.rejected = True
        ctx.approval_note = "human rejected"
        ctx.human_feedback = input("可以输入取消原因，直接回车跳过：").strip()
        ctx.logs.append(f"approval=rejected, feedback={ctx.human_feedback!r}")
        return "rejected"


@dataclass
class RevisePlanNode(BaseWorkflowNode):
    """
    根据人工修改意见修订计划（练习一新增节点）。

    它和 PlanNode 的区别只在于输入多了“人工修改意见”，
    输出仍然是一份同样结构的 patch plan。
    修订后的计划回到 risk_check 重新过机器门，再回到人工审批——
    新计划不允许因为“是人要的”就免检。
    """

    def run(self, ctx: HitlWorkflowContext) -> str:
        system_prompt = (
            "你是一个 workflow 修改计划修订器。"
            "根据用户目标、文件快照、原修改计划和人工修改意见，输出修订后的完整计划 JSON。"
            "字段与原计划相同：relative_path, old_text, new_text, expected_occurrences, rationale。"
            "old_text 必须逐字来自文件快照的当前内容，只做一个小而精确的改动。"
        )
        user_content = (
            f"用户目标：{ctx.goal}\n"
            f"目标文件：{ctx.target_file}\n"
            f"文件快照：{ctx.file_snapshot}\n"
            f"原修改计划：{ctx.patch_plan}\n"
            f"人工修改意见（第 {ctx.revision_count} 轮）：{ctx.human_feedback}\n"
        )
        plan = ask_llm_json(system_prompt, user_content)
        ctx.patch_plan = plan
        ctx.logs.append(f"revised_plan round={ctx.revision_count}, plan={plan}")
        return "revised"


@dataclass
class SafeApplyNode(BaseWorkflowNode):
    """
    带确认保护的执行节点。

    第八课的 ApplyNode 会直接执行修改；第九课这里多了一道硬约束：
    没有人工确认，就不允许写文件。
    """

    def run(self, ctx: HitlWorkflowContext) -> str:
        if ctx.approval_required and not ctx.approved:
            ctx.apply_result = {"ok": False, "error": "human approval is required before applying changes"}
            ctx.logs.append("apply blocked: approval missing")
            return "report"

        relative_path = str(ctx.patch_plan.get("relative_path") or ctx.target_file or "")
        old_text = str(ctx.patch_plan.get("old_text") or "")
        new_text = str(ctx.patch_plan.get("new_text") or "")
        expected_occurrences = int(ctx.patch_plan.get("expected_occurrences") or 1)

        if relative_path:
            ctx.before_snapshot = read_text_file(str(ctx.workspace_dir), relative_path)
            ctx.logs.append(f"backup_before_apply={ctx.before_snapshot.get('ok')}")

        if old_text and new_text:
            result = replace_text_in_file(
                str(ctx.workspace_dir),
                relative_path,
                old_text,
                new_text,
                expected_occurrences,
            )
        else:
            result = write_text_file(
                str(ctx.workspace_dir),
                relative_path,
                str(ctx.patch_plan.get("content") or ""),
                overwrite=True,
            )

        ctx.apply_result = result
        ctx.logs.append(f"apply_result={result}")
        return "verify"


@dataclass
class HitlReportNode(BaseWorkflowNode):
    """生成包含确认结果的最终报告。"""

    def run(self, ctx: HitlWorkflowContext) -> str:
        if ctx.rejected:
            ctx.report = (
                "任务已取消：修改计划没有通过人工确认，所以没有写入任何文件。"
                f"\n取消原因：{ctx.human_feedback or '未填写'}"
            )
            return "done"

        system_prompt = (
            "你是一个 workflow 报告生成器。"
            "请基于执行日志、审批结果、修改结果和验证结果，输出一段简洁中文总结。"
        )
        user_content = (
            f"用户目标：{ctx.goal}\n"
            f"意图：{ctx.intent}\n"
            f"审批结果：approved={ctx.approved}, rejected={ctx.rejected}, note={ctx.approval_note}, "
            f"修订轮数={ctx.revision_count}\n"
            f"修改计划：{ctx.patch_plan}\n"
            f"执行结果：{ctx.apply_result}\n"
            f"验证结果：{ctx.verification_result}\n"
            f"日志：{ctx.logs}\n"
        )
        ctx.report = ask_llm_text(system_prompt, user_content)
        return "done"


__all__ = [
    "ApprovalNode",
    "ClassifyNode",
    "HitlReportNode",
    "InspectNode",
    "PlanNode",
    "RevisePlanNode",
    "SafeApplyNode",
    "VerifyNode",
]
