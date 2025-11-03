import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from .manual_dinit import ServiceLoader, SimpleDinit

logger = logging.getLogger(__name__)

TEST_MODE = os.environ.get("MCP_TESTING_MODE", "1") in ["1", "true"]

if TEST_MODE:
    # xfce starts quickly on our computer, but not in test
    XFCE_STARTUP_DELAY = 5
    CHROMIUM_STARTUP_DELAY = 3
else:
    # in test mode, we need to wait for the computer to start
    XFCE_STARTUP_DELAY = 30
    CHROMIUM_STARTUP_DELAY = 5


async def start_dinit():
    logger.info("Starting dinit")
    loader = ServiceLoader(Path("/etc/dinit.d"))
    services = loader.load_all()
    engine = SimpleDinit(services)
    engine.start("boot")