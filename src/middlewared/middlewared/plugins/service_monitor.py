import asyncio
import os
import socket
import random
import sys
import threading
import time

from middlewared.service import Service, private

if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
from django.apps import apps
if not apps.ready:
    django.setup()

from freenasUI.common.freenassysctl import freenas_sysctl as _fs


class ServiceMonitorThread(threading.Thread):
    def __init__(self, **kwargs):
        super(ServiceMonitorThread, self).__init__()
        self.setDaemon(False)

        self.id = kwargs.get('id')
        self.frequency = kwargs.get('frequency')
        self.retry = kwargs.get('retry')
        self.host = kwargs.get('host')
        self.port = kwargs.get('port')
        self.name = kwargs.get('name')
        self.logger = kwargs.get('logger')
        self.middleware = kwargs.get('middleware')
        self.finished = threading.Event()

        self.logger.debug("[ServiceMonitorThread] name={0} frequency={1} retry={2}".format(self.name, self.frequency, self.retry))

    @private
    def alert(self, message):
        _random = str(random.randint(1, 1000))
        file_error = '/tmp/.' + _random + self.name + '.service_monitor'
        with open(file_error, 'w') as _file:
            _file.write(message)

    @private
    def isEnabled(self, service):
        enabled = False

        # XXX yet another hack. We need a generic mechanism/interface that we can use that tells
        # use if a service is enabled or not. When the service monitor starts up, it assumes 
        # self.connected is True. If the service is down, but enabled, and we restart the middleware,
        # and the service becomes available, we do not see a transition occur and therefore do not
        # start the service.
        if service in ('activedirectory', 'ldap', 'nis'):
            try:
                ds = self.middleware.call_sync('datastore.query', 'directoryservice.%s' % service)[0]
                if service == 'activedirectory':
                    service = 'ad'
                enabled = ds["%s_enable" % service]

            except Exception as e:
                self.logger.debug("[ServiceMonitorThread] ERROR: isEnabled: {}".format(e))

        else:
            try:
                services = self.middleware.call_sync('datastore.query', 'services.services')
                for s in services:
                    if s['srv_service'] == 'cifs':
                        enabled = s['srv_enable']

            except Exception as e:
                self.logger.debug("[ServiceMonitorThread] ERROR: isEnabled: {}".format(e))

        return enabled

    @private
    def tryConnect(self, host, port):
        max_tries = 3
        timeout = _fs().middlewared.plugins.service_monitor.socket_timeout
        connected = False

        i = 0
        while i < max_tries:

            # XXX What about UDP?
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)

            try:
                s.connect((host, port))
                connected = True

            except Exception as e:
                self.logger.debug("[ServiceMonitorThread] Cannot connect: {0}:{1} with error: {2}".format(host, port, e))
                connected = False

            finally:
                s.settimeout(None)
                s.close()

            i += 1

        return connected

    @private
    def getStarted(self, service):
        max_tries = 3

        started = self.middleware.call_sync('service.started', self.name)
        if started is True:
            return started

        i = 0
        while i < max_tries:
            time.sleep(1)
            started = self.middleware.call_sync('service.started', self.name)
            i += 1

        return started

    def run(self):
        ntries = 0

        while True:
            self.finished.wait(self.frequency)

            #
            # We should probably have a configurable threshold for number of
            # failures before starting or stopping the service
            #
            connected = self.tryConnect(self.host, self.port)
            started = self.getStarted(self.name)
            enabled = self.isEnabled(self.name)

            self.logger.debug("[ServiceMonitorThread] connected={0} started={1} enabled={2}".format(connected, started, enabled))

            if (connected is False):
                self.alert("attempt %d to recover service %s\n" % (ntries + 1, self.name))

            if (connected is True) and (started is False):
                self.logger.debug("[ServiceMonitorThread] enabling service {}".format(self.name))
                try:
                    self.middleware.call_sync('service.start', self.name)
                except Exception:
                    pass

            elif (connected is False) and (enabled is True):
                self.logger.debug("[ServiceMonitorThread] disabling service {}".format(self.name))
                try:
                    self.middleware.call_sync('service.stop', self.name)
                except Exception:
                    pass

            if self.finished.is_set():
                break

            ntries += 1
            if self.retry == 0:
                continue
            if ntries >= self.retry:
                break

        self.alert("tried %d attempts to recover service %s" % (self.retry, self.name))

    def cancel(self):
        self.finished.set()


class ServiceMonitorService(Service):
    """Main-Class for service monitoring."""

    def __init__(self, *args):
        super(ServiceMonitorService, self).__init__(*args)
        self.threads = {}

    async def start(self):
        services = await self.middleware.call('datastore.query', 'services.servicemonitor')
        for s in services:
            thread_name = s['sm_name']

            if not s['sm_enable']:
                self.logger.debug("[ServiceMonitorService] skipping {}".format(thread_name))
                continue

            self.logger.debug("[ServiceMonitorService] monitoring {}".format(thread_name))

            thread = ServiceMonitorThread(id=s['id'], frequency=s['sm_frequency'], retry=s['sm_retry'],
                host=s['sm_host'], port=s['sm_port'], name=thread_name, logger=self.logger, middleware=self.middleware)
            self.threads[thread_name] = thread
            thread.start()

    async def stop(self):
        for thread in self.threads.copy():
            thread = self.threads.get(thread)
            await self.middleware.threaded(thread.cancel)
            del self.threads[thread.name]
        self.threads = {}

    async def restart(self):
        await self.stop()
        await self.start()


def setup(middleware):
    asyncio.ensure_future(middleware.call('servicemonitor.start'))
