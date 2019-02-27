import os
import signal


def render(service, middleware):
    os.kill(1, signal.SIGHUP)
