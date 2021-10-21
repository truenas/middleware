from middlewared.plugins.devd_.devd_events import devd_connected
from middlewared.service import Service


class DevdService(Service):

    class Config:
        private = True

    async def connected(self):
        return await devd_connected()
