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


class mDNSObject(object):
    def __init__(self, **kwargs):
        self.sdRef = kwargs.get('sdRef')
        self.flags = kwargs.get('flags')
        self.interface = kwargs.get('interface')
        self.name = kwargs.get('name')

    def to_dict(self):
        return {
            'type': 'mDNSObject',
            'sdRef': memoryview(self.sdRef).tobytes().decode('utf-8'),
            'flags': self.flags,
            'interface': self.interface,
            'name': self.name
        }


class mDNSDiscoverObject(mDNSObject):
    def __init__(self, **kwargs):
        super(mDNSDiscoverObject, self).__init__(**kwargs)
        self.regtype = kwargs.get('regtype')
        self.domain = kwargs.get('domain')

    @property
    def fullname(self):
        return "%s.%s.%s" % (
            self.name.strip('.'),
            self.regtype.strip('.'),
            self.domain.strip('.')
        )

    def to_dict(self):
        bdict = super(mDNSDiscoverObject, self).to_dict()
        bdict.update({
            'type': 'mDNSDiscoverObject',
            'regtype': self.regtype,
            'domain': self.domain
        })
        return bdict


class mDNSServiceObject(mDNSObject):
    def __init__(self, **kwargs):
        super(mDNSServiceObject, self).__init__(**kwargs)
        self.target = kwargs.get('target')
        self.port = kwargs.get('port')
        self.text = kwargs.get('text')

    def to_dict(self):
        bdict = super(mDNSServiceObject, self).to_dict()
        bdict.update({
            'type': 'mDNSServiceObject',
            'target': self.target,
            'port': self.port,
            'text': self.text
        })
        return bdict


class mDNSThread(threading.Thread):
    def __init__(self, **kwargs):
        super(mDNSThread, self).__init__()
        self.setDaemon(True)
        self.middleware = kwargs.get('middleware')
        self.logger = self.middleware.logger
        self.timeout = kwargs.get('timeout', 30)

    def active(self, sdRef):
        return (bool(sdRef) and sdRef.fileno() != -1)


class ServicesThread(mDNSThread):
    def __init__(self, **kwargs):
        super(ServicesThread, self).__init__(**kwargs)
        self.queue = kwargs.get('queue')
        self.service_queue = kwargs.get('service_queue')
        self.finished = threading.Event()
        self.pipe = os.pipe()
        self.references = []
        self.cache = {}

    def to_regtype(self, obj):
        regtype = None

        if (obj.flags & (kDNSServiceFlagsAdd | kDNSServiceFlagsMoreComing)) \
           or not (obj.flags & kDNSServiceFlagsAdd):
            service = obj.name
            proto = obj.regtype.split('.')[0]
            regtype = "%s.%s." % (service, proto)

        return regtype

    def on_discover(self, sdRef, flags, interface, error, name, regtype, domain):
        self.logger.trace("ServicesThread: name=%s flags=0x%08x error=%d", name, flags, error)

        if error != kDNSServiceErr_NoError:
            return

        obj = mDNSDiscoverObject(
            sdRef=sdRef,
            flags=flags,
            interface=interface,
            name=name,
            regtype=regtype,
            domain=domain
        )

        if not (obj.flags & kDNSServiceFlagsAdd):
            self.logger.trace("ServicesThread: remove %s", name)
            cobj = self.cache.get(obj.fullname)
            if cobj:
                if cobj.sdRef in self.references:
                    self.references.remove(cobj.sdRef)
                if self.active(cobj.sdRef):
                    cobj.sdRef.close()
                del self.cache[obj.fullname]
        else:
            self.cache[obj.fullname] = obj
            self.service_queue.put(obj)

    def run(self):
        set_thread_name('mdns_services')
        while True:
            if not mDNSDaemonMonitor.instance.mdnsd_running.wait(timeout=10):
                return

            try:
                obj = self.queue.get(block=True, timeout=self.timeout)
            except queue.Empty:
                if self.finished.is_set():
                    break
                continue

            regtype = self.to_regtype(obj)
            if not regtype:
                continue

            sdRef = pybonjour.DNSServiceBrowse(
                regtype=regtype,
                callBack=self.on_discover
            )

            self.references.append(sdRef)
            _references = list(filter(self.active, self.references))

            r, w, x = select.select(_references + [self.pipe[0]], [], [])
            if self.pipe[0] in r:
                break
            for ref in r:
                pybonjour.DNSServiceProcessResult(ref)
            if not (obj.flags & kDNSServiceFlagsAdd):
                self.references.remove(sdRef)
                if self.active(sdRef):
                    sdRef.close()

            if self.finished.is_set():
                break

        for ref in self.references:
            self.references.remove(ref)
            if self.active(ref):
                ref.close()

    def cancel(self):
        self.finished.set()
        os.write(self.pipe[1], b'42')


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
        self.pipe = os.pipe()
        self.finished = threading.Event()

    def _register(self, name, regtype, port):
        if not (name and regtype and port):
            return

        sdRef = pybonjour.DNSServiceRegister(name=name, regtype=regtype, port=port, callBack=None)

        while True:
            r, w, x = select.select([sdRef, self.pipe[0]], [], [])
            if self.pipe[0] in r:
                break

            for ref in r:
                pybonjour.DNSServiceProcessResult(ref)

            if self.finished.is_set():
                break

        # This deregisters service
        sdRef.close()

    def register(self):
        if self.hostname and self.regtype and self.port:
            self._register(self.hostname, self.regtype, self.port)

    def run(self):
        set_thread_name(f'mdns_svc_{self.service}')
        try:
            self.register()
        except pybonjour.BonjourError:
            self.logger.trace("ServiceThread: failed to register '%s', is mdnsd running?", self.service)

    def setup(self):
        pass

    def cancel(self):
        self.finished.set()
        os.write(self.pipe[1], b'42')


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
