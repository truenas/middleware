import threading

from os import mkfifo
from prctl import set_name
from time import sleep

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
