from ipaddress import ip_address, ip_network
from typing import Iterable, TYPE_CHECKING

from aiohttp.http_websocket import WSCloseCode
from aiohttp.web import Request, WebSocketResponse

from middlewared.utils.origin import ConnectionOrigin
if TYPE_CHECKING:
    from middlewared.main import Middleware


def addr_in_allowlist(remote_addr, allowlist: Iterable) -> bool:
    """Determine if `remote_addr` is a valid IP address included in `allowlist`."""
    valid = False
    try:
        remote_addr = ip_address(remote_addr)
    except Exception:
        # invalid/malformed IP so play it safe and
        # return False
        valid = False
    else:
        for allowed in allowlist:
            try:
                allowed = ip_network(allowed)
            except Exception:
                # invalid/malformed network so play it safe
                valid = False
                break
            else:
                if remote_addr == allowed or remote_addr in allowed:
                    valid = True
                    break

    return valid


class BaseWebSocketHandler:
    def __init__(self, middleware: "Middleware"):
        self.middleware = middleware

    async def __call__(self, request: Request):
        ws = WebSocketResponse()
        try:
            await ws.prepare(request)
        except ConnectionResetError:
            # Happens when we're preparing a new session, and during the time we prepare, the server is
            # stopped/killed/restarted etc. Ignore these to prevent log spam.
            return ws

        origin = await self.get_origin(request)
        if origin is None:
            await ws.close()
            return ws
        if not await self.can_access(origin):
            await ws.close(
                code=WSCloseCode.POLICY_VIOLATION,
                message=b"You are not allowed to access this resource",
            )
            return ws

        await self.process(origin, ws)
        return ws

    async def get_origin(self, request: Request) -> ConnectionOrigin | None:
        return await self.middleware.run_in_thread(ConnectionOrigin.create, request)

    async def can_access(self, origin: ConnectionOrigin | None) -> bool:
        if origin is None:
            return False

        if origin.is_unix_family or origin.is_ha_connection:
            return True

        ui_allowlist = await self.middleware.call("system.general.get_ui_allowlist")
        return not ui_allowlist or addr_in_allowlist(origin.rem_addr, ui_allowlist)

    async def process(self, origin: ConnectionOrigin, ws: WebSocketResponse):
        raise NotImplementedError
