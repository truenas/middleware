import logging
import traceback

log = logging.getLogger('common.log')


def log_traceback(log=log, level=logging.DEBUG):
    """
    Log the whole exception in the stack, line by line
    """
    for line in traceback.format_exc().splitlines():
        log.log(level, line)
