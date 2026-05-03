from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from truenas_os_pyutils.io import atomic_write

if TYPE_CHECKING:
    from middlewared.main import Middleware


# Materialized from system.advanced.config['debugkernel']. truenas-initrd.py
# reads this file to decide whether to (re)build the debug kernel's initrd
# alongside the production kernel's. Lives under /data so it survives BE
# upgrades (the installer rsyncs /data into the new BE).
DEBUG_KERNEL_FLAG_PATH = "/data/subsystems/initramfs/debug_kernel"


def write_debug_kernel_flag(middleware: Middleware) -> bool:
    """
    Materialize the `debugkernel` setting to a stable path under /data.

    Returns True if the file changed (caller should force an initramfs
    rebuild so truenas-initrd.py picks up the new value).

    Sync — call from a thread (`asyncio.to_thread`) when invoked from a
    coroutine.
    """
    desired = "0\n"
    if middleware.call_sync("system.advanced.config")["debugkernel"]:
        desired = "1\n"

    try:
        with open(DEBUG_KERNEL_FLAG_PATH) as f:
            existing = f.read()
    except FileNotFoundError:
        existing = ""
    if existing == desired:
        return False
    os.makedirs(os.path.dirname(DEBUG_KERNEL_FLAG_PATH), exist_ok=True)
    with atomic_write(DEBUG_KERNEL_FLAG_PATH, "w") as f:
        f.write(desired)
    return True


async def _event_system_ready(middleware, event_type, args):
    # Don't block boot
    middleware.create_task(_reconcile(middleware))


async def _reconcile(middleware):
    try:
        changed = await asyncio.to_thread(write_debug_kernel_flag, middleware)
        if changed:
            # Flag drifted from the live DB (factory install, upgrade from a
            # release that didn't write it, config upload, etc.). Force a
            # rebuild so the new flag value is honored on next boot.
            await middleware.call("boot.update_initramfs", {"force": True})
    except Exception:
        middleware.logger.error("Failed to reconcile debug_kernel flag", exc_info=True)


async def setup(middleware):
    middleware.event_subscribe("system.ready", _event_system_ready)
