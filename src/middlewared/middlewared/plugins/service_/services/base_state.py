from collections import namedtuple
import logging

logger = logging.getLogger(__name__)

ServiceState = namedtuple("ServiceState", ["running", "pids"])
