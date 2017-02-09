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
import libzfs
from setproctitle import setproctitle
from syslog import (
    syslog,
    LOG_ALERT,
)


PIDFILE = '/var/run/freenas-snmpd.pid'
SOCKFILE = '/var/run/freenas-snmpd.sock'
QUIT_FLAG = threading.Event()  # Termination Event

# Global Dicts
# The following contain zilstat results from the last
# zilstat command (1, 5 and 10 second intervals)
zilstat_one = {}
zilstat_five = {}
zilstat_ten = {}
# This is for zpool iostat (total and 1 sec results)
zpoolio_all = {}
zpoolio_one = {}
# This is for properly teminating all subprocess when freenas-snmpd is killed
proc_pid_list = []

# global data lock
lock = threading.Lock()

size_dict = {"K": 1024,
             "M": 1048576,
             "G": 1073741824,
             "T": 1099511627776}


# Method to convert 1K --> 1024 and so on
def unprettyprint(ster):
    num = 0.0
    try:
        num = float(ster)
    except:
        try:
            num = float(ster[:-1]) * size_dict[ster[-1]]
        except:
            pass
    return int(num)


# Our custom terminate signal handler
# is called when the daemon recieves signal.SIGTERM
def cust_terminate(signal_number, stack_frame):
    global proc_pid_list
    QUIT_FLAG.set()
    time.sleep(0.01)
    # Try to terminate all subprocesses on exit
    for pd in proc_pid_list:
        try:
            os.killpg(pd, signal.SIGTERM)
        except:
            # Maybe this process has already ended?
            pass
    exception = SystemExit(
        "\nfreenas-snmpd Terminating on SIGTERM\n")
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
            SockHandler(*client)


class SockHandler(asyncore.dispatcher_with_send):

    def __init__(self, sock, addr):
        asyncore.dispatcher_with_send.__init__(self, sock)
        self.addr = addr
        self.buffer = ''
        self.end = False

    def handle_read(self):
        global zilstat_one
        global zilstat_five
        global zilstat_ten
        global zpoolio_all
        with lock:
            tmp_data = {
                "zil_data": {
                    "1": zilstat_one.copy(),
                    "5": zilstat_five.copy(),
                    "10": zilstat_ten.copy()
                },
                "zpool_data": {
                    "1": zpoolio_one.copy(),
                    "all": zpoolio_all.copy()
                }
            }
        res = None
        a = self.recv(8192)
        if a.startswith("get_zilstat_1_second_interval"):
            res = tmp_data["zil_data"]["one"]
        if a.startswith("get_zilstat_5_second_interval"):
            res = tmp_data["zil_data"]["five"]
        if a.startswith("get_zilstat_10_second_interval"):
            res = tmp_data["zil_data"]["ten"]
        if a.startswith("get_zpoolio_1_second_interval"):
            res = tmp_data["zpool_data"]["one"]
        if a.startswith("get_all"):
            res = tmp_data
        self.buffer = json.dumps(res)
        self.end = True

    def writable(self):
        return (len(self.buffer) > 0)

    def handle_write(self):
        self.socket.sendall(self.buffer)
        self.buffer = ''
        if self.end:
            self.close()

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
    global proc_pid_list
    zilstatproc = subprocess.Popen(
        ['/usr/local/bin/zilstat', str(interval), '1'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,
    )
    ppid = zilstatproc.pid
    with lock:
        proc_pid_list.append(ppid)
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
    with lock:
        try:
            proc_pid_list.remove(ppid)
        except ValueError:
            # Its not in the list?
            pass
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


class zpoolioWorker(threading.Thread):
    def __init__(self):
        super(zpoolioWorker, self).__init__()
        self.daemon = True

    def run(self):
        global zpoolio_one
        global zpoolio_all
        zfs = libzfs.ZFS()
        previous_values = {}
        while not QUIT_FLAG.wait(1.0):
            rv = {}
            for pool in zfs.pools:
                next_val = {
                    'pool': pool.name,
                    'alloc': unprettyprint(pool.properties['allocated'].value),
                    'free': unprettyprint(pool.properties['free'].value),
                    'opread': pool.root_vdev.stats.ops[libzfs.ZIOType.READ],
                    'opwrite': pool.root_vdev.stats.ops[libzfs.ZIOType.WRITE],
                    'bwread': pool.root_vdev.stats.bytes[libzfs.ZIOType.READ],
                    'bwrite': pool.root_vdev.stats.bytes[libzfs.ZIOType.WRITE],
                }
                try:
                    update_dict = {
                        'opread': next_val['opread'] - previous_values[pool.name]['opread'],
                        'opwrite': next_val['opwrite'] - previous_values[pool.name]['opwrite'],
                        'bwread': next_val['bwread'] - previous_values[pool.name]['bwread'],
                        'bwrite': next_val['bwrite'] - previous_values[pool.name]['bwrite'],
                    }
                except KeyError:
                    # This means that the 'previous_values' dict does not contain this
                    # pool (maybe it was just added or maybe we just started this worker)
                    # and thus there is nothing to report at this point for this pool
                    pass
                else:
                    # If the Key Error exception was not raised then do the following
                    rv[pool.name] = next_val.copy()
                    rv[pool.name].update(update_dict)
                finally:
                    # In either case we want the next previous_value's pool.name key to contain
                    # the current next_val
                    previous_values[pool.name] = next_val.copy()
            with lock:
                zpoolio_one = rv.copy()
                zpoolio_all = previous_values.copy()

if __name__ == '__main__':

    pidfile = PidFile(PIDFILE)

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
        setproctitle('freenas-snmpd')
        loop_thread = Loop_Sockserver()
        loop_thread.start()
        z1 = zilOneWorker()
        z5 = zilFiveWorker()
        z10 = zilTenWorker()
        zio = zpoolioWorker()
        z1.start()
        z5.start()
        z10.start()
        zio.start()
        # stupid while true to keep main loop active
        # fix this if possible
        while True:
            time.sleep(0.5)
