"""
Will read integers from stdin and submit tasks that execute specified number of seconds
In parallel, will print pool state every second
"""

import time

from middlewared.logger import setup_logging
from middlewared.utils.io_thread_pool_executor import IoThreadPoolExecutor
from middlewared.utils import start_daemon_thread


def monitor_executor(executor):
    while True:
        print(" ".join([repr(worker) for worker in executor.workers]))
        time.sleep(1)


if __name__ == "__main__":
    setup_logging("middleware", "TRACE", "console")

    executor = IoThreadPoolExecutor("IoThread", 5)
    start_daemon_thread(target=monitor_executor, args=(executor,))

    while True:
        sleep = int(input())
        print(f"Starting task {sleep} seconds long")
        executor.submit(time.sleep, sleep)
