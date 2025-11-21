import logging

from hud_controller.spec import ProblemSpec, PROBLEM_REGISTRY

logger = logging.getLogger(__name__)


PROBLEM_REGISTRY.append(
    ProblemSpec(
        id="simple_counter",
        description="""Please implement a simple synchronous counter that with reset, enable, and load functionality.
Inputs:
clk - Clock signal (triggers on rising edge)
rst - Synchronous reset signal
ena - Enable signal (allows counting)
set - Load signal (sets counter to a specific value)
din - 8-bit data input (value to load when set is high)
Output:
counter - 8-bit counter value        
        
""",
        difficulty="easy",
        base="simple_counter_baseline",
        test="simple_counter_test",
        golden="simple_counter_golden",
        test_files=["tests/test_simple_counter_hidden.py"],
    )
)

PROBLEM_REGISTRY.append(
    ProblemSpec(
        id="simple_dff",
        description="""Please implement a simple digital flip-flop with a clock input and a data input. 
The output should be the same as the data input on the rising edge of the clock.

Inputs:
clk - Clock signal (triggers on rising edge)
d - Data input
Output:
q - Output value      
""",
        difficulty="easy",
        base="simple_dff_baseline",
        test="simple_dff_test",
        golden="simple_dff_golden",
        test_files=["tests/test_simple_dff_hidden.py"],
    )
)