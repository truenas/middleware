import socket
import struct

from aiohttp.http_websocket import WSCloseCode
from aiohttp.web import Request, WebSocketResponse

from middlewared.auth import is_ha_connection
from middlewared.utils.nginx import get_remote_addr_port
from middlewared.utils.origin import Origin, UnixSocketOrigin, TCPIPOrigin
from middlewared.webui_auth import addr_in_allowlist


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

    async def get_origin(self, request: Request) -> Origin | None:
        try:
            sock = request.transport.get_extra_info("socket")
        except AttributeError:
            # request.transport can be None by the time this is called on HA systems because remote node could have been
            # rebooted
            return

        if sock.family == socket.AF_UNIX:
            peercred = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            pid, uid, gid = struct.unpack("3i", peercred)
            return UnixSocketOrigin(pid, uid, gid)

        remote_addr, remote_port = await self.middleware.run_in_thread(get_remote_addr_port, request)
        return TCPIPOrigin(remote_addr, remote_port)

    async def can_access(self, origin: Origin | None) -> bool:
        if not isinstance(origin, TCPIPOrigin):
            return True

        if not (ui_allowlist := await self.middleware.call("system.general.get_ui_allowlist")):
            return True

        if is_ha_connection(origin.addr, origin.port):
            return True

        if addr_in_allowlist(origin.addr, ui_allowlist):
            return True

        return False

    async def process(self, origin: Origin, ws: WebSocketResponse):
        raise NotImplementedError
