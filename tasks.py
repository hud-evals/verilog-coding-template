"""Task definitions for verilog coding environment.

One generic ``verilog_task`` scenario accepts all task content as parameters
(description, test files). Each ``.task()`` call produces a distinct task by
passing different values — no new scenario function needed.

Branch names are derived from ``task_id`` by convention:
``{task_id}_baseline``, ``{task_id}_test``, ``{task_id}_golden``.

    hud sync tasks <slug>
    python local_test.py --list
    python local_test.py --task simple_counter
"""

from env import env, make_prompt, setup_task
from grading import AgentPatchGrader, Grade, ValidateMode


# =============================================================================
# Scenario — generic Verilog implementation template
# =============================================================================


@env.scenario("verilog-task", exclude_tools=["hud_validate"])
async def verilog_task(
    task_id: str,
    description: str,
    test_files: list[str],
    validate_mode: ValidateMode | None = None,
):
    """Implement a Verilog module from a specification.

    All task-specific content is passed as parameters, making this scenario
    a reusable template.

    Branch names are derived from *task_id* by convention:
    ``{task_id}_baseline``, ``{task_id}_test``, ``{task_id}_golden``.

    Args:
        task_id: Unique identifier (e.g. "simple_counter").
        description: Task description shown to the agent.
        test_files: List of test file paths applied via patch.
        validate_mode: "baseline_fail" or "golden_pass" for validation.
    """
    setup_task(
        task_id=task_id,
        validate_mode=validate_mode,
    )

    prompt = make_prompt(description)
    _ = yield prompt

    grade = Grade.from_subscores(
        [
            AgentPatchGrader.grade(
                weight=1.0,
                problem_id=task_id,
                test_files=test_files,
                validate_mode=validate_mode,
            )
        ]
    )
    yield grade.score


# =============================================================================
# Tasks
# =============================================================================

_counter = verilog_task.task(
    task_id="simple_counter",
    description=(
        "Please implement a simple synchronous counter with reset, enable, set, "
        "and load functionality.\n\n"
        "Inputs:\n"
        "clk - Clock signal (triggers on rising edge)\n"
        "rst - Synchronous reset signal\n"
        "ena - Enable signal (allows counting)\n"
        "set - Load signal (sets counter to a specific value)\n"
        "din - 8-bit data input (value to load when set is high)\n\n"
        "Output:\n"
        "counter - 8-bit counter value"
    ),
    test_files=["tests/test_simple_counter_hidden.py"],
)
_counter.slug = "simple-counter"

_counter_hints = verilog_task.task(
    task_id="simple_counter",
    description=(
        "Please implement a simple synchronous counter with reset, enable, set, "
        "and load functionality.\n\n"
        "Inputs:\n"
        "clk - Clock signal (triggers on rising edge)\n"
        "rst - Synchronous reset signal\n"
        "ena - Enable signal (allows counting)\n"
        "set - Load signal (sets counter to a specific value)\n"
        "din - 8-bit data input (value to load when set is high)\n\n"
        "Output:\n"
        "counter - 8-bit counter value\n\n"
        "Hint: Use an always @(posedge clk) block. Check rst first (reset counter to 0),"
        " then set (load din into counter), then ena (increment counter by 1)."
    ),
    test_files=["tests/test_simple_counter_hidden.py"],
)
_counter_hints.slug = "simple-counter-hints"

_dff = verilog_task.task(
    task_id="simple_dff",
    description=(
        "Please implement a simple digital flip-flop with a clock input and a data input.\n"
        "The output should be the same as the data input on the rising edge of the clock.\n\n"
        "Inputs:\n"
        "clk - Clock signal (triggers on rising edge)\n"
        "d - Data input\n\n"
        "Output:\n"
        "q - Output value"
    ),
    test_files=["tests/test_simple_dff_hidden.py"],
)
_dff.slug = "simple-dff"

_dff_hints = verilog_task.task(
    task_id="simple_dff",
    description=(
        "Please implement a simple digital flip-flop with a clock input and a data input.\n"
        "The output should be the same as the data input on the rising edge of the clock.\n\n"
        "Inputs:\n"
        "clk - Clock signal (triggers on rising edge)\n"
        "d - Data input\n\n"
        "Output:\n"
        "q - Output value\n\n"
        "Hint: Use always @(posedge clk) q <= d;"
    ),
    test_files=["tests/test_simple_dff_hidden.py"],
)
_dff_hints.slug = "simple-dff-hints"

# =============================================================================
# Task registry — keyed by name for CLI discovery
# =============================================================================

ALL_TASKS = {
    "simple_counter": _counter,
    "simple_counter_hints": _counter_hints,
    "simple_dff": _dff,
    "simple_dff_hints": _dff_hints,
}

# Also expose as a flat list for hud sync tasks discovery
tasks = list(ALL_TASKS.values())
