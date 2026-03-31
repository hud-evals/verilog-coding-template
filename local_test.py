"""Local test script for the verilog coding environment.

Usage:
    python local_test.py --list
    python local_test.py --task simple_counter
    python local_test.py --task simple_dff_hints --model claude-sonnet-4-5
    python local_test.py --task simple_counter_hints --max-steps 30
"""

import argparse
import asyncio
import copy

import hud
from hud import Environment
from hud.agents.claude import ClaudeAgent

from tasks import ALL_TASKS

_ENV_NAME = "verilog-coding"
_IMAGE = "verilog-coding-template"

# Client-side environment — routes tool calls and scenarios to the container.
env = Environment(_ENV_NAME)
env.connect_image(_IMAGE)


def _client_task(task):
    """Return a copy of *task* whose env is the client-side Environment.

    scenario.task() binds the live Environment from env.py, which has
    scenarios registered locally and causes the SDK to execute setup_task()
    in-process.  Rebinding to our client-side env (which only has
    connect_image, no scenarios) makes the SDK route execution to the
    Docker container instead.
    """
    t = copy.copy(task)
    t.env = env
    return t


async def main():
    available = sorted(ALL_TASKS)

    parser = argparse.ArgumentParser(description="Run agent against a Verilog coding task")
    parser.add_argument("--task", default=available[0], choices=available)
    parser.add_argument("--model", default="claude-sonnet-4-5")
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--list", action="store_true", help="List available tasks and exit")
    args = parser.parse_args()

    if args.list:
        for t in available:
            slug = ALL_TASKS[t].slug
            print(f"  {t:30s} ({slug})")
        return

    task = _client_task(ALL_TASKS[args.task])

    print(f"=== {args.task} ({args.model}) ===")
    async with env:
        async with hud.eval(task, name=args.task, trace=True) as ctx:
            agent = ClaudeAgent.create(model=args.model)
            await agent.run(ctx, max_steps=args.max_steps)
            print(f"Reward: {ctx.reward}")


if __name__ == "__main__":
    asyncio.run(main())
