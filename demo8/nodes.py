from __future__ import annotations

from dataclasses import dataclass

from demo6.framework import ask_llm_json, ask_llm_text
from demo8.example_context import CodeWorkflowContext
from demo8.framework import BaseWorkflowNode
from demo8.tools import list_files, read_text_file, replace_text_in_file, search_text, write_text_file


@dataclass
class ClassifyNode(BaseWorkflowNode):
    """
    把用户目标分类为 summary / edit。

    这是 workflow 的第一步：
    先把任务分成“只读观察”还是“需要修改”两类，
    后面的节点再走不同路径。
    """

    def run(self, ctx: CodeWorkflowContext) -> str:
        system_prompt = (
            "你是一个 workflow 分类器。"
            "请根据用户目标输出 JSON，字段如下："
            "intent (summary 或 edit), target_file, search_query, reason。"
            "如果用户明显要求修改代码或文件，intent 选择 edit。"
            "如果用户只是想了解、总结或检查，intent 选择 summary。"
        )
        data = ask_llm_json(system_prompt, f"用户目标：{ctx.goal}")

        ctx.intent = str(data.get("intent") or "edit")
        ctx.target_file = data.get("target_file") or None
        ctx.search_query = data.get("search_query") or None
        ctx.logs.append(f"classify={data}")
        return "inspect"


@dataclass
class InspectNode(BaseWorkflowNode):
    """
    先观察工作区。

    workflow 的第二步先看：
    - 当前目录有什么
    - 目标文件长什么样
    - 搜索关键词命中了哪些地方
    """

    def run(self, ctx: CodeWorkflowContext) -> str:
        listing = list_files(str(ctx.workspace_dir), ".")
        ctx.logs.append(f"workspace_list_count={len(listing.get('items', []))}")

        if ctx.search_query:
            hits = search_text(str(ctx.workspace_dir), ctx.search_query, ".")
            ctx.search_hits = hits.get("matches", [])
            ctx.logs.append(f"search_hits={len(ctx.search_hits)}")

        if ctx.target_file:
            ctx.file_snapshot = read_text_file(str(ctx.workspace_dir), ctx.target_file)
            ctx.logs.append(f"snapshot_path={ctx.file_snapshot.get('path')}")

        if ctx.intent == "summary":
            return "report"
        return "plan"


@dataclass
class PlanNode(BaseWorkflowNode):
    """
    让模型根据观察结果生成一个具体修改计划。

    这一步的目标不是让模型直接修改，而是先把修改意图收敛成
    可执行的 patch plan。
    """

    def run(self, ctx: CodeWorkflowContext) -> str:
        system_prompt = (
            "你是一个 workflow 规划器。"
            "根据用户目标、文件快照和搜索结果，输出 JSON。"
            "字段如下：relative_path, old_text, new_text, expected_occurrences, rationale。"
            "只做一个小而精确的改动。"
        )
        user_content = (
            f"用户目标：{ctx.goal}\n"
            f"目标文件：{ctx.target_file}\n"
            f"文件快照：{ctx.file_snapshot}\n"
            f"搜索结果：{ctx.search_hits}\n"
        )
        plan = ask_llm_json(system_prompt, user_content)
        ctx.patch_plan = plan
        ctx.logs.append(f"plan={plan}")
        # 练习一：计划不再直接进 apply，而是先过一道风险检查。
        return "risk_check"


@dataclass
class RiskCheckNode(BaseWorkflowNode):
    """
    在 apply 之前做一次风险检查（练习一）。

    检查分两层：
    - 硬校验（程序做，便宜且确定）：
      目标文件是否可读、old_text 当前实际出现几次、
      是否和计划声明的 expected_occurrences 一致
    - 软评估（模型做）：改动范围、是否可能影响其他调用方

    只有硬校验全部通过、且模型评估不是 high 风险，才放行到 apply；
    否则直接跳 report 汇报拦截原因，修改不会执行。
    """

    def run(self, ctx: CodeWorkflowContext) -> str:
        plan = ctx.patch_plan
        relative_path = str(plan.get("relative_path") or ctx.target_file or "")
        old_text = str(plan.get("old_text") or "")
        new_text = str(plan.get("new_text") or "")

        hard_checks: dict[str, Any] = {
            "target_file_known": bool(relative_path),
            "has_edit_texts": bool(old_text) and bool(new_text),
        }

        if relative_path and old_text:
            current = read_text_file(str(ctx.workspace_dir), relative_path)
            if current.get("ok"):
                actual = str(current.get("content")).count(old_text)
                expected = plan.get("expected_occurrences")
                hard_checks["old_text_occurrences"] = actual
                # expected 缺失或与实际不一致都视为不过：计划必须自证清楚。
                hard_checks["occurrences_match"] = (
                    expected is not None and int(expected) == actual
                )
            else:
                hard_checks["file_readable"] = False

        hard_checks_passed = all(bool(value) for value in hard_checks.values())

        system_prompt = (
            "你是一个 workflow 风险评估器。"
            "根据修改计划和硬校验结果输出 JSON，字段如下："
            "risk_level (low / medium / high), reasons。"
            "改动小而精确、只影响局部逻辑时是 low；"
            "可能影响多个调用方、删除既有逻辑、大范围重写时升高。"
        )
        user_content = (
            f"用户目标：{ctx.goal}\n"
            f"修改计划：{plan}\n"
            f"硬校验结果：{hard_checks}\n"
        )
        assessment = ask_llm_json(system_prompt, user_content)
        risk_level = str(assessment.get("risk_level") or "medium").lower()

        ctx.risk_assessment = {
            "hard_checks": hard_checks,
            "hard_checks_passed": hard_checks_passed,
            "risk_level": risk_level,
            "reasons": assessment.get("reasons"),
        }
        ctx.logs.append(
            f"risk_check passed={hard_checks_passed}, level={risk_level}"
        )

        if not hard_checks_passed or risk_level == "high":
            return "report"
        return "apply"


