"""Verilog coding environment (HUD v6).

The agent gets a workspace-rooted ``ssh`` shell holding one module skeleton to implement
under ``sources/``, graded by hidden cocotb tests via iverilog. The oracle repo (hidden
``_test`` / reference ``_golden`` branches) is cloned to a private dir never mounted into
the workspace; the workspace is a ``git archive`` export with no ``.git``. Isolation caveat:
the platform shell is unsandboxed (no bwrap), so use a private substrate for a real eval.
"""


import asyncio
import io
import logging
import os
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from hud.environment import Environment
from hud.graders import BashGrader, SubScore, combine

logger = logging.getLogger(__name__)

# NOTE: this file deliberately omits ``from __future__ import annotations``. Do NOT add it
# back: under it, an @env.template parameter typed with Literal/Optional/an alias/a Pydantic
# model crashes at deploy/start (the server runs ``TypeAdapter`` on a string forward-ref ->
# PydanticUserError, surfaced as ``-32000``). Without it, annotations resolve to real objects
# and any param type works (validate_mode is kept as a plain ``str | None``). Known SDK bug.

# Substrate identity (overridable for forks).
FOLDER_NAME = os.environ.get("FOLDER_NAME", "example-verilog-codebase")
REPO_URL = os.environ.get("REPO_URL", "https://github.com/hud-evals/example-verilog-codebase")

# Portable, per-process paths.
# The built image pins ORACLE/WORKSPACE/PATCHES via Dockerfile ENV (substrate cloned +
# synced at build time). Locally (LocalRuntime serves each rollout as its own subprocess
# sharing the host filesystem) we key the dirs on the PID so concurrent rollouts don't
# clobber one another, and we DON'T export them to os.environ (children would inherit
# them, defeating per-process isolation).
_EXPLICIT = os.environ.get("ORACLE_DIR") or os.environ.get("PROJECT_DIR")
if _EXPLICIT:
    ORACLE_DIR = _EXPLICIT
    _parent = Path(_EXPLICIT).parent
    WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", str(_parent / "workspace"))
    PATCHES_DIR = os.environ.get("PATCHES_DIR", str(_parent / "patches"))
    LOCAL = False
else:
    # System temp dir, NOT inside the project: a grade dir under the repo would make
    # `git apply` find the project's .git (and skip the patch) and pytest climb to the
    # project's pyproject.toml. Outside any repo, both behave like the built image.
    _ROOT = Path(tempfile.gettempdir()) / "hud-verilog-coding"
    _PID = os.getpid()
    ORACLE_DIR = str(_ROOT / f"{FOLDER_NAME}-oracle-{_PID}")
    WORKSPACE_DIR = str(_ROOT / f"{FOLDER_NAME}-work-{_PID}")
    PATCHES_DIR = str(_ROOT / f"patches-{_PID}")
    LOCAL = True


env = Environment(name="verilog-coding")


# Substrate bootstrap. Registered BEFORE env.workspace(...) so the oracle clone completes
# before the ssh capability is published (both are @env.initialize hooks; only registration
# order separates them). All init hooks finish before any client can connect.


