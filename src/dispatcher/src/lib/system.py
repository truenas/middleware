__author__ = 'jceel'

import logging
from gevent import subprocess

logger = logging.getLogger('system')


class SubprocessException(Exception):
    def __init__(self, code, out, err):
        self.returncode = code
        self.out = out
        self.err = err


def system(*args):
    proc = subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE, close_fds=True)
    out, err = proc.communicate()

    logger.debug("Running command: %s", ' '.join(args))

    if proc.returncode != 0:
        logger.warning("Command %s failed, return code %d, stderr output: %s", ' '.join(args), proc.returncode, err)
        raise SubprocessException(proc.returncode, out, err)

    return out, err