@dataclass
class ApplyNode(BaseWorkflowNode):
    """执行修改计划。"""

    def run(self, ctx: CodeWorkflowContext) -> str:
        relative_path = str(ctx.patch_plan.get("relative_path") or ctx.target_file or "")
        old_text = str(ctx.patch_plan.get("old_text") or "")
        new_text = str(ctx.patch_plan.get("new_text") or "")
        expected_occurrences = int(ctx.patch_plan.get("expected_occurrences") or 1)

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
class VerifyNode(BaseWorkflowNode):
    """读取文件并确认修改结果。"""

    def run(self, ctx: CodeWorkflowContext) -> str:
        if not ctx.apply_result.get("ok"):
            ctx.verification_result = {"ok": False, "error": "apply failed"}
            ctx.verification_summary = "修改未执行成功，没有可验证的内容。"
            return "report"

        path = str(ctx.apply_result.get("path") or ctx.target_file or "")
        snapshot = read_text_file(str(ctx.workspace_dir), path)
        ctx.verification_result = snapshot
        ctx.logs.append(f"verification={snapshot.get('ok')}")

        # 练习三：验证节点多做一步“结果总结”。
        # 先做一次廉价的硬校验（旧文本应消失、新文本应出现），
        # 再让模型把验证结论写成一段用户可读的总结。
        checks: dict[str, Any] = {}
        if snapshot.get("ok"):
            content = str(snapshot.get("content") or "")
            old_text = str(ctx.patch_plan.get("old_text") or "")
            new_text = str(ctx.patch_plan.get("new_text") or "")
            if old_text:
                checks["old_text_gone"] = old_text not in content
            if new_text:
                checks["new_text_present"] = new_text in content
        ctx.verification_checks = checks
        ctx.logs.append(f"verification_checks={checks}")

        system_prompt = (
            "你是一个 workflow 验证结果总结器。"
            "基于硬校验结果和读回的文件内容，输出两三句中文结论："
            "修改是否生效、是否和计划一致、有没有可疑之处。"
        )
        user_content = (
            f"用户目标：{ctx.goal}\n"
            f"修改计划：{ctx.patch_plan}\n"
            f"硬校验：{checks}\n"
            f"读回内容（截断）：{str(snapshot.get('content'))[:2000]}\n"
        )
        ctx.verification_summary = ask_llm_text(system_prompt, user_content)
        return "report"


@dataclass
class ReportNode(BaseWorkflowNode):
    """
    把 workflow 过程总结成最终答案。

    最终输出不是工具日志，而是对用户可读的简短结果。
    """

    def run(self, ctx: CodeWorkflowContext) -> str:
        system_prompt = (
            "你是一个 workflow 报告生成器。"
            "基于执行日志、修改结果和验证结果，输出一段简洁中文总结。"
        )
        user_content = (
            f"用户目标：{ctx.goal}\n"
            f"意图：{ctx.intent}\n"
            f"修改计划：{ctx.patch_plan}\n"
            f"风险检查：{ctx.risk_assessment}\n"
            f"执行结果：{ctx.apply_result}\n"
            f"验证结果：{ctx.verification_result}\n"
            f"硬校验：{ctx.verification_checks}\n"
            f"验证总结：{ctx.verification_summary}\n"
            f"日志：{ctx.logs}\n"
        )
        ctx.report = ask_llm_text(system_prompt, user_content)
        return "done"
