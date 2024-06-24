import time

import psutil

from middlewared.event import EventSource
from middlewared.service import CallError


class ProcessesEventSource(EventSource):
    """
    Retrieve currently running processes stats.

    Usage: reporting.processes:{"interval": 10, "cpu_percent": 0.1, "memory_percent": 0.1}
    """

    def run_sync(self):
        options = {
            "interval": 10,
            "cpu_percent": 0.1,
            "memory_percent": 0.1,
            **(self.arg or {})
        }
        if options["interval"] < 5:
            raise CallError("Interval should be >= 5")

        processes = {}
        first_iteration = True
        while not self._cancel_sync.is_set():
            iteration_processes = {}
            for p in psutil.process_iter(["cmdline", "cpu_percent", "memory_percent", "num_threads"]):
                existing_process = processes.get(p)
                if existing_process is not None:
                    p = existing_process  # Keep previously observed CPU time value

                iteration_processes[p] = p

            processes = iteration_processes

            result = []
            for process in processes.values():
                if (
                    process.memory_percent() < options["memory_percent"] and
                    process.cpu_percent() < options["cpu_percent"]
                ):
                    continue

                row = {
                    "cmdline": " ".join(process.cmdline()).strip(),
                    "cpu_percent": process.cpu_percent(),
                    "memory_percent": process.memory_percent(),
                    "num_threads": process.num_threads(),
                    "pid": process.pid,
                }

                result.append(row)

            if not first_iteration:
                self.send_event("ADDED", fields={"processes": result})

            first_iteration = False

            time.sleep(options["interval"])


def setup(middleware):
    middleware.register_event_source("reporting.processes", ProcessesEventSource, roles=['REPORTING_READ'])
