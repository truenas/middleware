from logging import getLogger
from os import mkfifo
from threading import Thread
from time import sleep, time

from middlewared.utils.prctl import set_name

VRRP_THREAD = None
LOGGER = getLogger('failover')  # so logs show up in /var/log/failover.log


class VrrpFifoThread(Thread):

    def __init__(self, *args, **kwargs):
        super(VrrpFifoThread, self).__init__()
        self._retry_timeout = 2  # timeout in seconds before retrying to connect to FIFO
        self._vrrp_file = '/var/run/vrrpd.fifo'
        self.middleware = kwargs.get('middleware')
        self.shutdown_line = '--SHUTDOWN--'

    def shutdown(self):
        with open(self._vrrp_file, 'w') as f:
            f.write(f'{self.shutdown_line}\n')

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
            LOGGER.error('FATAL: Unable to create VRRP fifo.', exc_info=True)
            return

        log_it = True
        while True:
            try:
                with open(self._vrrp_file) as f:
                    LOGGER.info('vrrp fifo connection established')
                    for line in f:
                        event = line.strip()
                        if event == self.shutdown_line:
                            return
                        elif not self.middleware.call_sync('system.ready'):
                            LOGGER.warning(
                                'Ignoring failover event: %r because system is not ready', event
                            )
                        else:
                            self.middleware.call_hook_sync('vrrp.fifo', data={'event': event, 'time': time()})
            except Exception:
                if log_it:
                    LOGGER.warning(
                        'vrrp fifo connection not established, retrying every %d seconds',
                        self._retry_timeout,
                        exc_info=True
                    )
                    log_it = False
                    sleep(self._retry_timeout)


async def _start_stop_vrrp_thread(middleware):
    global VRRP_THREAD

    licensed = await middleware.call('failover.licensed')
    if not licensed and (VRRP_THREAD is not None and VRRP_THREAD.is_alive()):
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


async def _post_license_update(middleware, *args, **kwargs):
    await _start_stop_vrrp_thread(middleware)


async def setup(middleware):
    middleware.create_task(_start_stop_vrrp_thread(middleware))  # start thread on middlewared service start/restart
    middleware.register_hook('system.post_license_update', _post_license_update)  # catch license change
