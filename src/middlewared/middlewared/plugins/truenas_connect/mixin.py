from truenas_connect_utils.request import auth_headers, call

from middlewared.service import private


class TNCAPIMixin:

    @private
    async def auth_headers(self, config: dict) -> dict:
        return auth_headers(config)

    async def _call(self, *args, **kwargs):
        # FIXME: Add network activity check for TNC
        return await call(*args, **kwargs)
