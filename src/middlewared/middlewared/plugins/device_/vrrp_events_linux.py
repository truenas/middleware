import os
import time

from middlewared.utils import start_daemon_thread

VRRP_FIFO_FILE = '/var/run/vrrpd.fifo'
TIMEOUT = 2
VRRP_THREAD = None


def vrrp_hook_license_update(middleware, prev_product_type, *args, **kwargs):

    global VRRP_THREAD

    # get new product_type
    new_product_type = middleware.call_sync('system.product_type')

    if prev_product_type != 'SCALE_ENTERPRISE' and new_product_type == 'SCALE_ENTERPRISE':
        if VRRP_THREAD is None:
            VRRP_THREAD = start_daemon_thread(target=vrrp_fifo_listen, args=(middleware,))


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

    # register hook to be called if/when a license has been uploaded
    # to system changing the product type to 'SCALE_ENTERPRISE'
    middleware.register_hook('system.post_license_update', vrrp_hook_license_update, sync=False)

    # only run on licensed systems
    if await middleware.call('failover.licensed'):
        if VRRP_THREAD is None:
            VRRP_THREAD = start_daemon_thread(target=vrrp_fifo_listen, args=(middleware,))
