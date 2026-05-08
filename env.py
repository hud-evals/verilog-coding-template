"""Verilog coding environment.

Tools (bash/shell/edit/apply_patch) come from the HUD SDK directly. The
verilog-task scenario sets up baseline/test/golden branches and grades by
applying test.patch + running pytest in a copy of the repo, via BashGrader.
"""

import logging
import os
import subprocess
import uuid
from typing import Literal

from hud import Environment
from hud.native.graders import BashGrader, Grade
from hud.tools.coding import ApplyPatchTool, BashTool, EditTool, ShellTool
from hud.tools.types import SubScore

logger = logging.getLogger(__name__)

ValidateMode = Literal["baseline_fail", "golden_pass"]

env = Environment("verilog-coding")


def _get_project_dir() -> str:
    """Get the project directory path."""
    return f"/home/ubuntu/{os.environ.get('FOLDER_NAME', 'example-verilog-codebase')}"


# ============================================================================
# Agent-Visible Tools (registered directly from the SDK)
# ============================================================================

env.add_tool(BashTool())
env.add_tool(ShellTool())
env.add_tool(EditTool())
env.add_tool(ApplyPatchTool(base_path=_get_project_dir()))


@env.tool()
async def hud_validate() -> str:
    """Run the test suite to validate the environment is working correctly."""
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd="/mcp_server",
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(output or f"pytest exited with code {result.returncode}")
    return output


# ============================================================================
# Scenario helpers
# ============================================================================


def setup_task(
    task_id: str,
    validate_mode: ValidateMode | None = None,
) -> None:
    """Check out the right branch and generate test/golden patches at runtime.

    Branch names are derived from *task_id* by the convention
    ``{task_id}_baseline``, ``{task_id}_test``, ``{task_id}_golden``.
    """
    base = f"{task_id}_baseline"
    test = f"{task_id}_test"
    golden = f"{task_id}_golden"

    project_dir = _get_project_dir()
    patches_dir = os.environ.get("PATCHES_DIR", "/home/root/patches")
    os.environ["PROBLEM_ID"] = task_id

    task_patches_dir = os.path.join(patches_dir, task_id)
    os.makedirs(task_patches_dir, exist_ok=True)

    logger.info("Generating test.patch: %s -> %s", base, test)
    result = subprocess.run(
        ["git", "diff", f"origin/{base}", f"origin/{test}"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    with open(os.path.join(task_patches_dir, "test.patch"), "w") as f:
        f.write(result.stdout)

    logger.info("Generating golden.patch: %s -> %s", base, golden)
    result = subprocess.run(
        ["git", "diff", f"origin/{base}", f"origin/{golden}"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    with open(os.path.join(task_patches_dir, "golden.patch"), "w") as f:
        f.write(result.stdout)

    if validate_mode == "golden_pass":
        checkout_branch = golden
        logger.info("Checking out golden branch (validation): %s", golden)
    else:
        checkout_branch = base
        logger.info("Checking out baseline branch: %s", checkout_branch)

    result = subprocess.run(
        ["git", "checkout", "-f", f"origin/{checkout_branch}"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("Failed to checkout %s: %s", checkout_branch, result.stderr)
    else:
        logger.info("Checked out branch: %s", checkout_branch)
        subprocess.run(["chown", "-R", "ubuntu:ubuntu", project_dir], capture_output=True)
        subprocess.run(
            ["chown", "-R", "root:root", os.path.join(project_dir, ".git")],
            capture_output=True,
        )

    os.chdir(project_dir)


def make_prompt(description: str) -> str:
    """Format a task description into a full agent prompt."""
    folder_name = os.environ.get("FOLDER_NAME", "example-verilog-codebase")
    return f"""You will be working on a task for {folder_name}.
The repository has already been cloned in the environment in /home/ubuntu/{folder_name}.
Iverilog and Verilator have been installed.
Do not change any of the input or output ports of the modules.

You should write verilog testbenches to test your code and ensure it matches the functional specification (in addition to syntactic correctness).

Use the tools provided to complete the following task:

{description}
"""


# ============================================================================
# Scenario
# ============================================================================


@env.scenario("verilog-task", exclude_tools=["hud_validate"])
async def verilog_task(
    task_id: str,
    description: str,
    test_files: list[str],
    validate_mode: ValidateMode | None = None,
):
    """Implement a Verilog module from a specification.

    Branch names are derived from *task_id* by convention:
    ``{task_id}_baseline``, ``{task_id}_test``, ``{task_id}_golden``.

    Args:
        task_id: Unique identifier (e.g. "simple_counter").
        description: Task description shown to the agent.
        test_files: List of test file paths applied via patch.
        validate_mode: "baseline_fail" or "golden_pass" for validation.
    """
    setup_task(task_id=task_id, validate_mode=validate_mode)
    _ = yield make_prompt(description)

    project_dir = _get_project_dir()
    workdir = f"/tmp/grade_{task_id}_{uuid.uuid4().hex[:8]}"
    patches_dir = os.environ.get("PATCHES_DIR", "/home/root/patches")
    test_patch = f"{patches_dir}/{task_id}/test.patch"
    cmd = (
        f"cp -rT {project_dir} {workdir} && "
        f"cd {workdir} && "
        f"git update-index --refresh > /dev/null 2>&1; "
        f"git apply --verbose < {test_patch} && "
        f"uv run --no-sync pytest {' '.join(test_files)}"
    )

    sub = await BashGrader.grade(weight=1.0, command=cmd, timeout_seconds=600)
    if validate_mode == "baseline_fail":
        sub = SubScore(
            name=sub.name,
            weight=sub.weight,
            value=1.0 - sub.value,
            metadata=sub.metadata,
        )
    yield await Grade.gather(sub)
