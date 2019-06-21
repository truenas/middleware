import threading
import time
import os
import pybonjour
import queue
import select
import socket
import subprocess

from bsd.threading import set_thread_name
from pybonjour import (
    kDNSServiceFlagsMoreComing,
    kDNSServiceFlagsAdd,
    kDNSServiceErr_NoError
)

from middlewared.service import Service, private


class mDNSDaemonMonitor(threading.Thread):

    instance = None

    def __init__(self, middleware):
        super(mDNSDaemonMonitor, self).__init__(daemon=True)
        self.middleware = middleware
        self.logger = self.middleware.logger
        self.mdnsd_pidfile = "/var/run/mdnsd.pid"
        self.mdnsd_piddir = "/var/run/"
        self.mdnsd_running = threading.Event()
        self.dns_sync = threading.Event()

        if self.__class__.instance:
            raise RuntimeError('Can only be instantiated a single time')
        self.__class__.instance = self
        self.start()

    def run(self):
        set_thread_name('mdnsd_monitor')
        while True:
            """
            If the system has not completely booted yet we need to way at least
            for DNS to be configured.

            In case middlewared is started after boot, system.ready will be set after this plugin
            is loaded, hence the dns_sync timeout.
            """
            if not self.middleware.call_sync('system.ready'):
                if not self.dns_sync.wait(timeout=2):
                    continue

            pid = self.is_alive()
            if not pid:
                self.start_mdnsd()
                time.sleep(2)
                continue
            kqueue = select.kqueue()
            try:
                kqueue.control([
                    select.kevent(
                        pid,
                        filter=select.KQ_FILTER_PROC,
                        flags=select.KQ_EV_ADD,
                        fflags=select.KQ_NOTE_EXIT,
                    )
                ], 0, 0)
            except ProcessLookupError:
                continue
            self.mdnsd_running.set()
            self.middleware.call_sync('mdnsadvertise.restart')
            kqueue.control(None, 1)
            self.mdnsd_running.clear()
            kqueue.close()

    def is_alive(self):
        if not os.path.exists(self.mdnsd_pidfile):
            return False

        try:
            with open(self.mdnsd_pidfile, 'r') as f:
                pid = int(f.read().strip())

            os.kill(pid, 0)
        except (FileNotFoundError, ProcessLookupError, ValueError):
            return False
        except Exception as e:
            self.logger.debug('Failed to read mdnsd pidfile', exc_info=True)
            return False

        return pid

    def start_mdnsd(self):
        p = subprocess.Popen(["/usr/local/etc/rc.d/mdnsd", "onestart"])
        p.wait()
        return p.returncode == 0


class mDNSThread(threading.Thread):
    def __init__(self, **kwargs):
        super(mDNSThread, self).__init__()
        self.setDaemon(True)
        self.middleware = kwargs.get('middleware')
        self.logger = self.middleware.logger
        self.timeout = kwargs.get('timeout', 30)

    def active(self, sdRef):
        return (bool(sdRef) and sdRef.fileno() != -1)


class mDNSServiceThread(threading.Thread):
    def __init__(self, **kwargs):
        super(mDNSServiceThread, self).__init__()
        self.setDaemon(True)
        self.service = kwargs.get('service')
        self.middleware = kwargs.get('middleware')
        self.logger = self.middleware.logger
        self.hostname = kwargs.get('hostname')
        self.service = kwargs.get('service')
        self.regtype = kwargs.get('regtype')
        self.port = kwargs.get('port')
        self.finished = threading.Event()

    def _register(self, name, regtype, port):
        """
        An instance of DNSServiceRef (sdRef) represents an active connection to mdnsd.

        DNSServiceRef class supports the context management protocol, sdRef
        is closed automatically when block is exited.
        """
        if not (name and regtype and port):
            return

        sdRef = pybonjour.DNSServiceRegister(name=name, regtype=regtype, port=port, callBack=None)
        with sdRef:
            self.finished.wait()
            self.logger.trace(f'Unregistering {name} {regtype}')

    def register(self):
        if self.hostname and self.regtype and self.port:
            self._register(self.hostname, self.regtype, self.port)

    def run(self):
        set_thread_name(f'mdns_svc_{self.service}')
        try:
            self.register()
        except pybonjour.BonjourError:
            self.logger.debug("ServiceThread: failed to register '%s', is mdnsd running?", self.service)

    def setup(self):
        pass

    def cancel(self):
        self.finished.set()


class mDNSServiceSSHThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        if 'service' not in kwargs:
            kwargs['service'] = 'ssh'
        super(mDNSServiceSSHThread, self).__init__(**kwargs)

    def setup(self):
        ssh_service = self.middleware.call_sync(
            'datastore.query',
            'services.services', [('srv_service', '=', 'ssh'), ('srv_enable', '=', True)])
        if ssh_service:
            response = self.middleware.call_sync('datastore.query', 'services.ssh', [], {'get': True})
            if response:
                self.port = response['ssh_tcpport']
                self.regtype = "_ssh._tcp."


class mDNSServiceSFTPThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'sftp'
        super(mDNSServiceSFTPThread, self).__init__(**kwargs)

    def setup(self):
        ssh_service = self.middleware.call_sync(
            'datastore.query',
            'services.services', [('srv_service', '=', 'ssh'), ('srv_enable', '=', True)])
        if ssh_service:
            response = self.middleware.call_sync('datastore.query', 'services.ssh', [], {'get': True})
            if response:
                self.port = response['ssh_tcpport']
                self.regtype = "_sftp-ssh._tcp."


class mDNSServiceHTTPThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'http'
        super(mDNSServiceHTTPThread, self).__init__(**kwargs)

    def setup(self):
        webui = self.middleware.call_sync('datastore.query', 'system.settings')
        self.port = int(webui[0]['stg_guiport'] or 80)
        self.regtype = '_http._tcp.'


class mDNSServiceHTTPSThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'https'
        super(mDNSServiceHTTPSThread, self).__init__(**kwargs)

    def setup(self):
        webui = self.middleware.call_sync('datastore.query', 'system.settings')
        self.port = int(webui[0]['stg_guihttpsport'] or 443)
        self.regtype = '_https._tcp.'


class mDNSServiceMiddlewareThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'middleware'
        super(mDNSServiceMiddlewareThread, self).__init__(**kwargs)
        set_thread_name(f'mdns_{self.service}')

    def setup(self):
        self.port = 6000
        self.regtype = "_middleware._tcp."


class mDNSServiceMiddlewareSSLThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'middleware-ssl'
        super(mDNSServiceMiddlewareSSLThread, self).__init__(**kwargs)

    def setup(self):
        webui = self.middleware.call_sync('datastore.query', 'system.settings')
        self.port = int(webui[0]['stg_guihttpsport'] or 443)
        self.regtype = '_middleware-ssl._tcp.'


class mDNSAdvertiseService(Service):
    def __init__(self, *args, **kwargs):
        super(mDNSAdvertiseService, self).__init__(*args, **kwargs)
        self.threads = {}
        self.initialized = False
        self.lock = threading.Lock()

    @private
    def start(self):
        with self.lock:
            if self.initialized:
                return

        if not mDNSDaemonMonitor.instance.mdnsd_running.wait(timeout=10):
            return

        try:
            hostname = socket.gethostname().split('.')[0]
        except IndexError:
            hostname = socket.gethostname()

        mdns_advertise_services = [
            mDNSServiceSSHThread,
            mDNSServiceSFTPThread,
            mDNSServiceHTTPThread,
            mDNSServiceHTTPSThread,
            mDNSServiceMiddlewareThread,
            mDNSServiceMiddlewareSSLThread
        ]

        for service in mdns_advertise_services:
            thread = service(middleware=self.middleware, hostname=hostname)
            thread.setup()
            thread_name = thread.service
            self.threads[thread_name] = thread
            thread.start()

        with self.lock:
            self.initialized = True

    @private
    def stop(self):
        for thread in self.threads.copy():
            thread = self.threads.get(thread)
            thread.cancel()
            del self.threads[thread.service]
        self.threads = {}

        with self.lock:
            self.initialized = False

    @private
    def restart(self):
        self.stop()
        self.start()


async def dns_post_sync(middleware):
    mDNSDaemonMonitor.instance.dns_sync.set()


def setup(middleware):
    mDNSDaemonMonitor(middleware)
    middleware.register_hook('dns.post_sync', dns_post_sync)
