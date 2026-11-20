from __future__ import annotations

import asyncio
import errno
import socket
from typing import TYPE_CHECKING

from middlewared.service_exception import CallError

if TYPE_CHECKING:
    from middlewared.api.current import ServiceEntry
    from middlewared.main import Middleware

SERVICE = "s3"
ETC_GROUP = "truenas_s3"
MISSING_ALERT = "S3BucketDatasetMissing"
CONTROL_SOCKET = "/run/truenas_s3/control"
# a reload resolves every credential through NSS, so a slow directory makes it slow
CONTROL_TIMEOUT = 120
# how long a `require_nts` change waits for chronyd, restarted for the same change, to select a source again
CLOCK_SYNC_TIMEOUT = 60

_lock = asyncio.Lock()


def ask_reload() -> str | None:
    """Ask the daemon to reload. Returns the first word of its answer,
    `reloading`, `restart`, `invalid` or `draining`, or None when no daemon
    is listening."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(CONTROL_TIMEOUT)
            sock.connect(CONTROL_SOCKET)
            sock.sendall(b"reload\n")
            answer = b""
            while not answer.endswith(b"\n"):
                chunk = sock.recv(4096)
                if not chunk:
                    break
                answer += chunk
    except OSError as e:
        if e.errno in (errno.ENOENT, errno.ECONNREFUSED):
            return None
        raise CallError(f"The {SERVICE} service did not answer a reload request: {e}")
    return answer.decode(errors="replace").strip()


async def render_and_apply(middleware: Middleware, *, force_restart: bool = False) -> str | None:
    """Regenerate the S3 service's files and apply them. Returns "RELOAD" when
    the daemon reloaded, "RESTART" when it had to be restarted, or None when
    it is not running. Files the daemon cannot load are an error, and the
    running service keeps the old ones. `force_restart` is for registry
    changes the files cannot show, such as a dataset mountpoint."""
    async with _lock:
        await middleware.call("etc.generate", ETC_GROUP)

        if force_restart:
            verb = "RESTART"
        else:
            answer = await middleware.run_in_thread(ask_reload)
            if answer is None:
                return None
            word, _, why = answer.partition(" ")
            if word == "reloading":
                return "RELOAD"
            if word == "invalid":
                raise CallError(f"The {SERVICE} service refused the configuration: {why}")
            if word == "draining":
                # a stop is under way; the next start reads what was rendered
                return None
            if word != "restart":
                raise CallError(f"The {SERVICE} service gave an answer this version does not know: {answer!r}")
            verb = "RESTART"

        svc: ServiceEntry = await middleware.call("service.query", [["service", "=", SERVICE]], {"get": True})
        if svc.state.lower() != "running":
            return None
        if not await (await middleware.call("service.control", verb, SERVICE)).wait(raise_error=True):
            raise CallError(f"The {SERVICE} service failed to {verb.lower()}", CallError.ESERVICESTARTFAILURE)
        return verb


async def chronyd_selected_source(middleware: Middleware) -> bool:
    """Whether chronyd has selected a source to synchronize the clock to."""
    try:
        return bool(await middleware.call("system.ntpserver.peers", [["state", "=", "BEST"]]))
    except CallError:
        # chronyd is still starting
        return False


async def apply_require_nts(middleware: Middleware) -> str | None:
    """Apply a changed `require_nts`. The daemon's clock check reads it once, at start-up, so a reload answers that
    the daemon must restart. A running service first waits for chronyd, restarted for the same change, to select a
    source again: a check that finds it unsynchronized holds every object-locked bucket read-only until the next
    restart. Returns what `render_and_apply` returns."""
    svc: ServiceEntry = await middleware.call("service.query", [["service", "=", SERVICE]], {"get": True})
    if svc.state.lower() == "running":
        for _ in range(CLOCK_SYNC_TIMEOUT):
            if await chronyd_selected_source(middleware):
                break
            await asyncio.sleep(1)
        else:
            middleware.logger.warning(
                "s3: chronyd selected no time source within %d seconds, so the restarted service may hold "
                "object-locked buckets read-only until it restarts again",
                CLOCK_SYNC_TIMEOUT,
            )
    return await render_and_apply(middleware)


async def start_or_restart(middleware: Middleware) -> None:
    """Start the service if it is enabled and not running, restart it if it is running."""
    async with _lock:
        await middleware.call("etc.generate", ETC_GROUP)
        svc: ServiceEntry = await middleware.call("service.query", [["service", "=", SERVICE]], {"get": True})
        if svc.state.lower() == "running":
            verb = "RESTART"
        elif svc.enable:
            verb = "START"
        else:
            return
        await (await middleware.call("service.control", verb, SERVICE)).wait(raise_error=True)
