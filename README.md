# Verilog Coding Environment

A Verilog HDL coding environment where agents implement digital logic modules and are graded by hidden testbenches using iverilog and verilator.

## Quick Start

```bash
uv sync                # install dependencies
hud deploy .           # build and deploy to HUD platform
hud sync tasks <name>  # upload task definitions
```

## Tasks

4 tasks (2 problems, each with and without hints):

- **simple counter** — 8-bit synchronous counter with reset, enable, and load
- **D flip-flop** — basic D flip-flop with clock and data inputs

Each task has a variant with and without hints. Agents get a description of the module to implement, write Verilog in a sandboxed workspace, and are graded by applying hidden test patches and running `pytest`.

## Documentation

To learn more about tasks, evaluations, and running at scale see the [full docs](https://docs.hud.ai).
