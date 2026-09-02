"""Turn a configuration change into what the S3 service can take.

The daemon reloads on SIGHUP for most keys and silently refuses or half
applies the rest, and `kill -HUP` exits 0 either way. So the verb is
never taken from the caller: the files are rendered, the new text is
diffed against what was on disk, and only a diff the daemon cannot take
on a reload becomes a restart. Render and act are serialized so two
callers cannot interleave a restart-only change with the other's
reload.
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import TYPE_CHECKING

from middlewared.service_exception import CallError

from .render import needs_restart

if TYPE_CHECKING:
    from middlewared.main import Middleware

SERVICE = "truenas_s3"
ETC_GROUP = "truenas_s3"
BUCKETS_CONF = "/etc/truenas_s3/buckets.conf"
UNIT_DROPIN = "/etc/systemd/system/truenas_s3.service.d/override.conf"

_lock = asyncio.Lock()


def _read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return ""


def daemon_reload() -> None:
    """Make systemd read the unit drop-in again. Runs from the service
    object's start and restart hooks, after the files are on disk."""
    subprocess.run(["systemctl", "daemon-reload"], capture_output=True, check=True)


async def render_and_apply(middleware: Middleware, *, force_restart: bool = False) -> str | None:
    """Regenerate the S3 service's files and reload or restart it.

    Returns the verb applied, or None when the service is not running
    (the files are regenerated either way, so a later start picks them
    up). `force_restart` is for callers that know the registry moved in
    a way the render cannot show, such as a dataset mount point.
    """
    async with _lock:
        before = await middleware.run_in_thread(lambda: (_read(BUCKETS_CONF), _read(UNIT_DROPIN)))
        await middleware.call("etc.generate", ETC_GROUP)
        after = await middleware.run_in_thread(lambda: (_read(BUCKETS_CONF), _read(UNIT_DROPIN)))

        verb = "RESTART" if force_restart or needs_restart(before[0], after[0], before[1], after[1]) else "RELOAD"

        # a systemd Reload runs the unit's ExecReload; a drop-in change is
        # restart-only, and the service object reloads systemd before it
        await middleware.call("etc.generate", "rc")
        state = (await middleware.call("service.query", [["service", "=", SERVICE]], {"get": True}))["state"]
        if state.lower() != "running":
            return None

        if not await (await middleware.call("service.control", verb, SERVICE)).wait(raise_error=True):
            raise CallError(f"The {SERVICE} service failed to {verb.lower()}", CallError.ESERVICESTARTFAILURE)
        return verb


async def start_or_restart(middleware: Middleware) -> None:
    """For a registry change while the service may be stopped but enabled,
    such as a pool import bringing bucket rows back: start it if it is
    enabled and not running, restart it if it is."""
    async with _lock:
        await middleware.call("etc.generate", ETC_GROUP)
        svc = await middleware.call("service.query", [["service", "=", SERVICE]], {"get": True})
        if svc["state"].lower() == "running":
            verb = "RESTART"
        elif svc["enable"]:
            verb = "START"
        else:
            return
        await (await middleware.call("service.control", verb, SERVICE)).wait(raise_error=True)
