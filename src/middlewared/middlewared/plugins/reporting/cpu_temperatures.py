import threading
import time

from middlewared.service import private, Service
from middlewared.utils.cpu import cpu_temperatures


class ReportingService(Service):
    CACHE = None
    CACHE_LOCK = threading.Lock()
    CACHE_TIME = None
    LOGGED_ERROR = False

    @private
    def cpu_temperatures(self):
        with self.CACHE_LOCK:
            if self.CACHE_TIME is None or time.monotonic() - self.CACHE_TIME >= 60:
                try:
                    self.CACHE = cpu_temperatures()
                except Exception:
                    self.CACHE = {}
                    if not self.LOGGED_ERROR:
                        self.middleware.logger.error("Error gathering CPU temperatures", exc_info=True)
                        self.LOGGED_ERROR = True

                self.CACHE_TIME = time.monotonic()

            return self.CACHE
