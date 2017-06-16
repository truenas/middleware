from middlewared.schema import accepts
from middlewared.service import Service


class TrueNASService(Service):

    class Config:
        private = True

    @accepts()
    async def get_chassis_hardware(self):
        # FIXME: bring code from notifier
        return await self.middleware.call('notifier.get_chassis_hardware')
