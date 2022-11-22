from threading import RLock
from asyncio import ensure_future

from middlewared.service import Service
from .vrrp_thread import VrrpFifoThread

RLOCK = RLock()


class VrrpThreadService(Service):

    class Config:
        namespace = 'vrrp.thread'
        private = True

    VTHR = None

    def is_running(self):
        running = False
        with RLOCK:
            running = VrrpThreadService.VTHR is not None and VrrpThreadService.VTHR.is_alive()

        return running

    def start(self, bypass=False):
        with RLOCK:
            if bypass or not self.is_running():
                VrrpThreadService.VTHR = VrrpFifoThread(middleware=self.middleware)
                VrrpThreadService.VTHR.start()

    def stop(self, bypass=False):
        with RLOCK:
            if bypass or self.is_running():
                VrrpThreadService.VTHR.shutdown()

    def start_or_stop(self, middleware_is_shutting_down=False):
        is_ha = self.middleware.call_sync('failover.licensed')
        with RLOCK:
            already_running = self.is_running()
            if is_ha and not already_running:
                # 1. HA system so it should always be running
                self.start(bypass=True)
            elif already_running and not is_ha or middleware_is_shutting_down:
                # 1. middlewarwe process is shutting down
                # 2. or system is being downgraded from an HA to non-HA system (very rare)
                self.stop(bypass=True)


async def _event_system(middleware, *args, **kwargs):
    try:
        shutting_down = args[1]['id'] == 'shutdown'
    except (IndexError, KeyError):
        shutting_down = False

    await middleware.call('vrrp.thread.start_or_stop', shutting_down)


async def setup(middleware):
    ensure_future(_event_system(middleware))  # start thread on middlewared service start/restart
    middleware.register_hook('system', _event_system)  # catch shutdown event and clean up thread
    middleware.register_hook('system.post_license_update', _event_system)  # catch license change
