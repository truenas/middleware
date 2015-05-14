#!/usr/local/bin/python

import os
import sys
import errno
import signal
import time
import subprocess
import daemon
import threading
import fcntl
import socket
import asyncore
import json
from setproctitle import setproctitle
from syslog import (
    syslog,
    LOG_ALERT,
    LOG_ERR,
)


PIDFILE = '/var/run/zilstatd.pid'
SOCKFILE = '/var/run/zilstatd.sock'
QUIT_FLAG = threading.Event() # Termination Event

# Global Dicts containing zilstat results from the last
# zilstat command (1, 5 and 10 second intervals)
global zilstat_one
global zilstat_five
global zilstat_ten

lock = threading.Lock()


# Our custom termincate signal handler
# is called when the daemon recieves signal.SIGTERM
def cust_terminate(signal_number, stack_frame):
    QUIT_FLAG.set()
    time.sleep(0.01)
    exception = SystemExit(
            u"\nZilstatd Terminating on SIGTERM\n")
    raise exception


class PidFile(object):

    def __init__(self, path):
        self.path = path
        self.pidfile = None

    def __enter__(self):
        self.pidfile = open(self.path, 'a+')
        try:
            fcntl.flock(self.pidfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise SystemExit('Already running according to ' + self.path)
        self.pidfile.seek(0)
        self.pidfile.truncate()
        self.pidfile.write(str(os.getpid()))
        self.pidfile.flush()
        self.pidfile.seek(0)
        return self.pidfile

    def __exit__(self, *args, **kwargs):
        try:
            if os.path.exists(self.path):
                os.unlink(self.path)
            self.pidfile.close()
        except IOError:
            pass


class SockSelect(asyncore.dispatcher):

    def __init__(self):
        asyncore.dispatcher.__init__(self)
        self.path = SOCKFILE
        self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.set_reuse_addr()
        try:
            self.bind(self.path)
        except socket.error as serr:
            if serr.errno != errno.EADDRINUSE:
                raise serr
            # Delete socket if it prexists when we try to bind
            os.unlink(self.path)
            self.bind(self.path)
        self.listen(5)

    def handle_accept(self):
        client = self.accept()
        if client is None:
            pass
        else:
            handler = SockHandler(*client)


class SockHandler(asyncore.dispatcher_with_send):

    def __init__(self, sock, addr):
        asyncore.dispatcher_with_send.__init__(self, sock)
        self.addr = addr
        self.buffer = ''

    def handle_read(self):
        global zilstat_one
        global zilstat_five
        global zilstat_ten
        res = None
        a = self.recv(8192)
        if a.startswith("get_1_second_interval"):
            with lock:
                res = zilstat_one
        if a.startswith("get_5_second_interval"):
            with lock:
                res = zilstat_five
        if a.startswith("get_10_second_interval"):
            with lock:
                res = zilstat_ten
        self.buffer = json.dumps(res)

    def writable(self):
        return (len(self.buffer) > 0)

    def handle_write(self):
        self.send(self.buffer)
        self.buffer = ''

    def handle_close(self):
        self.close()


class Loop_Sockserver(threading.Thread):
    def __init__(self):
        super(Loop_Sockserver, self).__init__()
        self.daemon = True
        self.obj = SockSelect()

    def run(self):
        try:
            asyncore.loop()
        except Exception as e:
            syslog(LOG_ALERT, str(e))
        finally:
            if os.path.exists(self.obj.path):
                os.unlink(self.obj.path)

    def stop(self):
        self.obj.close()
        self.join()


# Method to parse `zilstat interval 1`
def zfs_zilstat_ops(interval):
    zilstatproc = subprocess.Popen([
        '/usr/local/bin/zilstat',
        str(interval),
        '1',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = zilstatproc.communicate()[0].strip('\n')
    output = output.split('\n')[1].split()
    attrs = {
         'NBytes': output[0],
         'NBytespersec': output[1],
         'NMaxRate': output[2],
         'BBytes': output[3],
         'BBytespersec': output[4],
         'BMaxRate': output[5],
         'ops': output[6],
         'lteq4kb': output[7],
         '4to32kb': output[8],
         'gteq4kb': output[9],
    }
    return attrs


class zilOneWorker(threading.Thread):
    def __init__(self):
        super(zilOneWorker, self).__init__()
        self.daemon = True

    def run(self):
        global zilstat_one
        while not QUIT_FLAG.wait(0.01):
            temp = zfs_zilstat_ops(1)
            with lock:
                zilstat_one = temp


class zilFiveWorker(threading.Thread):
    def __init__(self):
        super(zilFiveWorker, self).__init__()
        self.daemon = True

    def run(self):
        global zilstat_five
        while not QUIT_FLAG.wait(0.01):
            temp = zfs_zilstat_ops(5)
            with lock:
                zilstat_five = temp


class zilTenWorker(threading.Thread):
    def __init__(self):
        super(zilTenWorker, self).__init__()
        self.daemon = True

    def run(self):
        global zilstat_ten
        while not QUIT_FLAG.wait(0.01):
            temp = zfs_zilstat_ops(10)
            with lock:
                zilstat_ten = temp


if __name__ == '__main__':

    pidfile = PidFile('/var/run/zilstatd.pid')

    context = daemon.DaemonContext(
        working_directory='/root',
        umask=0o002,
        pidfile=pidfile,
        stdout=sys.stdout,
        stdin=sys.stdin,
        stderr=sys.stderr,
        detach_process=True,
        signal_map={signal.SIGTERM: cust_terminate},
    )

    with context:
        setproctitle('zilstatd')
        loop_thread = Loop_Sockserver()
        loop_thread.start()
        z1 = zilOneWorker()
        z5 = zilFiveWorker()
        z10 = zilTenWorker()
        z1.start()
        z5.start()
        z10.start()
        # stupid while true to keep main loop active
        # fix this if possible
        while True:
            time.sleep(0.5)
