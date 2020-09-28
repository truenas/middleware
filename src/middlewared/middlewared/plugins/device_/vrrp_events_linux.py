import os
import time

from middlewared.utils import start_daemon_thread

VRRP_FIFO_FILE = '/var/run/vrrpd.fifo'
TIMEOUT = 2
VRRP_THREAD = None


def vrrp_fifo_listen(middleware):

    # create the fifo, ignoring if it already exists
    try:
        os.mkfifo(VRRP_FIFO_FILE)
    except FileExistsError:
        pass

    while True:
        try:
            with open(VRRP_FIFO_FILE) as f:
                middleware.logger.info('vrrp fifo connection established')
                # all vrrp messages are terminated with a newline
                for line in f:
                    middleware.call_hook_sync('vrrp.fifo', data=line)
        except Exception:
            middleware.logger.error('vrrp fifo connection not established, retrying')
            # sleep for `TIMEOUT` before trying to open FIFO and send event again
            time.sleep(TIMEOUT)


async def setup(middleware):

    global VRRP_THREAD

    # only run on licensed systems
    if await middleware.call('failover.licensed'):
        if VRRP_THREAD is None:
            VRRP_THREAD = start_daemon_thread(target=vrrp_fifo_listen, args=(middleware,))
