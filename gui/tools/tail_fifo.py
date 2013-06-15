#!/usr/local/bin/python
#- 
# Copyright (c) 2013 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

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
PIDFILE = "/var/run/tail_fifo.pid"

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
    os.unlink(PIDFILE)
    sys.exit(0)

def main():
    global TAIL_FIFO
    global PIDFILE

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

    fd = os.open(PIDFILE, os.O_WRONLY | os.O_CREAT)
    os.write(fd, "%d" % os.getpid())
    os.close(fd)

    ret = 0
    for line in tail_file(f):
        line = line.strip()
      
        try:
            fd = os.open(TAIL_FIFO, os.O_WRONLY)
            if os.write(fd, line) <= 0:
                os.close(fd) 
                break
            os.close(fd) 

        except Exception as e:
            print >> sys.stderr, e
            ret = 1
            break

    os.unlink(TAIL_FIFO)
    os.unlink(PIDFILE)
    sys.exit(ret)

if __name__ == '__main__':
    main()
