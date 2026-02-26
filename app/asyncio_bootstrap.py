import asyncio
import sys


_BOOTSTRAPPED = False


def bootstrap_asyncio() -> None:
    """Initialize asyncio for Windows/main-thread import-time compatibility.

    Safe to call multiple times.
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return

    if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    _BOOTSTRAPPED = True
