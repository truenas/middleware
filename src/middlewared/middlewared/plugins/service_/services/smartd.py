import logging

from .base import SimpleService

logger = logging.getLogger(__name__)


class SMARTDService(SimpleService):
    name = "smartd"
    reloadable = True

    etc = ["rc", "smartd"]

    systemd_unit = "smartmontools"
    systemd_async_start = True

    async def after_start(self):
        await self.middleware.call('service.restart', 'netdata')
