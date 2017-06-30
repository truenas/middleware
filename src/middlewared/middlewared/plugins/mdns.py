import asyncio
import os
import pybonjour
import queue
import select
import socket
import sys
import time
import threading

from pybonjour import (
    kDNSServiceFlagsMoreComing,
    kDNSServiceFlagsAdd,
    kDNSServiceFlagsDefault,
    kDNSServiceFlagsNoAutoRename,
    kDNSServiceFlagsShared,
    kDNSServiceFlagsUnique,
    kDNSServiceFlagsBrowseDomains,
    kDNSServiceFlagsRegistrationDomains,
    kDNSServiceErr_NoError
)

from middlewared.service import Service

if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
django.setup()

from freenasUI.common.freenassysctl import freenas_sysctl as _fs

class mDNSObject(object):
    def __init__(self, **kwargs):
        self.sdRef = kwargs.get('sdRef')
        self.flags = kwargs.get('flags')
        self.interface = kwargs.get('interface')
        self.name = kwargs.get('name')


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


class mDNSServiceObject(mDNSObject):
    def __init__(self, **kwargs):
        super(mDNSServiceObject, self).__init__(**kwargs)
        self.target = kwargs.get('target')
        self.port = kwargs.get('port')
        self.text = kwargs.get('text')


class mDNSThread(threading.Thread):
    def __init__(self, **kwargs):
        super(mDNSThread, self).__init__()
        self.setDaemon(False)

    def active(self, sdRef):
        return (bool(sdRef) and sdRef.fileno() != -1)

    def debug(self, format, *values):
        if self.debug_enable:
            print(format % values)


class DiscoverThread(mDNSThread):
    def __init__(self, **kwargs):
        super(DiscoverThread, self).__init__()
        self.regtype = "_services._dns-sd._udp"
        self.queue = kwargs.get('queue')
        self.debug_enable = kwargs.get('debug')
        self.finished = threading.Event()

    def on_discover(self,sdRef, flags, interface, error, name, regtype, domain):
        self.debug("DiscoverThread: name=%s flags=0x%08x error=%d" % (name, flags, error))

        if error != kDNSServiceErr_NoError:
            return

        self.queue.put(
            mDNSDiscoverObject(
                sdRef=sdRef,
                flags=flags,
                interface=interface,
                name=name,
                regtype=regtype,
                domain=domain
            )
        )

    def active(self, sdRef):
        return (bool(sdRef) and sdRef.fileno() != -1)

    def run(self):
        sdRef = pybonjour.DNSServiceBrowse(
            regtype=self.regtype,
            callBack=self.on_discover
        )
        while True:
            r, w, x = select.select([sdRef], [], [])
            for ref in r:
                pybonjour.DNSServiceProcessResult(ref)

            if self.finished.is_set(): 
                break

        if self.active(sdRef):
            sdRef.close()

    def cancel(self):
        self.finished.set()

class ServicesThread(mDNSThread):
    def __init__(self, **kwargs):
        super(ServicesThread, self).__init__()
        self.queue = kwargs.get('queue')
        self.service_queue = kwargs.get('service_queue')
        self.debug_enable = kwargs.get('debug')
        self.finished = threading.Event()
        self.references = []
        self.cache = {}

    def to_regtype(self, obj):
        regtype = None

        if (obj.flags & 3) or not (obj.flags & kDNSServiceFlagsAdd):
            service = obj.name
            proto = obj.regtype.split('.')[0]
            regtype = "%s.%s." % (service, proto)

        return regtype

    def on_discover(self, sdRef, flags, interface, error, name, regtype, domain):
        self.debug("ServicesThread: name=%s flags=0x%08x error=%d" % (name, flags, error))

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
            self.debug("ServicesThread: remove %s" % name)
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

    def active(self, sdRef):
        return (bool(sdRef) and sdRef.fileno() != -1)

    def run(self):
        while True:
            obj = self.queue.get(block=True)
            if not obj:
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

            r, w, x = select.select(_references, [], [])
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
        

