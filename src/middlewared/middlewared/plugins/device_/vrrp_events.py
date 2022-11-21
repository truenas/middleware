import threading

from os import mkfifo
from prctl import set_name
from time import sleep
from asyncio import ensure_future

VRRP_THREAD_NAME = 'vrrp_fifo'


class VrrpFifoThread(threading.Thread):

    def __init__(self, *args, **kwargs):
        super(VrrpFifoThread, self).__init__()
        self._retry_timeout = 2  # timeout in seconds before retrying to connect to FIFO
        self._vrrp_file = '/var/run/vrrpd.fifo'
        self.middleware = kwargs.get('middleware')
        self.logger = self.middleware.logger
        self.shutdown_line = '--SHUTDOWN--\n'
        self.name = VRRP_THREAD_NAME

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
        set_name(VRRP_THREAD_NAME)
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


def start_or_stop_vrrp_thread(middleware, licensed, shutting_down):
    try:
        vthread = [i for i in threading.enumerate() if i.name == VRRP_THREAD_NAME][0]
    except IndexError:
        vthread = None

    if licensed and (not vthread or not vthread.is_alive()):
        VrrpFifoThread(middleware=middleware).start()
    elif (vthread and vthread.is_alive()) and not licensed or shutting_down:
        vthread.shutdown()


async def _event_system(middleware, *args, **kwargs):
    try:
        shutting_down = args[1]['id'] == 'shutdown'
    except (IndexError, KeyError):
        shutting_down = False

    licensed = await middleware.call('failover.licensed')
    await middleware.run_in_thread(start_or_stop_vrrp_thread, middleware, licensed, shutting_down)


async def setup(middleware):
    ensure_future(_event_system(middleware))  # start thread on middlewared service start/restart
    middleware.register_hook('system', _event_system)  # catch shutdown event and clean up thread
    middleware.register_hook('system.post_license_update', _event_system)  # catch license change
