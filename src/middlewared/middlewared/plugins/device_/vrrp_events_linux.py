import os

from middlewared.utils import start_daemon_thread

VRRP_FIFO_FILE = '/var/run/vrrpd.fifo'


def vrrp_fifo_listen(middleware):

    # create the fifo, ignoring if it already exists
    try:
        os.mkfifo(VRRP_FIFO_FILE)
    except FileExistsError:
        pass

    while True:
        with open(VRRP_FIFO_FILE) as f:
            middleware.logger.info('vrrp fifo connection established')
            # all vrrp messages are terminated with a newline
            for line in f:
                middleware.call_hook_sync('vrrp.fifo', data=line)


def setup(middleware):
    start_daemon_thread(target=vrrp_fifo_listen, args=(middleware,))
