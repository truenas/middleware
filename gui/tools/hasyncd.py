#!/usr/bin/env python

from ctypes import cdll, byref, create_string_buffer
from ctypes.util import find_library
import base64
import fcntl
import logging
import logging.config
import os
import socket
import sys
import threading
import xmlrpclib

from twisted.web.xmlrpc import XMLRPC, withRequest
from twisted.web.server import Site
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

            s = notifier().failover_rpc()

            with Journal() as j:
                for q in list(j.queries):
                    query, params = q
                    try:
                        s.run_sql(query, params)
                        j.queries.remove(q)
                    except xmlrpclib.Fault, e:
                        self.logger.exception('Failed to run sql: %s', e)
                        break
                    except socket.error:
                        break


class HASync(XMLRPC):

    def __init__(self, *args, **kwargs):
        from django.db import connection
        self._conn = connection
        XMLRPC.__init__(self, *args, **kwargs)

    def _ebRender(self, failure):
        return xmlrpclib.Fault(self.FAILURE, str(failure))

    def _authenticated(self, secret):
        from freenasUI.failover.models import Failover
        qs = Failover.objects.filter(secret=secret)
        if not qs.exists():
            raise xmlrpclib.Fault(5, 'Access Denied')
        return qs[0]

    @withRequest
    def xmlrpc_pairing_receive(self, request, secret):
        from freenasUI.failover.models import CARP, Failover
        from freenasUI.failover.utils import (
            delete_pending_pairing,
            get_pending_pairing,
        )
        from freenasUI.storage.models import Volume

        pairing = get_pending_pairing()
        if pairing is None:
            return False
        if secret != pairing.get('secret'):
            return False

        delete_pending_pairing()

        carp = CARP.objects.get(pk=pairing['carp'])
        volume = Volume.objects.get(pk=pairing['volume'])

        failover = Failover()
        failover.volume = volume
        failover.carp = carp
        failover.ipaddress = pairing['ip']
        failover.secret = pairing['secret']
        failover.save()

        return self._conn.dump_send(failover=failover)

    @withRequest
    def xmlrpc_pairing_send(self, request, secret):
        from freenasUI.failover.utils import set_pending_pairing
        try:
            set_pending_pairing(secret=secret, ip=request.getClientIP())
        except Exception as e:
            log.error('Failed set_pending_pairing: %s', e)
            return False
        return True

    def xmlrpc_ping(self):
        return 'pong'

    def xmlrpc_pool_available(self, secret):
        from freenasUI.middleware.notifier import notifier
        failover = self._authenticated(secret)
        p1 = notifier()._pipeopen('zpool list %s' % failover.volume.vol_name)
        p1.communicate()
        return p1.returncode

    def xmlrpc_file_recv(self, secret, path):
        self._authenticated(secret)
        if not os.path.exists(path):
            return None
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read())
        return data

    def xmlrpc_file_send(self, secret, path, content):
        self._authenticated(secret)
        with open(path, 'wb+') as f:
            f.write(base64.b64decode(content))
        return True

    def xmlrpc_run_sql(self, secret, query, params):
        self._authenticated(secret)
        cursor = self._conn.cursor()
        if params is None:
            cursor.executelocal(query)
        else:
            cursor.executelocal(query, params)

    def xmlrpc_sync_to(self, secret, query):
        from freenasUI.failover.models import Failover
        from freenasUI.failover.utils import (
            delete_pending_pairing,
            get_pending_pairing,
        )

        update_ip = False
        if Failover.objects.all().count() == 0:
            # Pairing
            pairing = get_pending_pairing()
            if not pairing:
                return False
            if secret != pairing['secret'] or pairing['verified'] is False:
                return False
            update_ip = True

            delete_pending_pairing()
        else:
            self._authenticated(secret)

        rv = self._conn.dump_recv(query)
        # If this is a pairing action we need to update the IP
        if update_ip and rv:
            Failover.objects.filter(secret=secret).update(
                ipaddress=pairing['ip']
            )
        return rv

    def xmlrpc_sync_from(self, secret):
        failover = self._authenticated(secret)
        return self._conn.dump_send(failover=failover)


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

        log.debug('Starting Journal')

        ja = JournalAlive(logger=log)
        ja.daemon = True
        ja.start()

        r = HASync(allowNone=True)

        # reactor must imported within the daemon context
        # otherwise it will cause a 100% cpu usage
        from twisted.internet import reactor
        reactor.listenTCP(8000, Site(r))
        reactor.run()
