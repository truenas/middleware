import asyncio
import os
import pybonjour
import select
import socket
import sys
import threading

from middlewared.service import Service

if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
django.setup()

from freenasUI.common.freenassysctl import freenas_sysctl as _fs

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
        self.finished = threading.Event()

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


class mDNSService(Service):
    def __init__(self, *args):
        super(mDNSService, self).__init__(*args)
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

        mdns_services = [
            mDNSServiceSSHThread,
            mDNSServiceSFTPThread,
            mDNSServiceMiddlewareThread,
            mDNSServiceMiddlewareSSLThread
        ]

        for service in mdns_services:
            thread = service(middleware=self.middleware, logger=self.logger, hostname=hostname)
            await thread.setup()

            self.logger.debug("[mDNSService] starting thread %s", thread.service)

            thread_name = thread.service
            self.threads[thread_name] = thread
            thread.start()

        self.lock.acquire()
        self.initialized = True
        self.lock.release()

    async def stop(self):
        for thread in self.threads.copy():
            thread = self.threads.get(thread)

            self.logger.debug("[mDNSService] stopping thread %s", thread.service)

            await self.middleware.threaded(thread.cancel)
            del self.threads[thread.service]
        self.threads = {}

        self.lock.acquire()
        self.initialized = False
        self.lock.release()

    async def restart(self):
        await self.stop()
        await self.start()

def setup(middleware):
    asyncio.ensure_future(middleware.call('mdns.start'))
