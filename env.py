"""Verilog coding environment - tools for implementing and testing Verilog modules.

This environment provides tools for:
- Running bash commands in a sandboxed shell
- Editing files with view/create/edit commands
- Running shell commands (OpenAI shell spec)
- Applying patches in V4A diff format

Tools prefixed with _ are internal (hidden from agent, used by scenarios).
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from hud import Environment

from grading import ValidateMode
from hud_controller.tools.base import ToolError

logger = logging.getLogger(__name__)

# Create the environment
env = Environment("verilog-coding")

# Initialize tools
_bash_tool = None
_edit_tool = None
_shell_tool = None
_apply_patch_tool = None


def _get_project_dir() -> str:
    """Get the project directory path."""
    return f"/home/ubuntu/{os.environ.get('FOLDER_NAME', 'example-verilog-codebase')}"


@env.initialize
async def initialize() -> None:
    """Initialize the coding environment tools."""
    global _bash_tool, _edit_tool, _shell_tool, _apply_patch_tool

    from hud_controller.tools.bash import BashTool
    from hud_controller.tools.edit import EditTool
    from hud_controller.tools.shell import ShellTool
    from hud_controller.tools.apply_patch import ApplyPatchTool

    logger.info("Initializing verilog coding environment")
    _bash_tool = BashTool()
    _edit_tool = EditTool()
    _shell_tool = ShellTool()
    _apply_patch_tool = ApplyPatchTool(base_path=_get_project_dir())
    logger.info("Verilog coding environment initialized")


@env.shutdown
async def shutdown() -> None:
    """Clean up the coding environment."""
    global _bash_tool, _edit_tool, _shell_tool, _apply_patch_tool

    if _bash_tool and _bash_tool._session:
        _bash_tool._session.stop()

    _bash_tool = None
    _edit_tool = None
    _shell_tool = None
    _apply_patch_tool = None
    logger.info("Verilog coding environment shut down")


# ============================================================================
# Agent-Visible Tools
# ============================================================================


@env.tool()
async def bash(
    command: str | None = None,
    restart: bool = False,
) -> str:
    """Run a bash command in the sandboxed shell.

    Args:
        command: The bash command to execute
        restart: Whether to restart the bash session

    Returns:
        The command output or error message
    """
    if _bash_tool is None:
        return "Error: Bash tool not initialized"

    try:
        result = await _bash_tool(command=command, restart=restart)
        output = result.output or ""
        if result.error:
            output = f"{output}\n{result.error}".strip() if output else result.error
        return output or result.system or ""
    except ToolError as e:
        return f"Error: {e.message}"


@env.tool()
async def editor(
    command: str,
    path: str,
    file_text: str | None = None,
    view_range: list[int] | None = None,
    old_str: str | None = None,
    new_str: str | None = None,
    insert_line: int | None = None,
) -> str:
    """Edit files with view, create, edit, and undo operations.

    Args:
        command: One of 'view', 'create', 'str_replace', 'insert', 'undo_edit'
        path: Absolute path to the file
        file_text: Content for 'create' command
        view_range: [start_line, end_line] for 'view' command
        old_str: String to replace for 'str_replace' command
        new_str: Replacement string for 'str_replace' or 'insert'
        insert_line: Line number for 'insert' command

    Returns:
        The command result or file content
    """
    if _edit_tool is None:
        return "Error: Editor tool not initialized"

    try:
        result = await _edit_tool(
            command=command,  # type: ignore
            path=path,
            file_text=file_text,
            view_range=view_range,
            old_str=old_str,
            new_str=new_str,
            insert_line=insert_line,
        )
        if result.error:
            return f"Error: {result.error}"
        return result.output or ""
    except ToolError as e:
        return f"Error: {e.message}"


@env.tool()
async def shell(
    commands: list[str] | None = None,
    timeout_ms: int | None = None,
    max_output_length: int | None = None,
) -> str:
    """Run shell commands. Supports concurrent command execution with dynamic timeout and output length.

    Args:
        commands: List of shell commands to execute
        timeout_ms: Timeout in milliseconds for each command
        max_output_length: Max output length (passed back to API)

    Returns:
        JSON string of shell execution results
    """
    if _shell_tool is None:
        return "Error: Shell tool not initialized"

    try:
        result = await _shell_tool(
            commands=commands,
            timeout_ms=timeout_ms,
            max_output_length=max_output_length,
        )
        return json.dumps(result.to_dict())
    except ToolError as e:
        return f"Error: {e.message}"


@env.tool()
async def apply_patch(
    type: str | None = None,
    path: str | None = None,
    diff: str | None = None,
) -> str:
    """Create, update, or delete files using structured V4A diffs.

    Args:
        type: Operation type - "create_file", "update_file", or "delete_file"
        path: The file path to operate on
        diff: The V4A diff content (required for create_file and update_file)

    Returns:
        Status message of the patch operation
    """
    if _apply_patch_tool is None:
        return "Error: Apply patch tool not initialized"

    try:
        result = await _apply_patch_tool(
            type=type,
            path=path,
            diff=diff,
        )
        return json.dumps(result.to_dict())
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# Validation
# ============================================================================


@env.tool()
async def hud_validate() -> str:
    """Run the test suite to validate the environment is working correctly."""
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
# Scenario Helpers (called by @env.scenario functions in tasks/)
# ============================================================================


def setup_task(
    task_id: str,
    validate_mode: ValidateMode | None = None,
) -> None:
    """Set up environment for a task: checkout baseline, generate patches.

    Branch names are derived from *task_id* using the convention
    ``{task_id}_baseline``, ``{task_id}_test``, ``{task_id}_golden``.

    Args:
        task_id: Unique identifier for the task (e.g. "simple_counter").
        validate_mode: "baseline_fail" or "golden_pass" for validation.
    """
    base = f"{task_id}_baseline"
    test = f"{task_id}_test"
    golden = f"{task_id}_golden"

    project_dir = _get_project_dir()
    patches_dir = os.environ.get("PATCHES_DIR", "/home/root/patches")

    # Set PROBLEM_ID env var for grading runner
    os.environ["PROBLEM_ID"] = task_id

    # Generate patches at runtime
    task_patches_dir = os.path.join(patches_dir, task_id)
    os.makedirs(task_patches_dir, exist_ok=True)

    # Generate test.patch (base -> test)
    logger.info("Generating test.patch: %s -> %s", base, test)
    result = subprocess.run(
        ["git", "diff", f"origin/{base}", f"origin/{test}"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    with open(os.path.join(task_patches_dir, "test.patch"), "w") as f:
        f.write(result.stdout)

    # Generate golden.patch (base -> golden)
    logger.info("Generating golden.patch: %s -> %s", base, golden)
    result = subprocess.run(
        ["git", "diff", f"origin/{base}", f"origin/{golden}"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    with open(os.path.join(task_patches_dir, "golden.patch"), "w") as f:
        f.write(result.stdout)

    # Checkout the appropriate branch
    if validate_mode == "golden_pass":
        logger.info("Checking out golden branch (validation): %s", golden)
        checkout_branch = golden
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
        # Restore file ownership to ubuntu
        subprocess.run(["chown", "-R", "ubuntu:ubuntu", project_dir], capture_output=True)
        # Keep .git protected
        subprocess.run(["chown", "-R", "root:root", os.path.join(project_dir, ".git")], capture_output=True)

    os.chdir(project_dir)


def make_prompt(description: str) -> str:
    """Generate a prompt from a task description.

    Args:
        description: The task description

    Returns:
        Formatted prompt string
    """
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
# Import and register all scenarios from tasks/
# ============================================================================

import tasks  # noqa: E402, F401 - registers scenarios
