__author__ = 'jceel'

import logging
from gevent import subprocess

logger = logging.getLogger('system')


class SubprocessException(Exception):
    def __init__(self, code, out, err):
        self.returncode = code
        self.out = out
        self.err = err


def system(*args, **kwargs):
    sh = kwargs["shell"] if "shell" in kwargs else False
    proc = subprocess.Popen(args, stderr=subprocess.PIPE, shell=sh,
                            stdout=subprocess.PIPE, close_fds=True)
    out, err = proc.communicate()

    logger.debug("Running command: %s", ' '.join(args))

    if proc.returncode != 0:
        logger.warning("Command %s failed, return code %d, stderr output: %s",
                       ' '.join(args), proc.returncode, err)
        raise SubprocessException(proc.returncode, out, err)

    return out, err


# Only use this for running background processes
# for which you do not want subprocess to wait on
# for the output or error (warning: no error handling)
def system_bg(*args, **kwargs):
    sh = False
    to_log = False
    sh = kwargs["shell"] if "shell" in kwargs else False
    to_log = kwargs["to_log"] if "to_log" in kwargs else True
    subprocess.Popen(args, stderr=subprocess.PIPE, shell=sh,
                     stdout=subprocess.PIPE, close_fds=True)
    if to_log:
        logger.debug("Started command (in background) : %s", ' '.join(args))
