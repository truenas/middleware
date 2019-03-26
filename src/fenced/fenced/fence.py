import logging
import time

logger = logging.getLogger(__name__)


class Fence(object):

    def __init__(self, interval, force):
        self._interval = interval
        self._force = force

    def run(self):
        self.loop()

    def loop(self):
        while True:
            time.sleep(self._interval)
