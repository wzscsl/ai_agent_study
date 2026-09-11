from __future__ import annotations

import contextlib
import hashlib
import io
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from demo6.framework import MessageStore, ToolRegistry, get_api_key

from demo7.coding_runtime import CodingAgentRuntime
from demo7.coding_tools import register_coding_tools
from demo7.config import WORKSPACE_DIR as DEMO7_WORKSPACE

from demo8.config import WORKSPACE_DIR as DEMO8_WORKSPACE
from demo8.example_context import CodeWorkflowContext
from demo8.workflow_demo import build_workflow


def snapshot_files(root: Path) -> dict[str, str]:
    """给工作区拍一个“文件名 -> 内容哈希”的快照，用于对比前后变化。"""
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            key = str(path.relative_to(root)).replace("\\", "/")
            snapshot[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """对比两次快照，返回发生变化的文件。"""
    changed = [
        name
        for name, digest in after.items()
        if before.get(name) != digest
    ]
    changed.extend(f"{name} (deleted)" for name in before if name not in after)
    return changed


def run_fixed_workflow(goal: str) -> dict[str, object]:
    """跑 demo8 的固定 workflow，返回耗时、步骤、结果。"""
    ctx = CodeWorkflowContext(goal=goal, workspace_dir=DEMO8_WORKSPACE)
    workflow = build_workflow()

    started = time.perf_counter()
    result = workflow.run(ctx)
    elapsed = time.perf_counter() - started

    step_logs = [line for line in result.logs if line.startswith("step=")]
    return {
        "elapsed": elapsed,
        "steps": [line.split("node=")[1] for line in step_logs],
        "report": result.report or "(无报告)",
        "risk": result.risk_assessment,
        "checks": result.verification_checks,
    }


def run_free_agent(goal: str, api_key: str) -> dict[str, object]:
    """跑 demo7 的自由 agent，返回耗时、循环数、结果。"""
    registry = ToolRegistry()
    register_coding_tools(registry)
    runtime = CodingAgentRuntime(api_key=api_key, tool_registry=registry)
    message_store = MessageStore(max_turns=6)
    message_store.append({"role": "user", "content": goal})

    # demo7 的 runtime 会往 stdout 打印工具调用过程，
    # 这里捕获下来用于统计循环数和工具调用数。
    buffer = io.StringIO()
    started = time.perf_counter()
    try:
        with contextlib.redirect_stdout(buffer):
            answer = runtime.run(goal=goal, message_store=message_store)
        error: str | None = None
    except Exception as exc:  # noqa: BLE001 - 对比脚本要如实记录失败
        answer, error = "", str(exc)
    elapsed = time.perf_counter() - started

    output = buffer.getvalue()
    loop_indexes = [
        int(line.split("[循环 ")[1].split("]")[0])
        for line in output.splitlines()
        if "[循环 " in line
    ]
    tool_calls = sum(1 for line in output.splitlines() if "模型选择工具" in line)

    return {
        "elapsed": elapsed,
        "loops": max(loop_indexes, default=0),
        "tool_calls": tool_calls,
        "answer": answer or "(未产出答复)",
        "error": error,
    }


def main() -> None:
    api_key = get_api_key()

    goal = sys.argv[1] if len(sys.argv) > 1 else input("\n请输入对比任务：").strip()
    if not goal:
        print("请输入任务目标。")
        return

    print(f"\n对比任务：{goal}")
    print(f"自由 agent 工作区：{DEMO7_WORKSPACE}")
    print(f"固定 workflow 工作区：{DEMO8_WORKSPACE}")
    print("注意：两个工作区的文件都会被真实修改。")

    before_7 = snapshot_files(DEMO7_WORKSPACE)
    before_8 = snapshot_files(DEMO8_WORKSPACE)

    print("\n=== 固定 workflow（demo8）运行中... ===")
    workflow_result = run_fixed_workflow(goal)
    changed_8 = changed_files(before_8, snapshot_files(DEMO8_WORKSPACE))

    print("=== 自由 agent（demo7）运行中... ===")
    agent_result = run_free_agent(goal, api_key)
    changed_7 = changed_files(before_7, snapshot_files(DEMO7_WORKSPACE))

    print("\n--- 对比结果 ---")
    print(f"固定 workflow：耗时 {workflow_result['elapsed']:.1f}s")
    print(f"  步骤（固定路径）：{' -> '.join(str(s) for s in workflow_result['steps'])}")
    print(f"  风险检查：{workflow_result['risk']}")
    print(f"  验证硬校验：{workflow_result['checks']}")
    print(f"  改动文件：{changed_8 or '无'}")

    print(f"自由 agent：耗时 {agent_result['elapsed']:.1f}s")
    print(f"  循环数：{agent_result['loops']}，工具调用：{agent_result['tool_calls']} 次")
    print(f"  改动文件：{changed_7 or '无'}")
    if agent_result["error"]:
        print(f"  执行失败：{agent_result['error']}")

    print("\n--- 固定 workflow 的最终报告 ---")
    print(workflow_result["report"])
    print("\n--- 自由 agent 的最终答复 ---")
    print(agent_result["answer"])

    print(
        "\n提示：把同一个任务多跑几遍。workflow 的步骤路径每次都一样；"
        "自由 agent 的循环数和工具调用顺序可能会变——这就是两种形态最直观的差异。"
    )


if __name__ == "__main__":
    main()
