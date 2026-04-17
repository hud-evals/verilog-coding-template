# Verilog Coding Environment

A Verilog HDL coding environment where agents implement digital logic modules and are graded by hidden testbenches using iverilog and verilator.

## Setup

```bash
uv sync
hud set HUD_API_KEY=your-key-here   # CLI auth, get one at hud.ai/project/api-keys
```

## Deploy & Run

```bash
hud deploy .                              # deploy the environment (once)
hud sync tasks <taskset-name>             # push tasks to a taskset (fast, re-run on every task change)
hud eval <taskset-name> --remote --full
```

**Iteration loop:** `hud deploy` is the slow step — run it once. After that, edit `tasks.py` and re-run `hud sync tasks` (takes seconds). Only redeploy when `env.py` or the Dockerfile changes.

See [Deploy & Go Remote](https://docs.hud.ai/building/running-at-scale) for deploy flags, secrets, and auto-deploy options.

## Tasks

4 tasks (2 problems, each with and without hints):

- **simple counter** — 8-bit synchronous counter with reset, enable, and load
- **D flip-flop** — basic D flip-flop with clock and data inputs

Each task has a variant with and without hints. Agents get a description of the module to implement, write Verilog in a sandboxed workspace, and are graded by applying hidden test patches and running `pytest`.

## Documentation

To learn more about tasks, evaluations, and running at scale see the [full docs](https://docs.hud.ai).
