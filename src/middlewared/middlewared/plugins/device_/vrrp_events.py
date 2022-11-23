from os import mkfifo
from prctl import set_name
from threading import Thread
from time import sleep
from asyncio import ensure_future


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


async def _event_system(middleware, *args, **kwargs):
    global VRRP_THREAD
    try:
        shutting_down = args[1]['id'] == 'shutdown'
    except (IndexError, KeyError):
        shutting_down = False

    licensed = await middleware.call('failover.licensed')
    if licensed and (VRRP_THREAD is None or not VRRP_THREAD.is_alive()):
        # if this is a system that is being licensed for HA for the
        # first time (without being rebooted) then we need to make
        # sure we start this.
        VRRP_THREAD = VrrpFifoThread(middleware=middleware)
        VRRP_THREAD.start()
    elif (VRRP_THREAD is not None and VRRP_THREAD.is_alive()) and not licensed or shutting_down:
        # maybe the system is being downgraded to non-HA
        # (this is rare but still need to handle it) or
        # system is being restarted/shutdown etc
        await middleware.run_in_thread(VRRP_THREAD.shutdown)
        VRRP_THREAD = None


async def setup(middleware):
    ensure_future(_event_system(middleware))  # start thread on middlewared service start/restart
    middleware.register_hook('system', _event_system)  # catch shutdown event and clean up thread
    middleware.register_hook('system.post_license_update', _event_system)  # catch license change
