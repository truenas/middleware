"""Turn a configuration change into what the S3 service can take.

The files are rendered, then the running daemon is asked over its control
socket to reload them, and it answers: reloading, or refused because a
key that holds to a restart moved, or refused because the files do not
load. The daemon is the one authority on which change costs what, so
nothing here keeps a copy of that list. Render and ask are serialized so
two callers cannot interleave a render with the other's answer.
"""

from __future__ import annotations

import asyncio
import errno
import socket
from typing import TYPE_CHECKING

from middlewared.service_exception import CallError

if TYPE_CHECKING:
    from middlewared.api.current import ServiceEntry
    from middlewared.main import Middleware

SERVICE = "truenas_s3"
ETC_GROUP = "truenas_s3"
MISSING_ALERT = "S3BucketDatasetMissing"
CONTROL_SOCKET = "/run/truenas_s3/control"
# a reload resolves every credential through NSS before it answers; a
# directory that is slow to answer is the daemon's to time out, not ours
CONTROL_TIMEOUT = 120

_lock = asyncio.Lock()


def ask_reload() -> str | None:
    """Ask the daemon to reload and return the first word of its answer,
    or None when no daemon is listening.

    The protocol is one line each way (crates/daemon/README.md in the
    truenas_s3 repository): `reloading`, `restart <why>`, `invalid <why>`
    or `draining`. The text after the word is for a person.
    """
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
    """Regenerate the S3 service's files and put them in force.

    Returns "RELOAD" when the daemon took them in place, "RESTART" when it
    could not and was restarted, or None when it is not running (the
    files are regenerated either way, so a later start picks them up). A
    deployment the daemon cannot load is an error: the running one stays
    in force and nothing is restarted, since a start would refuse the
    same files. `force_restart` is for callers that know the registry
    moved in a way the files cannot show, such as a dataset mount point.
    """
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


async def start_or_restart(middleware: Middleware) -> None:
    """For a registry change while the service may be stopped but enabled,
    such as a pool import bringing bucket rows back: start it if it is
    enabled and not running, restart it if it is."""
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
