#!/usr/local/bin/python

import os
import signal
import sys
import time

WWW_PATH = "/usr/local/www"
FREENAS_PATH = os.path.join(WWW_PATH, "freenasUI")
NOTIFIER_PATH = os.path.join(FREENAS_PATH, "middleware/notifier.py")

sys.path.append(WWW_PATH)
sys.path.append(FREENAS_PATH)

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from freenasUI.common.pipesubr import pipeopen
from signal import (
    signal,
    SIGINT, 
    SIGQUIT,
    SIGABRT,
    SIGTERM,
    SIGHUP
)

TAIL_FIFO = "/var/tmp/tail_fifo"

def tail_file(thefile):
    thefile.seek(0,2)
    sleep = 0.00001
    while True:
        line = thefile.readline()
        if not line:
            time.sleep(sleep)
            if sleep < 1.0:
                sleep += 0.00001
            continue
        sleep = 0.00001
        yield line

def cleanup(*args):
    os.unlink(TAIL_FIFO)
    sys.exit(0)

def main():
    global TAIL_FIFO

    if len(sys.argv) < 2:
        print >> sys.stderr, "Usage: %s <file>" % sys.argv[0]
        sys.exit(1)

    thefile = sys.argv[1]
    try:
        f = open(thefile)

    except Exception as e:
        print >> sys.stderr, e
        sys.exit(1)

    if len(sys.argv) > 2:
        TAIL_FIFO = sys.argv[2]

    if not os.access(TAIL_FIFO, os.F_OK):
        try:
            os.mkfifo(TAIL_FIFO)

        except Exception as e:
            print >> sys.stderr, e
            sys.exit(1)

    signal(SIGINT, cleanup)
    signal(SIGQUIT, cleanup)
    signal(SIGABRT, cleanup)
    signal(SIGTERM, cleanup)
    signal(SIGHUP, cleanup)

    ret = 0
    for line in tail_file(f):
        line = line.strip()
      
        try:
            fd = os.open(TAIL_FIFO, os.O_WRONLY)
            if os.write(fd, line) <= 0:
                os.close(fd) 
                break
            os.close(fd) 

        except Except as e:
            print >> sys.stderr, e
            ret = 1
            break

    os.unlink(TAIL_FIFO)
    sys.exit(ret)

if __name__ == '__main__':
    main()
