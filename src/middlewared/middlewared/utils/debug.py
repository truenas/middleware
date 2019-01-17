import sys
import traceback


def get_threads_stacks():
    return {
        thread_id: traceback.format_stack(frame)
        for thread_id, frame in sys._current_frames().items()
    }
