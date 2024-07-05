import faulthandler
import threading

from middlewared.test.integration.utils.client import truenas_server


def test__thread_count(request):
    """Having outstanding threads can prevent python from exiting cleanly."""

    # Tear down our persistent connection
    truenas_server.client.close()
    truenas_server._client = None

    count = threading.active_count()
    if count > 1:
        faulthandler.dump_traceback()
        with open('threads.trace', 'w') as f:
            faulthandler.dump_traceback(f)
        assert count == 1
