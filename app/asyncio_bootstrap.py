import asyncio
import sys


_BOOTSTRAPPED = False


def bootstrap_asyncio() -> None:
    """Initialize asyncio policy for Windows compatibility.

    Safe to call multiple times.
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return

    if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    _BOOTSTRAPPED = True
