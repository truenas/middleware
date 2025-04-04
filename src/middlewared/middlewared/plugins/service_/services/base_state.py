import logging
from typing import NamedTuple


logger = logging.getLogger(__name__)


class ServiceState(NamedTuple):
    running: bool
    pids: list
