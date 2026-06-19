# Verilog Coding Environment (HUD v6)

A HUD v6 environment where an agent implements a Verilog/SystemVerilog module from a spec over an
`ssh` shell, graded by hidden cocotb tests run through Icarus Verilog (no LLM judge):

> read the spec → implement `sources/<module>.sv` → pass the hidden testbench.

## Tasks

| Task | Module | Contract the testbench checks |
|------|--------|-------------------------------|
| `simple-counter` | 8-bit synchronous counter | reset, enable, synchronous load priority |
| `simple-dff` | D flip-flop | positive-edge-triggered |

Each module also has a `-hints` variant (`simple-counter-hints`, `simple-dff-hints`) that adds an
implementation hint to the prompt: 4 tasks total. Every prompt states the behavioral contract, so
a correct reading of the spec is gradeable.

## How grading stays honest

- The target repo (hidden `_test` + reference `_golden` branches) is cloned to a private **oracle**
  dir, never mounted into the workspace.
- The workspace is a `git archive` of the **baseline** (no `.git`), so the solution isn't visible
  from `ls`/`cat`.
- Grading copies only the agent's `sources/` into a clean baseline tree, applies the hidden
  `test.patch`, and runs `pytest` there, so the agent can't plant a `conftest.py` to force a pass.

> **Isolation caveat.** Hiding the oracle dir from the agent would need `bubblewrap`, but the
> platform kernel disallows unprivileged namespaces (with bwrap installed, every agent command
> fails), so the image ships without it and the shell is unsandboxed. Cross-rollout isolation still
> holds (fresh container per rollout), but a determined agent could read the oracle or clone the
> substrate. For a rigorous eval, point `REPO_URL` at a private substrate (the default is public and
> likely memorized) and add a container-level network policy.

## Setup

```bash
uv sync --extra dev                  # hud v6 + dev tools
hud set HUD_API_KEY=your-key-here    # CLI auth, get one at hud.ai/project/api-keys
```

Local grading shells out to `iverilog`, so a real pass needs Icarus Verilog on this host
(`brew install icarus-verilog verilator` on macOS). The shell is unsandboxed locally too, so treat
local as trusted iteration, not isolation.

## Run

```bash
# local
hud eval tasks.py claude --task-ids simple-counter --group 1 -y

# deploy once, then run hosted
hud deploy .
hud sync tasks <taskset-name>
hud eval tasks.py claude --runtime hud --full
```

`hud deploy` is the slow step; re-run `hud sync tasks` after editing `tasks.py`, and redeploy only
when `env.py` or the Dockerfile changes.

## Validate golden / baseline

Build the image (bundles iverilog + the synced venv) and attach the no-agent test driver:

```bash
docker build -f Dockerfile.hud -t verilog-coding-template:dev .
docker run -d --rm -p 8765:8765 verilog-coding-template:dev
uv run --extra dev pytest tests/ -v --runtime tcp://127.0.0.1:8765
```

This asserts each reference solution passes (reward 1.0) and the empty baseline fails (inverted
reward 1.0).

## Documentation

See the [full docs](https://docs.hud.ai) for tasks, evaluation, and scaling.
