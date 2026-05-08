"""Task definitions for verilog coding environment.

One generic ``verilog_task`` scenario accepts all task content as parameters
(description, test files). Each ``.task()`` call produces a distinct task by
passing different values — no new scenario function needed.

Branch names are derived from ``task_id`` by convention:
``{task_id}_baseline``, ``{task_id}_test``, ``{task_id}_golden``.
"""

from env import verilog_task


# =============================================================================
# Tasks
# =============================================================================

simple_counter = verilog_task.task(
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
simple_counter.slug = "simple-counter"

simple_counter_hints = verilog_task.task(
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
simple_counter_hints.slug = "simple-counter-hints"

simple_dff = verilog_task.task(
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
simple_dff.slug = "simple-dff"

simple_dff_hints = verilog_task.task(
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
simple_dff_hints.slug = "simple-dff-hints"

# =============================================================================
# Task registry — keyed by name for CLI discovery
# =============================================================================

tasks = {
    "simple_counter": simple_counter,
    "simple_counter_hints": simple_counter_hints,
    "simple_dff": simple_dff,
    "simple_dff_hints": simple_dff_hints,
}
