"""Task definitions for verilog coding environment.

Each task is created via scenario.task() and can be run locally or remotely:

    python local_test.py --list
    python local_test.py --task simple_counter
    python local_test.py --task simple_dff_hints --model claude-sonnet-4-5
"""

# Import task modules to register their scenarios
from . import basic  # noqa: F401

# --- Basic tasks (easy) -------------------------------------------------------

_counter = basic.implement_counter.task()
_counter.slug = "simple-counter"

_counter_hints = basic.implement_counter.task(hints_enabled=True)
_counter_hints.slug = "simple-counter-hints"

_dff = basic.implement_dff.task()
_dff.slug = "simple-dff"

_dff_hints = basic.implement_dff.task(hints_enabled=True)
_dff_hints.slug = "simple-dff-hints"

# --- Registry for discovery ----------------------------------------------------

ALL_TASKS = {
    "simple_counter": _counter,
    "simple_counter_hints": _counter_hints,
    "simple_dff": _dff,
    "simple_dff_hints": _dff_hints,
}
