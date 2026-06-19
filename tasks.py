"""Task definitions for the Verilog coding environment.

Run locally:  hud eval tasks.py claude --task-ids simple-counter --group 1 -y

Calling the generic ``verilog_task`` template binds a concrete ``Task``; branch names
follow ``{task_id}_{baseline,test,golden}``. ``env`` is re-exported because ``hud eval
tasks.py`` serves this module as the env source (``load_environment`` needs it here).
"""

from env import env, verilog_task  # noqa: F401  (env re-exported for `hud eval tasks.py`)

# Behavioral contract shared by both counter variants. Stated explicitly so the prompt
# matches what the hidden cocotb testbench actually checks (synchronous design, the
# rst > set > ena priority, synchronous load, hold-on-idle, 8-bit wrap); otherwise a
# reasonable-but-different counter (e.g. async reset, or ena beating set) fails silently.
_COUNTER_SPEC = (
    "Implement an 8-bit synchronous counter in sources/simple_counter.sv.\n\n"
    "Ports (already declared, do not change them):\n"
    "  clk     - clock; all state changes happen on its rising edge\n"
    "  rst     - synchronous reset\n"
    "  ena     - count enable\n"
    "  set     - synchronous load enable\n"
    "  din     - 8-bit value loaded when set is asserted\n"
    "  counter - 8-bit registered output\n\n"
    "Behavior, evaluated on each rising edge of clk, in this priority order:\n"
    "  1. If rst is high, counter becomes 0.\n"
    "  2. Else if set is high, counter is loaded with din.\n"
    "  3. Else if ena is high, counter increments by 1 (wrapping modulo 256).\n"
    "  4. Otherwise counter holds its current value.\n"
    "All updates are synchronous (registered on the rising clock edge); counter resets "
    "to 0 and starts at 0."
)

_DFF_SPEC = (
    "Implement a positive-edge-triggered D flip-flop in sources/dff.sv.\n\n"
    "Ports (already declared, do not change them):\n"
    "  clk - clock\n"
    "  d   - data input\n"
    "  q   - registered data output\n\n"
    "Behavior: on each rising edge of clk, q is updated to the value of d sampled at "
    "that edge. q is registered, so it reflects d with one clock of latency (a "
    "combinational `assign q = d` is incorrect)."
)


# The intermediate Task vars are underscore-prefixed so the taskset scanner skips them (it
# collects public module-level Tasks AND public lists/tuples of Tasks). If they were public,
# each task would be collected twice (standalone and via the `tasks` list), and Taskset would
# raise "duplicate task slugs". Only the public `tasks` LIST below is collected.

_simple_counter = verilog_task(
    task_id="simple_counter",
    description=_COUNTER_SPEC,
    test_files=["tests/test_simple_counter_hidden.py"],
)
_simple_counter.slug = "simple-counter"
_simple_counter.columns = {"module": "simple_counter", "hints": False}

_simple_counter_hints = verilog_task(
    task_id="simple_counter",
    description=(
        _COUNTER_SPEC
        + "\n\nHint: use a single `always_ff @(posedge clk)` block. Check rst first "
        "(counter <= 0), then set (counter <= din), then ena (counter <= counter + 1), "
        "otherwise hold."
    ),
    test_files=["tests/test_simple_counter_hidden.py"],
)
_simple_counter_hints.slug = "simple-counter-hints"
_simple_counter_hints.columns = {"module": "simple_counter", "hints": True}

_simple_dff = verilog_task(
    task_id="simple_dff",
    description=_DFF_SPEC,
    test_files=["tests/test_simple_dff_hidden.py"],
)
_simple_dff.slug = "simple-dff"
_simple_dff.columns = {"module": "simple_dff", "hints": False}

_simple_dff_hints = verilog_task(
    task_id="simple_dff",
    description=_DFF_SPEC + "\n\nHint: use `always @(posedge clk) q <= d;`",
    test_files=["tests/test_simple_dff_hidden.py"],
)
_simple_dff_hints.slug = "simple-dff-hints"
_simple_dff_hints.columns = {"module": "simple_dff", "hints": True}


# Public taskset, a LIST (not a dict): hud eval / hud sync scan module-level Task objects;
# a dict would collect nothing.
tasks = [_simple_counter, _simple_counter_hints, _simple_dff, _simple_dff_hints]
