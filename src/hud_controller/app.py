import asyncio
import logging
import os

import click
from mcp.server.fastmcp import FastMCP  # type: ignore
from mcp.types import ImageContent, TextContent  # type: ignore
from pydantic import Field

import hud_controller.problems
from hud_controller.grading_runner import GradingRunner
from hud_controller.utils import import_submodules

from .setup import start_dinit
from .spec import PROBLEM_REGISTRY, Grade, ProblemSpec
from .tools.base import ToolResult

logger = logging.getLogger(__name__)

# [CUSTOMIZE] Set your MCP server name
mcp = FastMCP("agent_evaluation", log_level="DEBUG", debug=True)

TEST_MODE = os.environ.get("MCP_TESTING_MODE", "1") in ["1", "true"]

if TEST_MODE:
    # Note, these tools are only available in testing mode for the purpose of testing
    # If the enviroment performs well with these tools, it will also work with our internal
    # implementation

    from .tools.bash import BashTool
    from .tools.edit import Command, EditTool

    edit_tool = EditTool()
    bash_tool = BashTool()

    @mcp.tool(
        name="str_replace_editor",
        description="Create and edit files using str_replace_editor.  Please use absolute paths for all file names.",
    )
    async def str_replace_editor(
        *,
        command: Command,
        path: str,
        file_text: str | None = None,
        view_range: list[int] | None = None,
        old_str: str | None = None,
        new_str: str | None = None,
        insert_line: int | None = None,
    ) -> ToolResult:
        """Edit or create files using string replacement operations.

        Args:
            command (Command): The edit command to perform (e.g., create, edit, view)
            path (str): Absolute path to the target file
            file_text (str | None, optional): Content to write when creating a new file. Defaults to None.
            view_range (list[int] | None, optional): Line range to view [start, end]. Defaults to None.
            old_str (str | None, optional): String to replace when editing. Defaults to None.
            new_str (str | None, optional): Replacement string when editing. Defaults to None.
            insert_line (int | None, optional): Line number for insertion. Defaults to None.

        Returns:
            ToolResult: Result of the edit operation
        """
        return await edit_tool(
            command=command,
            path=path,
            file_text=file_text,
            view_range=view_range,
            old_str=old_str,
            new_str=new_str,
            insert_line=insert_line,
        )

    @mcp.tool(
        name="bash",
        description="Run bash commands. If you need to restart the bash session, set restart to true.",
    )
    async def bash(*, command: str, restart: bool = False) -> ToolResult:
        return await bash_tool(
            command=command,
            restart=restart,
        )

# import all submodules
# Import all problem modules to ensure problems are registered
import_submodules(hud_controller.problems)


# [CUSTOMIZE] Update this template for your project
template = """
You will be working on a task for example-verilog-codebase.
The repository has already been cloned in the environment in /home/ubuntu/example-verilog-codebase.
Iverilog and Verilator have been installed.
Do not change any of the inpute or output ports of the modules.
Do not change any files outside of the source/ directory.
Use the tools provided to complete the following task:

<STATEMENT>
"""

def spec_to_statement(spec: ProblemSpec) -> str:
    """
    Convert a problem spec to a statement.
    """
    hints_enabled = os.environ.get("HINTS", "none").lower() in ["all"]
    statement = spec.description
    
    if hints_enabled and len(spec.hints) > 0:
        hint_text = ""
        for hint_spec in spec.hints:
            hint_text += f"\n - {hint_spec.text}\n"
        statement += "\n\n" + f"<HINTS>{hint_text}</HINTS>"
    return template.replace("<STATEMENT>", statement)


# helper to lookup a problem spec by id
def _get_spec(problem_id: str) -> ProblemSpec:
    for spec in PROBLEM_REGISTRY:
        if spec.id == problem_id:
            return spec
    raise ValueError(f"No problem found for id: {problem_id}")


