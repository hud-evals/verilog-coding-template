"""Remote test script -- working with tasks and the platform.

This demonstrates the full workflow for remote evaluations:

1. Deploy your environment to hud.ai (New -> Environment -> Connect GitHub repo)
2. Tasks are defined in tasks/__init__.py using scenario.task()
3. Run evaluations locally or at scale

## Option A: Run on Platform

Run evaluations at scale directly on hud.ai with parallel execution and automatic tracing.

## Option B: CLI Evaluation

    # Run all tasks
    hud eval my-org/verilog-tasks --model gpt-4o --remote

## Option C: Python Script (this file)

    # Upload tasks to platform
    python remote_test.py --upload my-org/verilog-tasks

    # Run all tasks from platform
    python remote_test.py --platform my-org/verilog-tasks --model gpt-4o

"""

import argparse
import asyncio

import hud
from hud.agents import OpenAIChatAgent
from hud.datasets import load_tasks, save_tasks
from hud.eval.task import Task

from tasks import ALL_TASKS

ENV_NAME = "verilog-coding"


async def upload_to_platform(slug: str):
    """Upload tasks to the platform."""
    print(f"=== Upload to Platform: {slug} ===")

    remote_tasks = [
        Task(
            env={"name": ENV_NAME},
            scenario=f"{ENV_NAME}:{task.scenario}",
            args=task.args,
            slug=task.slug,
        )
        for task in ALL_TASKS.values()
    ]
    save_tasks(slug, remote_tasks)
    print(f"Saved {len(remote_tasks)} tasks -> hud eval {slug} --model gpt-4o --remote")


async def main():
    parser = argparse.ArgumentParser(description="Remote task operations")
    parser.add_argument(
        "--upload",
        metavar="SLUG",
        help="Upload tasks to platform (e.g. my-org/verilog-tasks)",
    )
    parser.add_argument(
        "--platform",
        metavar="SLUG",
        help="Load and run tasks from platform slug",
    )
    parser.add_argument("--model", default="gpt-4o", help="Model to use")
    args = parser.parse_args()

    if args.upload:
        await upload_to_platform(args.upload)
    else:
        print(f"=== Loading tasks from platform: {args.platform} ===")
        tasks = load_tasks(args.platform)
        async with hud.eval(tasks) as ctx:
            agent = OpenAIChatAgent.create(model=args.model)
            await agent.run(ctx)


if __name__ == "__main__":
    asyncio.run(main())
