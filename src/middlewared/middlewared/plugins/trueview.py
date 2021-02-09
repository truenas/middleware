from middlewared.event import EventSource

import json
import subprocess
import time


class TrueViewStatusEventSource(EventSource):

    """
    Retrieve True View Statistics. An integer `delay` argument can be specified to determine the delay
    on when the periodic event should be generated.
    """

    def run_sync(self):

        try:
            if self.arg:
                delay = int(self.arg)
            else:
                delay = 10
        except ValueError:
            return

        # Delay too slow
        if delay < 5:
            return

        while not self._cancel_sync.is_set():
            cp = subprocess.run(
                ['trueview_stats.sh'], stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            try:
                data = json.loads(cp.stdout)
            except ValueError:
                pass
            else:
                self.send_event('ADDED', fields=data)
            time.sleep(delay)


def setup(middleware):
    middleware.register_event_source('trueview.stats', TrueViewStatusEventSource)