async def _run(*argv: str, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a subprocess off the event loop, capturing combined output."""
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    return subprocess.CompletedProcess(argv, proc.returncode or 0, out.decode(errors="replace"), "")


@env.initialize
async def _ensure_substrate() -> None:
    """Clone the oracle repo if missing (an existing clone is refreshed); create the workspace dir.

    No-op clone in the built image (cloned + synced at build time). Locally, also
    ``uv sync``s the oracle once so the grader's ``uv run --no-sync`` works offline.
    """
    Path(WORKSPACE_DIR).mkdir(parents=True, exist_ok=True)
    oracle = Path(ORACLE_DIR)
    if (oracle / ".git").exists():
        await _run("git", "fetch", "--all", "--quiet", cwd=ORACLE_DIR)
        return

    logger.info("Cloning oracle %s -> %s", REPO_URL, ORACLE_DIR)
    oracle.parent.mkdir(parents=True, exist_ok=True)
    res = await _run("git", "clone", "--quiet", REPO_URL, ORACLE_DIR)
    if res.returncode != 0:
        raise RuntimeError(f"oracle clone failed:\n{res.stdout}")

    if LOCAL:
        # cocotb/pytest aren't vendored; sync once (needs network) so the grader can use
        # --no-sync. In the image this happens at build time instead.
        logger.info("uv sync oracle venv (one-time, local only)")
        res = await _run("uv", "sync", cwd=ORACLE_DIR)
        if res.returncode != 0:
            logger.warning("oracle `uv sync` failed (grading may not run):\n%s", res.stdout)


# Publish the ssh capability rooted in the (initially empty) workspace. Absolute path: a
# relative root would resolve against the serving process CWD, not this file.
#
# network=False expresses intent (the task needs only local iverilog/verilator), but it is
# enforced ONLY by bwrap, which is unavailable on the platform, so it is a no-op there. Real
# network restriction (to stop cloning the public substrate) must come from a container-level
# network policy. The substrate is public/likely-memorized; for a real eval/training run
# point REPO_URL at a private/transformed substrate (see README).
env.workspace(WORKSPACE_DIR, name="shell", network=False)


@env.shutdown
async def _cleanup() -> None:
    """Remove per-process scratch dirs we synthesized locally (never the image's clone)."""
    if LOCAL:
        for d in (WORKSPACE_DIR, ORACLE_DIR, PATCHES_DIR):
            shutil.rmtree(d, ignore_errors=True)


def _export_tree(ref: str, dest: str) -> None:
    """Replace ``dest`` contents with the ``origin/<ref>`` tree (no ``.git``)."""
    dest_p = Path(dest)
    dest_p.mkdir(parents=True, exist_ok=True)
    for child in dest_p.iterdir():
        if child.name == ".hud":
            continue  # the Workspace's own ssh credentials / bookkeeping, never wipe it
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)

    archive = subprocess.run(
        ["git", "archive", "--format=tar", f"origin/{ref}"],
        cwd=ORACLE_DIR,
        capture_output=True,
    )
    if archive.returncode != 0:
        raise RuntimeError(f"git archive origin/{ref} failed: {archive.stderr.decode(errors='replace')}")
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tf:
        try:
            tf.extractall(dest, filter="data")  # py>=3.12
        except TypeError:
            tf.extractall(dest)  # py3.11 fallback


def _setup_task(task_id: str, validate_mode: str | None = None) -> None:
    """Generate the hidden ``test.patch`` and populate the workspace with the task tree.

    Branch names follow the convention ``{task_id}_{baseline,test,golden}``.
    """
    base = f"{task_id}_baseline"
    test = f"{task_id}_test"
    golden = f"{task_id}_golden"

    task_patches = Path(PATCHES_DIR) / task_id
    task_patches.mkdir(parents=True, exist_ok=True)

    # Hidden testbench = diff(baseline -> test), taken from oracle refs (independent of any
    # working tree) and written outside the workspace so the agent never sees it.
    logger.info("Generating test.patch: %s -> %s", base, test)
    diff = subprocess.run(
        ["git", "diff", f"origin/{base}", f"origin/{test}"],
        cwd=ORACLE_DIR,
        capture_output=True,
        text=True,
    )
    (task_patches / "test.patch").write_text(diff.stdout)

    # golden_pass validation starts from the reference solution; the agent always starts
    # from the empty skeleton (baseline). Export WITHOUT .git -> no solution leak.
    ref = golden if validate_mode == "golden_pass" else base
    logger.info("Populating workspace from origin/%s", ref)
    _export_tree(ref, WORKSPACE_DIR)


def _make_prompt(description: str) -> str:
    """Format a task description into the full agent prompt.

    The files live DIRECTLY in the shell's working directory (the workspace root); there
    is no project subfolder. Being explicit avoids the agent editing a non-existent
    ``<repo-name>/sources/...`` path while the grader reads the real ``sources/``.
    """
    return f"""You are implementing a Verilog/SystemVerilog module.

Your shell starts in the project root. The files you need are DIRECTLY in your current
working directory: `sources/` (the module to edit), `tests/`, and `pyproject.toml`.
There is NO extra subfolder, so do not prefix paths with a repository name. Use the
`sources/` paths exactly as named in the task below. Icarus Verilog (iverilog) and Verilator
are installed.

Edit only the module body in the named file under `sources/`; do NOT change the module
name or any input/output port declarations (names, directions, or widths). Write your own
Verilog testbenches and run them with iverilog to check syntax and the functional behavior
described below before you finish.

{description}
"""


@env.template(id="verilog_task")
async def verilog_task(
    task_id: str,
    description: str,
    test_files: list[str],
    validate_mode: str | None = None,
):
    """Implement a Verilog module from a specification, graded by hidden cocotb tests.

    Args:
        task_id: Substrate branch prefix (e.g. ``"simple_counter"``).
        description: Spec shown to the agent (states the behavioral contract).
        test_files: Hidden test paths (created by ``test.patch``) to run under pytest.
        validate_mode: ``"golden_pass"`` / ``"baseline_fail"`` for no-agent validation.
    """
    _setup_task(task_id=task_id, validate_mode=validate_mode)
    _ = yield _make_prompt(description)

    # Grade in a throwaway copy of the agent's workspace so the hidden testbench never
    # lands in the workspace. We symlink the oracle's prebuilt venv so `uv run --no-sync`
    # works offline without copying hundreds of MB.
    workdir = Path(PATCHES_DIR) / f"grade_{task_id}_{os.getpid()}"
    shutil.rmtree(workdir, ignore_errors=True)
    test_patch = Path(PATCHES_DIR) / task_id / "test.patch"
    try:
        # Grade from a CLEAN, trusted baseline tree and overlay ONLY the agent's
        # sources/ (the RTL they may legitimately change). The agent never controls the
        # rest of the grade dir, so it cannot plant a conftest.py / pytest.ini /
        # sitecustomize.py / fake hidden test to hijack pytest's exit status. Its only
        # lever is the module RTL, which is exactly what the hidden testbench compiles.
        _export_tree(f"{task_id}_baseline", str(workdir))
        ws_sources = Path(WORKSPACE_DIR) / "sources"
        if ws_sources.is_dir():
            wd_sources = workdir / "sources"
            shutil.rmtree(wd_sources, ignore_errors=True)
            shutil.copytree(ws_sources, wd_sources, symlinks=True)
        # Grade with the oracle's prebuilt venv (cocotb/pytest) via a symlink (no big copy).
        os.symlink(Path(ORACLE_DIR) / ".venv", workdir / ".venv")
        # -p no:cacheprovider / --noconftest: defense-in-depth against pytest config hijack.
        command = (
            f"git apply --verbose {shlex.quote(str(test_patch))} && "
            f"uv run --no-sync pytest -p no:cacheprovider --noconftest "
            f"{' '.join(shlex.quote(t) for t in test_files)}"
        )
        sub = await BashGrader.grade(weight=1.0, command=command, cwd=str(workdir), timeout_seconds=600)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if validate_mode == "baseline_fail":
        # Invert: the empty baseline SHOULD fail, so a failure scores 1.0.
        sub = SubScore(name=sub.name, weight=sub.weight, value=1.0 - sub.value, metadata=sub.metadata)

    # A bare SubScore can't be yielded (no .reward); combine(...) -> EvaluationResult,
    # carrying the subscore + pytest stdout/stderr metadata for transparency.
    yield await combine(sub)
