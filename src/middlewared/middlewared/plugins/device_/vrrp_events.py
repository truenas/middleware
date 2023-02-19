from os import mkfifo
from prctl import set_name
from threading import Thread
from time import sleep
VRRP_THREAD = None


class VrrpFifoThread(Thread):

    def __init__(self, *args, **kwargs):
        super(VrrpFifoThread, self).__init__()
        self._retry_timeout = 2  # timeout in seconds before retrying to connect to FIFO
        self._vrrp_file = '/var/run/vrrpd.fifo'
        self.middleware = kwargs.get('middleware')
        self.logger = self.middleware.logger
        self.shutdown_line = '--SHUTDOWN--\n'

    def shutdown(self):
        with open(self._vrrp_file, 'w') as f:
            f.write(self.shutdown_line)

    def create_fifo(self):
        try:
            mkfifo(self._vrrp_file)
        except FileExistsError:
            pass
        except Exception:
            raise

    def run(self):
        set_name('vrrp_fifo_thread')
        try:
            self.create_fifo()
        except Exception:
            self.logger.error('FATAL: Unable to create VRRP fifo.', exc_info=True)
            return

        log_it = True
        while True:
            try:
                with open(self._vrrp_file) as f:
                    self.logger.info('vrrp fifo connection established')
                    for line in f:
                        if line == self.shutdown_line:
                            return
                        else:
                            self.middleware.call_hook_sync('vrrp.fifo', data=line)
            except Exception:
                if log_it:
                    self.logger.warning(
                        'vrrp fifo connection not established, retrying every %d seconds',
                        self._retry_timeout,
                        exc_info=True
                    )
                    log_it = False
                    sleep(self._retry_timeout)


async def _start_stop_vrrp_thread(middleware, *, shutting_down=False):
    global VRRP_THREAD

    licensed = await middleware.call('failover.licensed')
    if (not licensed or shutting_down) and (VRRP_THREAD is not None and VRRP_THREAD.is_alive()):
        # maybe the system is being downgraded to non-HA
        # (this is rare but still need to handle it) or
        # system is being restarted/shutdown etc
        await middleware.run_in_thread(VRRP_THREAD.shutdown)
        VRRP_THREAD = None
    elif licensed and (VRRP_THREAD is None or not VRRP_THREAD.is_alive()):
        # if this is a system that is being licensed for HA for the
        # first time (without being rebooted) then we need to make
        # sure we start this.
        VRRP_THREAD = VrrpFifoThread(middleware=middleware)
        VRRP_THREAD.start()


async def _event_system_ready(middleware, event_type, args):
    await _start_stop_vrrp_thread(middleware)


async def _event_system_shutdown(middleware, event_type, args):
    await _start_stop_vrrp_thread(middleware, shutting_down=True)


async def _post_license_update(middleware, *args, **kwargs):
    await _start_stop_vrrp_thread(middleware)


async def setup(middleware):
    middleware.create_task(_start_stop_vrrp_thread(middleware))  # start thread on middlewared service start/restart
    middleware.event_subscribe('system.ready', _event_system_ready)
    middleware.event_subscribe('system.shutdown', _event_system_shutdown)  # catch shutdown event and clean up thread
    middleware.register_hook('system.post_license_update', _post_license_update)  # catch license change
