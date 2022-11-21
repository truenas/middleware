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

    def start(self):
        with RLOCK.acquire():
            if VrrpThreadService.VTHR is not None and not VrrpThreadService.VTHR.is_alive():
                VrrpThreadService.VTHR = VrrpFifoThread(middleware=self.middleware)
                VrrpThreadService.VTHR.start()

    def stop(self):
        with RLOCK.acquire():
            if VrrpThreadService.VTHR is not None and VrrpThreadService.VTHR.is_alive():
                VrrpThreadService.VTHR.shutdown()

    def start_or_stop(self, middleware_is_shutting_down=False):
        is_ha = self.middleware.call_sync('failover.licensed')
        with RLOCK.acquire():
            cur_thr = VrrpThreadService.VTHR
            if is_ha and (cur_thr is None or not cur_thr.is_alive()):
                self.start()
            elif (cur_thr is not None and cur_thr.is_alive()) and not is_ha or middleware_is_shutting_down:
                self.stop()


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
