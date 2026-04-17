"""Task definitions for verilog coding environment.

Each task is created via scenario.task() and can be run locally or synced to the platform:

    hud sync tasks <slug>
    python local_test.py --list
    python local_test.py --task simple_counter
"""

from env import env, make_prompt, setup_task
from grading import AgentPatchGrader, Grade, ValidateMode

# =============================================================================
# Scenarios
# =============================================================================


@env.scenario("implement-counter", exclude_tools=["hud_validate"])
async def implement_counter(hints_enabled: bool = False, validate_mode: ValidateMode | None = None):
    """Implement a simple synchronous 8-bit counter with reset, enable, and load."""

    setup_task(
        task_id="simple_counter",
        base="simple_counter_baseline",
        test="simple_counter_test",
        golden="simple_counter_golden",
        validate_mode=validate_mode,
    )

    description = """Please implement a simple synchronous counter with reset, enable, set, and load functionality.

Inputs:
clk - Clock signal (triggers on rising edge)
rst - Synchronous reset signal
ena - Enable signal (allows counting)
set - Load signal (sets counter to a specific value)
din - 8-bit data input (value to load when set is high)

Output:
counter - 8-bit counter value"""

    if hints_enabled:
        description += (
            "\n\nHint: Use an always @(posedge clk) block. Check rst first (reset counter to 0),"
            " then set (load din into counter), then ena (increment counter by 1)."
        )

    prompt = make_prompt(description)
    _ = yield prompt

    grade = Grade.from_subscores(
        [
            AgentPatchGrader.grade(
                weight=1.0,
                problem_id="simple_counter",
                test_files=["tests/test_simple_counter_hidden.py"],
                validate_mode=validate_mode,
            )
        ]
    )
    yield grade.score


@env.scenario("implement-dff", exclude_tools=["hud_validate"])
async def implement_dff(hints_enabled: bool = False, validate_mode: ValidateMode | None = None):
    """Implement a simple D flip-flop with clock and data inputs."""

    setup_task(
        task_id="simple_dff",
        base="simple_dff_baseline",
        test="simple_dff_test",
        golden="simple_dff_golden",
        validate_mode=validate_mode,
    )

    description = """Please implement a simple digital flip-flop with a clock input and a data input.
The output should be the same as the data input on the rising edge of the clock.

Inputs:
clk - Clock signal (triggers on rising edge)
d - Data input

Output:
q - Output value"""

    if hints_enabled:
        description += "\n\nHint: Use always @(posedge clk) q <= d;"

    prompt = make_prompt(description)
    _ = yield prompt

    grade = Grade.from_subscores(
        [
            AgentPatchGrader.grade(
                weight=1.0,
                problem_id="simple_dff",
                test_files=["tests/test_simple_dff_hidden.py"],
                validate_mode=validate_mode,
            )
        ]
    )
    yield grade.score


# =============================================================================
# Task registry -- instantiate tasks from scenarios
# =============================================================================

_counter = implement_counter.task()
_counter.slug = "simple-counter"

_counter_hints = implement_counter.task(hints_enabled=True)
_counter_hints.slug = "simple-counter-hints"

_dff = implement_dff.task()
_dff.slug = "simple-dff"

_dff_hints = implement_dff.task(hints_enabled=True)
_dff_hints.slug = "simple-dff-hints"

# All tasks keyed by name for CLI discovery
ALL_TASKS = {
    "simple_counter": _counter,
    "simple_counter_hints": _counter_hints,
    "simple_dff": _dff,
    "simple_dff_hints": _dff_hints,
}

# Also expose as a flat list for hud sync tasks discovery
tasks = list(ALL_TASKS.values())
