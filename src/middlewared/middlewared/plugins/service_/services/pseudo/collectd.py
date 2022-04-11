import asyncio

from middlewared.plugins.service_.services.base import SimpleService, ServiceState

from middlewared.utils.contextlib import asyncnullcontext


class CollectDService(SimpleService):
    name = "collectd"

    etc = ["collectd"]
    restartable = True

    systemd_unit = "collectd"

    lock = asyncio.Lock()

    async def start(self, _lock=True):
        async with (self.lock if _lock else asyncnullcontext()):
            await self._ensure_rrdcached()
            await super().start()

    async def stop(self, _lock=True):
        async with (self.lock if _lock else asyncnullcontext()):
            await super().stop()

    async def restart(self, _lock=True):
        async with (self.lock if _lock else asyncnullcontext()):
            await self.stop(_lock=False)
            await self.start(_lock=False)

    async def _ensure_rrdcached(self):
        if not await self.middleware.call("service.started", "rrdcached"):
            # Let's ensure that before we start collectd, rrdcached is always running
            await self.middleware.call("service.start", "rrdcached")


class RRDCacheDService(SimpleService):
    name = "rrdcached"

    restartable = True

    systemd_unit = "rrdcached"

    async def stop(self):
        await self.middleware.call("service.stop", "collectd")
        await super().stop()

    async def restart(self):
        await self.stop()
        await self.start()

        await self.middleware.call("service.start", "collectd")