# Implementation notes: setup_problem will only be called once per enviroment instance
@mcp.tool()
async def setup_problem(
    problem_id: str = Field(description="The id of the problem to solve"),
) -> str:
    """Starts the enviroment and returns the problem statement"""
    spec = _get_spec(problem_id)

    logger.info(f"=== SETUP_PROBLEM DEBUG ===")
    logger.info(f"Problem ID: {problem_id}")
    logger.info(f"Spec: {spec}")

    # Start the dinit services
    await start_dinit()
    # create the full statement
    return spec_to_statement(spec)


@click.command()
@click.argument("problem_id")
def setup_problem_script(problem_id: str):
    """Set up a problem environment and return the problem statement."""
    statement = asyncio.run(setup_problem(problem_id))
    print(statement)


# Implementation note: grade_problem will only be called once per enviroment instance
@mcp.tool()
async def grade_problem(
    problem_id: str,
    transcript: str | int = Field(description="The entire transcript produced by the model and its tool calls"),
) -> Grade:
    """Check your solution for grading. Returns a Grade object making sure to include all components that make up the score as subscores."""

    spec = _get_spec(problem_id)
    runner = GradingRunner(
        base=spec.base,
        test=spec.test,
        golden=spec.golden,
    )

    success, result = runner.run_grading()

    if success:
        logger.info("Grading successful!")
    else:
        logger.error("Grading failed!")

    grade = Grade(
        subscores={"Tests": 1.0 if success else 0.0},
        weights={"Tests": 1.0},
        metadata=result,
    )

    return grade


@click.command()
@click.argument("problem_id", envvar="PROBLEM_ID")
@click.option("--only-server", is_flag=True, help="Only start the server and wait for it to be ready")
@click.option("--output_path", default="/tmp/grade_junit.xml", help="Path to output the JUNIT XML file")
def grade_problem_script(
    problem_id: str,
    output_path: str = None,
):
    """Grade a problem solution and return the grade results."""
    transcript = "dummy transcript"
    grade = asyncio.run(grade_problem(problem_id, transcript))
    with open(output_path, "w") as f:
        f.write(grade.metadata["AgentPatchGrader"]["junit"])
    print(grade)



async def validate_problem(problem_id: str) -> tuple[bool, dict[str, any]]:
    """Validate the test and golden patches for a problem."""

    # Get the problem specification
    spec = _get_spec(problem_id)

    # Check if required branch/commit info is available
    if not spec.base:
        raise ValueError(f"Problem {problem_id} missing base branch/commit")
    if not spec.test:
        raise ValueError(f"Problem {problem_id} missing test branch/commit")
    if not spec.golden:
        raise ValueError(f"Problem {problem_id} missing golden branch/commit")

    logger.info("=== VALIDATE_PROBLEM DEBUG ===")
    logger.info(f"Problem ID: {problem_id}")
    logger.info(f"Base: {spec.base}")
    logger.info(f"Test: {spec.test}")
    logger.info(f"Golden: {spec.golden}")

    # Create grading runner with the problem's branch/commit info
    runner = GradingRunner(
        base=spec.base,
        test=spec.test,
        golden=spec.golden,
    )

    success, result = runner.validate_patches()

    if success:
        logger.info("Validation successful!")
    else:
        logger.error("Validation failed!")

    # Print the JUnit XML result if available
    if "junit" in result:
        print("\nJUnit XML Result:")
        print(result["junit"])

    return success, result



@click.command()
@click.argument("problem_id", envvar="PROBLEM_ID")
@click.option("--output_path", default="/tmp/validate_junit.xml", help="Path to output the JUNIT XML file")
def validate_problem_script(
    problem_id: str,
    output_path: str = None,
):
    """Validate a problem solution and return the validation results."""
    asyncio.run(validate_problem(problem_id))

@click.command()
def main():
    # Initialize and run the server as root; you can use files and services that require root permissions
    # once init is done, the server will run as the model user to prevent it from accessing problem data
    mcp.run(transport="stdio")
