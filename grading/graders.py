"""Graders for evaluating agent solutions."""

import asyncio
import os
from typing import Literal

from hud.native.graders import Grader

from .runner import GradingRunner

ValidateMode = Literal["baseline_fail", "golden_pass"]


class AgentPatchGrader(Grader):
    """Grader that applies test.patch and runs tests.

    Usage:
        await AgentPatchGrader.grade(
            weight=1.0,
            problem_id="my_task",
            test_files=["tests/test_foo.py"],
        )

    Custom test command:
        await AgentPatchGrader.grade(
            weight=1.0,
            problem_id="my_task",
            test_files=["tests/test_foo.py"],
            test_command="uv run --no-sync pytest {test_files}",
        )
    """

    name = "AgentPatchGrader"
    DEFAULT_TEST_COMMAND = "uv run --no-sync pytest {test_files}"

    @classmethod
    async def compute_score(
        cls,
        test_files: list[str],
        problem_id: str | None = None,
        test_command: str | None = None,
        validate_mode: ValidateMode | None = None,
        **kwargs,
    ) -> tuple[float, dict]:
        """Run tests and return score.

        Args:
            test_files: Test files to run
            problem_id: Problem ID for patches (default: PROBLEM_ID env)
            test_command: Test command with {test_files} placeholder
            validate_mode: If "baseline_fail", invert the score

        Returns:
            (score, metadata) - score is 1.0 if tests pass, 0.0 otherwise
        """
        pid = problem_id or os.environ.get("PROBLEM_ID")
        if not pid:
            raise ValueError("problem_id required (or set PROBLEM_ID env)")

        runner = GradingRunner(
            problem_id=pid,
            test_command=test_command or cls.DEFAULT_TEST_COMMAND,
            test_files=test_files,
        )

        score = await asyncio.to_thread(runner.grade)

        if validate_mode == "baseline_fail":
            score = 1.0 if score == 0.0 else 0.0

        return (score, {})
