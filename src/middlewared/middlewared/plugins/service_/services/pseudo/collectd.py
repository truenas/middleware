import asyncio

from middlewared.plugins.service_.services.base import SimpleService, ServiceState

from middlewared.utils.contextlib import asyncnullcontext


class CollectDService(SimpleService):
    name = "collectd"

    etc = ["collectd"]
    restartable = True

    freebsd_rc = "collectd-daemon"

    lock = asyncio.Lock()

    async def _get_state_freebsd(self):
        return ServiceState(
            (await self._freebsd_service("collectd-daemon", "status")).returncode == 0,
            [],
        )

    async def _start_freebsd(self, _lock=True):
        async with (self.lock if _lock else asyncnullcontext()):
            await self._freebsd_ensure_rrdcached()
            await super()._start_freebsd()

    async def _stop_freebsd(self, _lock=True):
        async with (self.lock if _lock else asyncnullcontext()):
            await super()._stop_freebsd()

    async def _restart_freebsd(self, _lock=True):
        async with (self.lock if _lock else asyncnullcontext()):
            await self._stop_freebsd(_lock=False)
            await self._start_freebsd(_lock=False)

    async def _freebsd_ensure_rrdcached(self):
        if not await self.middleware.call("service.started", "rrdcached"):
            # Let's ensure that before we start collectd, rrdcached is always running
            await self.middleware.call("service.start", "rrdcached")


class RRDCacheDService(SimpleService):
    name = "rrdcached"

    freebsd_rc = "rrdcached"

    async def _start_freebsd(self):
        await super()._start_freebsd()
        await self.middleware.call("service.start", "collectd")

    async def _stop_freebsd(self):
        await self.middleware.call("service.stop", "collectd")
        await super()._stop_freebsd()
