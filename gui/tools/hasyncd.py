#!/usr/bin/env python

from ctypes import cdll, byref, create_string_buffer
from ctypes.util import find_library
from SimpleXMLRPCServer import SimpleXMLRPCServer
import fcntl
import logging
import logging.config
import os
import socket
import sys
import threading
import xmlrpclib

import daemon

LOG_FILE = '/var/log/hasyncd.log'


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


class JournalAlive(threading.Thread):

    def __init__(self, *args, **kwargs):
        self.sleep = threading.Event()
        logger = kwargs.pop('logger', None)
        if not logger:
            self.logger = logging.getLogger('hasyncd.journal')
        else:
            self.logger = log
        super(JournalAlive, self).__init__(*args, **kwargs)

    def run(self):
        from freenasUI.freeadmin.sqlite3_ha.base import Journal
        from freenasUI.middleware.notifier import notifier

        while True:
            self.sleep.wait(5)
            if Journal.is_empty():
                continue

            ip = notifier().failover_peerip()
            if ip is None:
                continue

            s = xmlrpclib.ServerProxy('http://%s:8000' % ip, allow_none=True)

            with Journal() as j:
                for q in list(j.queries):
                    query, params = q
                    try:
                        s.run_sql(query, params)
                        j.queries.remove(q)
                    except xmlrpclib.Fault, e:
                        self.logger.exception('Failed to run sql')
                        break
                    except socket.error:
                        break


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

    def sync_from(self, query):
        return self._conn.dump_recv(query)

    def sync_to(self):
        return self._conn.dump_send()


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
        stderr=sys.stderr,
        detach_process=True,
    )

    with context:

        logging.config.dictConfig({
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'simple': {
                    'format': '%(levelname)s %(asctime)s: %(message)s'
                },
            },
            'handlers': {
                'file': {
                    'level': 'DEBUG',
                    'filters': [],
                    'class': 'logging.handlers.RotatingFileHandler',
                    'maxBytes': 1024 * 1024 * 10,
                    'backupCount': 5,
                    'filename': LOG_FILE,
                    'formatter': 'simple',
                },
            },
            'loggers': {
                'hasyncd': {
                    'handlers': ['file'],
                    'level': 'DEBUG',
                    'propagate': True,
                },
            }
        })

        if os.path.exists(LOG_FILE):
            os.chmod(LOG_FILE, 0o660)

        log = logging.getLogger('hasyncd')

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

        from freenasUI.middleware.notifier import notifier
        ip = notifier().failover_peerip()
        if ip is None:
            log.debug('No failover peer ip, exiting.')
            sys.exit(0)

        log.debug('Starting Journal')

        ja = JournalAlive(logger=log)
        ja.daemon = True
        ja.start()

        server = SimpleXMLRPCServer(
            ('0.0.0.0', 8000),
            allow_none=True,
            logRequests=False,
        )
        server.register_instance(Funcs())
        server.serve_forever()
