"""Golden / baseline grading validation (v6, no agent).

For each task we build a ``validate_mode`` variant of the template and drive it with the
no-agent ``Run`` driver: setup runs on context enter, grading on exit. We assert:

  * golden  -> the reference solution passes the hidden tests           -> reward 1.0
  * baseline -> the empty skeleton fails the hidden tests (inverted)    -> reward 1.0

The cocotb tests run through Icarus Verilog, so run this against an env that has the
toolchain (the built image): ``pytest tests/ -v --runtime tcp://127.0.0.1:8765``.

Note: ``test_baseline_fails`` inverts a pytest failure to 1.0, so a missing-iverilog
*infrastructure* error would also invert to 1.0 (a false green). Always run it together
with ``test_golden_passes``: golden is the infra canary; if the toolchain is broken,
golden fails, surfacing the problem. Do not run only the baseline tests.

    pytest tests/test_grading.py -v --runtime tcp://127.0.0.1:8765
    pytest tests/test_grading.py -v -k simple_counter --runtime tcp://127.0.0.1:8765
"""

import pytest
from hud import Run, connect

from env import verilog_task

# (task_id, hidden test files); hint variants share branches/grading, so we validate once.
TASKS = [
    ("simple_counter", ["tests/test_simple_counter_hidden.py"]),
    ("simple_dff", ["tests/test_simple_dff_hidden.py"]),
]


async def _grade(runtime, task) -> float:
    """Serve + connect + run with no agent: setup on enter, grade on exit."""
    async with runtime(task) as addr, connect(addr) as client:
        async with Run(client, task.id, task.args) as run:
            pass  # no agent; the workspace stays in its setup state
    return run.reward


@pytest.mark.parametrize("task_id,test_files", TASKS, ids=[t[0] for t in TASKS])
async def test_golden_passes(runtime, task_id, test_files):
    task = verilog_task(
        task_id=task_id,
        description="(validation)",
        test_files=test_files,
        validate_mode="golden_pass",
    )
    reward = await _grade(runtime, task)
    assert reward == 1.0, f"{task_id}: golden solution should pass the hidden tests (got {reward})"


@pytest.mark.parametrize("task_id,test_files", TASKS, ids=[t[0] for t in TASKS])
async def test_baseline_fails(runtime, task_id, test_files):
    task = verilog_task(
        task_id=task_id,
        description="(validation)",
        test_files=test_files,
        validate_mode="baseline_fail",
    )
    reward = await _grade(runtime, task)
    assert reward == 1.0, f"{task_id}: empty baseline should fail -> inverted reward 1.0 (got {reward})"
