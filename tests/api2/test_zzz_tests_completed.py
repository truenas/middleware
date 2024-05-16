import faulthandler
import threading


def test__thread_count(request):
    """Having outstanding threads can prevent python from exiting cleanly."""
    count = threading.active_count()
    if count > 1:
        faulthandler.dump_traceback()
        with open('threads.trace', 'w') as f:
            faulthandler.dump_traceback(f)
        assert count == 1
