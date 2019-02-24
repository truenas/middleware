import os
import signal


async def render(service, middleware):
    os.kill(1, signal.SIGHUP)
