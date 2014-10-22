__author__ = 'jceel'

from gevent import subprocess

class SubprocessException(Exception):
    def __init__(self, code, out, err):
        self.returncode = code
        self.out = out
        self.err = err

def system(args):
    proc = subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE, close_fds=True)
    out, err = proc.communicate()

    if proc.returncode != 0:
        raise SubprocessException(proc.returncode, out, err)

    return out, err