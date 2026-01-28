from typing import NamedTuple


class ServiceState(NamedTuple):
    running: bool
    pids: list
