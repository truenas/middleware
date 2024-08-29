from aiohttp.http_websocket import WSCloseCode
from aiohttp.web import Request, WebSocketResponse

from middlewared.utils.origin import ConnectionOrigin
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

    async def get_origin(self, request: Request) -> ConnectionOrigin | None:
        return await self.middleware.run_in_thread(ConnectionOrigin.create, request)

    async def can_access(self, origin: ConnectionOrigin | None) -> bool:
        if origin is None:
            return False

        if any((origin.is_unix_family, origin.is_ha_connection)):
            return True

        ui_allowlist = await self.middleware.call("system.general.get_ui_allowlist")
        if not ui_allowlist:
            return True
        elif addr_in_allowlist(origin.remote_addr, ui_allowlist):
            return True

        return False

    async def process(self, origin: ConnectionOrigin, ws: WebSocketResponse):
        raise NotImplementedError