class ResolveThread(mDNSThread):
    def __init__(self, **kwargs):
        super(ResolveThread, self).__init__()
        self.queue = kwargs.get('queue')
        self.debug_enable = kwargs.get('debug')
        self.finished = threading.Event()
        self.references = []
        self.services = []

    def on_resolve(self, sdRef, flags, interface, error, name, target, port, text):
        self.debug("ResolveThread: name=%s flags=0x%08x error=%d" % (name, flags, error))

        if error != kDNSServiceErr_NoError:
            return

        self.services.append(
            mDNSServiceObject(
                sdRef=sdRef,
                flags=flags,
                interface=interface,
                name=name,
                target=target,
                port=port,
                text=text
            )
        ) 

        self.references.remove(sdRef)
        sdRef.close()

    def active(self, sdRef):
        return (bool(sdRef) and sdRef.fileno() != -1)

    def run(self):
        while True:
            obj = self.queue.get(block=True)
            if not obj:
                continue

            sdRef = pybonjour.DNSServiceResolve(
                flags=obj.flags,
                interfaceIndex=obj.interface,
                name=obj.name,
                regtype=obj.regtype,
                domain=obj.domain,
                callBack=self.on_resolve
            )

            self.references.append(sdRef)
            _references = list(filter(self.active, self.references))

            r, w, x = select.select(_references, [], [])
            for ref in r:
                pybonjour.DNSServiceProcessResult(ref)

            if self.finished.is_set():
                break

        for ref in self.references:
            self.references.remove(ref)
            if self.active(ref):
                ref.close()

    def cancel(self):
        self.finished.set()

    def remove_by_host(self, host, service=None):
        ret = False

        if not host:
            return ret

        for s in self.services:
            parts = s.name.split('.')
            if len(parts) < 3:
                continue

            _host = parts[0]
            _service = "%s.%s" % (parts[1], parts[2])

            if _host == host:
                if (service and _service == service) or \
                    (service and _service == service[:-1]) or \
                    (not service):
                    self.services.remove(s)
                    ret = True
        return ret

    def get_by_host(self, host, service=None):
        if not host:
            return None

        services = []
        for s in self.services:
            parts = s.name.split('.')
            if len(parts) < 3:
                continue

            _host = parts[0]
            _service = "%s.%s" % (parts[1], parts[2])

            if _host == host:
                if (service and _service == service) or \
                    (service and _service == service[:-1]) or \
                    (not service):
                    services.append(s)

        return services

    def get_by_service(self, service, host=None):
        if not service:
            return None

        services = []
        for s in self.services:
            parts = s.name.split('.')
            if len(parts) < 3:
                continue

            _host = parts[0]
            _service = "%s.%s" % (parts[1], parts[2])

            if (_service == service) or (_service == service[:-1]):
                if (host and _host == host) or (not host):
                    services.append(s)

        return services

class mDNSBrowserService(Service):
    def __init__(self, *args):
        super(mDNSBrowserService, self).__init__(*args)
        self.threads = {}
        self.dq = queue.Queue()
        self.sq = queue.Queue()
        self.dthread = DiscoverThread(queue=self.dq)
        self.sthread = ServicesThread(queue=self.dq, service_queue=self.sq)
        self.rthread = ResolveThread(queue=self.sq)
        self.initialized = False
        self.lock = threading.Lock()

    async def start(self):
        self.dthread.start()
        self.sthread.start()
        self.rthread.start()

    async def stop(self):
        self.rthread.stop()
        self.sthread.stop()
        self.dthread.stop()

    async def restart(self):
        await self.stop()
        await self.start()


class mDNSServiceThread(threading.Thread):
    def __init__(self, **kwargs):
        super(mDNSServiceThread, self).__init__()
        self.setDaemon(False)
        self.service = kwargs.get('service')
        self.middleware = kwargs.get('middleware')
        self.logger = kwargs.get('logger')
        self.hostname = kwargs.get('hostname')
        self.service = kwargs.get('service')
        self.regtype = kwargs.get('regtype')
        self.port = kwargs.get('port')
        self.debug_enable = kwargs.get('debug')
        self.finished = threading.Event()

    def debug(self, format, *values):
        if self.debug_enable:
            self.logger.debug(format % values)

    def _register(self, name, regtype, port):
        if not (name and regtype and port):
            return

        sdRef = pybonjour.DNSServiceRegister(name=name,
            regtype=regtype, port=port, callBack=None)

        while True:
            r, w, x = select.select([sdRef], [], [], 30)
            if sdRef == r:
                pybonjour.DNSServiceProcessResult(r)
            if self.finished.is_set():
                break

        # This deregisters service
        sdRef.close()

    def register(self):
        if self.hostname and self.regtype and self.port:
            self._register(self.hostname, self.regtype, self.port)

    def run(self):
        self.register()

    async def setup(self):
        pass

    def cancel(self):
        self.finished.set()


class mDNSServiceSSHThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        if 'service' not in kwargs:
            kwargs['service'] = 'ssh'
        super(mDNSServiceSSHThread, self).__init__(**kwargs)

    async def setup(self):
        ssh_service = await self.middleware.call('datastore.query',
            'services.services', [('srv_service', '=', 'ssh'), ('srv_enable', '=', True)])
        if ssh_service:
            response = await self.middleware.call('datastore.query', 'services.ssh', [], {'get': True})
            if response:
                self.port = response['ssh_tcpport']
                self.regtype = "_ssh._tcp."


class mDNSServiceSFTPThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'sftp'
        super(mDNSServiceSFTPThread, self).__init__(**kwargs)

    async def setup(self):
        ssh_service = await self.middleware.call('datastore.query',
            'services.services', [('srv_service', '=', 'ssh'), ('srv_enable', '=', True)])
        if ssh_service:
            response = await self.middleware.call('datastore.query', 'services.ssh', [], {'get': True})
            if response:
                self.port = response['ssh_tcpport']
                self.regtype = "_sftp._tcp."


class mDNSServiceMiddlewareThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'middleware'
        super(mDNSServiceMiddlewareThread, self).__init__(**kwargs)

    async def setup(self):
        webui = await self.middleware.call('datastore.query', 'system.settings')
        if (webui[0]['stg_guiprotocol'] == 'http' or
            webui[0]['stg_guiprotocol'] == 'httphttps'):
            self.port = int(webui[0]['stg_guiport'] or 80)
            self.regtype = "_middleware._tcp."


class mDNSServiceMiddlewareSSLThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'middleware-ssl'
        super(mDNSServiceMiddlewareSSLThread, self).__init__(**kwargs)

    async def setup(self):
        webui = await self.middleware.call('datastore.query', 'system.settings')
        if (webui[0]['stg_guiprotocol'] == 'https' or
            webui[0]['stg_guiprotocol'] == 'httphttps'):
            self.port = int(webui[0]['stg_guihttpsport'] or 443)
            self.regtype = "_middleware-ssl._tcp."

class mDNSAdvertiseService(Service):
    def __init__(self, *args):
        super(mDNSAdvertiseService, self).__init__(*args)
        self.threads = {}
        self.initialized = False
        self.lock = threading.Lock()

    async def start(self):
        self.lock.acquire()
        if self.initialized:
            self.lock.release()
            return
        self.lock.release()

        try:
            hostname = socket.gethostname().split('.')[0]
        except IndexError:
            hostname = socket.gethostname()

        mdns_advertise_services = [
            mDNSServiceSSHThread,
            mDNSServiceSFTPThread,
            mDNSServiceMiddlewareThread,
            mDNSServiceMiddlewareSSLThread
        ]

        for service in mdns_advertise_services:
            thread = service(middleware=self.middleware, logger=self.logger, hostname=hostname)
            await thread.setup()
            thread_name = thread.service
            self.threads[thread_name] = thread
            thread.start()

        self.lock.acquire()
        self.initialized = True
        self.lock.release()

    async def stop(self):
        for thread in self.threads.copy():
            thread = self.threads.get(thread)
            await self.middleware.threaded(thread.cancel)
            del self.threads[thread.service]
        self.threads = {}

        self.lock.acquire()
        self.initialized = False
        self.lock.release()

    async def restart(self):
        await self.stop()
        await self.start()


class mDNSService(Service):
    pass

def setup(middleware):
    asyncio.ensure_future(middleware.call('mdnsadvertise.start'))
    asyncio.ensure_future(middleware.call('mdnsbrowser.start'))
