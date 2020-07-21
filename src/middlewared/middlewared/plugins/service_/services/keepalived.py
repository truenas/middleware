from .base import SimpleService


class KeepalivedService(SimpleService):

    name = 'keepalived'
    systemd_unit = 'keepalived'
    reloadable = True

    etc = ['keepalived']

    async def reload(self):
        await self._systemd_unit('keepalived', 'reload')
