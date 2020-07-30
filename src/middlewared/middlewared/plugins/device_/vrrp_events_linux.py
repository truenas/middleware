import asyncio
import os

from middlewared.service import private, Service

VRRP_FIFO_CONNECTED = False
VRRP_FIFO_FILE = '/var/run/vrrpd.fifo'


class VrrpFifoService(Service):

    @private
    async def vrrp_fifo_connected(self):
        return VRRP_FIFO_CONNECTED


async def vrrp_fifo_listen(middleware):

    global VRRP_FIFO_CONNECTED

    # create the fifo, ignoring if it already exists
    try:
        os.mkfifo(VRRP_FIFO_FILE)
    except FileExistsError:
        pass

    # all vrrp messages are terminated with a newline
    while True:
        with open(VRRP_FIFO_FILE) as f:
            VRRP_FIFO_CONNECTED = True
            middleware.logger.info('vrrp fifo connection established')
            for line in f:
                await middleware.call_hook('vrrp.fifo', data=line)


def setup(middleware):
    asyncio.ensure_future(vrrp_fifo_listen(middleware))
