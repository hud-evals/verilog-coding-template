"""Shared fixtures for the verilog-coding test suite (v6).

v6 tests drive a *served* environment over the control channel. The ``runtime`` fixture
chooses how the env is served:

  * ``--runtime local`` (default): ``LocalRuntime`` serves ``tasks.py`` in a child
    process. Self-contained, but the cocotb grade shells out to ``iverilog``, so a real
    pass/fail needs Icarus Verilog + a synced substrate venv on this host (Linux, or
    macOS with ``brew install icarus-verilog`` + a one-time substrate ``uv sync``).
  * ``--runtime tcp://HOST:PORT``: attach to an already-running container (the built
    image), which bundles iverilog + the synced venv. This is the authoritative way to
    validate golden/baseline:

        docker run -d --rm -p 8765:8765 verilog-coding-template:dev
        uv run --extra dev pytest tests/ -v --runtime tcp://127.0.0.1:8765
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def pytest_addoption(parser):
    parser.addoption(
        "--runtime",
        default="local",
        help="'local' (serve tasks.py via LocalRuntime) or a tcp:// url to attach to a running env.",
    )


@pytest.fixture(scope="session")
def runtime(request):
    """A v6 placement provider: ``LocalRuntime`` or a ``Runtime`` tcp attach."""
    from hud.eval import LocalRuntime, Runtime

    choice = request.config.getoption("--runtime")
    if choice == "local":
        return LocalRuntime(str(PROJECT_ROOT / "tasks.py"))
    if choice.startswith("tcp://"):
        return Runtime(choice)
    raise ValueError(f"--runtime must be 'local' or a tcp:// url, got {choice!r}")
