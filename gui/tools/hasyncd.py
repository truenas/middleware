#!/usr/bin/env python

from ctypes import cdll, byref, create_string_buffer
from ctypes.util import find_library
from SimpleXMLRPCServer import SimpleXMLRPCServer
import fcntl
import os
import sys

import daemon


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


class Funcs(object):

    def __init__(self, *args, **kwargs):
        from django.db import connection
        self._conn = connection
        super(Funcs, self).__init__(*args, **kwargs)

    def ping(self):
        return 'pong'

    def run_sql(self, query, params):
        cursor = self._conn.cursor()
        if params is None:
            cursor.executelocal(query)
        else:
            cursor.executelocal(query, params)

    def sync_from(self, query, params):
        self._conn.dump_recv(query)


def set_proc_name(newname):
    libc = cdll.LoadLibrary(find_library('c'))
    buff = create_string_buffer(len(newname) + 1)
    buff.value = newname
    libc.setproctitle(byref(buff))


if __name__ == '__main__':

    pidfile = PidFile('/var/run/hasyncd.pid')

    context = daemon.DaemonContext(
        working_directory='/root',
        umask=0o002,
        pidfile=pidfile,
        stdout=sys.stdout,
        stdin=sys.stdin,
        stderr=sys.stderr,
        detach_process=True,
    )

    with context:
        set_proc_name('hasyncd')
        sys.path.extend([
            '/usr/local/www',
            '/usr/local/www/freenasUI'
        ])

        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

        # Make sure to load all modules
        from django.db.models.loading import cache
        cache.get_apps()

        from freenasUI.freeadmin.utils import set_language
        set_language()

        server = SimpleXMLRPCServer(('0.0.0.0', 8000), allow_none=True)
        server.register_instance(Funcs())
        server.serve_forever()
