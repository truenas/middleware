from .base import SimpleService


class KeepalivedService(SimpleService):

    name = 'keepalived'
    systemd_unit = 'keepalived'
    reloadable = True
    restartable = True

    etc = ['keepalived']

    async def restart(self):
        # NOTE: this causes all interfaces on the node
        # to send an advertisement with priority 0
        # which means transition from MASTER to BACKUP
        await self._systemd_unit('keepalived', 'restart')

    async def reload(self):
        await self._systemd_unit('keepalived', 'reload')
