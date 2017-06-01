import os
import socket
import random
import sys
import threading
import middlewared.logger

from middlewared.client import CallTimeout
from middlewared.service import Service, job, private

if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
django.setup()

from freenasUI.common.freenassysctl import freenas_sysctl as _fs


#
# Using a timer thread is pretty dumb. We should use a backoff algorithm that eventually converges to a frequency
#
class ServiceMonitorThread(threading.Timer):
    def __init__(self, **kwargs):
        super(ServiceMonitorThread, self).__init__(interval=kwargs.get('frequency'), function=self.timerCallback)
        self.setDaemon(False)

        self.id = kwargs.get('id')
        self.frequency = kwargs.get('frequency')
        self.retry = kwargs.get('retry')
        self.counter = kwargs.get('retry')
        self.forever = True if self.retry is 0 else False
        self.func = self.testConnection
        self.host = kwargs.get('host')
        self.port = kwargs.get('port')
        self.name = kwargs.get('name')
        self.logger = kwargs.get('logger')
        self.middleware = kwargs.get('middleware')
        self.createFunc = kwargs.get('createFunc')
        self.destroyFunc = kwargs.get('destroyFunc')
        self.existsFunc = kwargs.get('existsFunc')
        self.connected = kwargs.get('connected', True)

        self.logger.debug("[ServiceMonitorThread] name=%s frequency=%d retry=%d", self.name, self.frequency, self.retry)

    @private
    def isEnabled(self, service):
        enabled = False

        #
        # XXX yet another hack. We need a generic mechanism/interface that we can use that tells
        # use if a service is enabled or not. When the service monitor starts up, it assumes 
        # self.connected is True. If the service is down, but enabled, and we restart the middleware,
        # and the service becomes available, we do not see a transition occur and therefore do not
        # start the service.
        #

        if service in ('activedirectory', 'ldap', 'nis', 'nt4'):
            try:
                ds = self.middleware.call('datastore.query', 'directoryservice.%s' % service)[0]
                if service == 'activedirectory':
                    service = 'ad'
                enabled = ds["%s_enable" % service]

            except Exception as e:
                self.logger.debug("[ServiceMonitorThread] ERROR: isEnabled: %s", e)

        else:
            try:
                services = self.middleware.call('datastore.query', 'services.services')
                for s in services:
                    if s['srv_service'] == 'cifs':
                        enabled = s['srv_enable']

            except Exception as e:
                self.logger.debug("[ServiceMonitorThread] ERROR: isEnabled: %s", e)

        return enabled

    #
    # XXX: Need mechanism for more intelligent protocol checking
    #
    @private
    def testConnection(self, host, port, name):
        """Try to open a socket for a given host and service port.

        Args:
                host (str): The hostname and domainname where we will try to connect.
                port (int): The service port number.
                name (str): Same name used to start/stop/restart method.
        """

        connected = self.connected

        # XXX What about UDP?
        bind = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        bind.settimeout(_fs().middlewared.plugins.service_monitor.socket_timeout)
 
        #
        # We should probably have a threshold rather than failing on first time we can't
        # connect, eg: Try to connect 3 times, then fail.
        #
        try:
            bind.connect((host, port))
            self.connected = True

        except Exception as error:
            self.connected = False
            self.logger.debug("[ServiceMonitorThread] Cannot connect: %s:%d with error: %s" % (host, port, error))

        finally:
            bind.settimeout(None)
            bind.close()

        #
        # This should be smarter about stopping|starting a service. We need to know
        # the current state of the service and if the service was enabled or not to
        # make a fully informed decision. For now, look for state change and if
        # the service is up and listening or not. Since the default assumption for
        # a new timer thread is that connected is true, the first transition from
        # connected being true to false will cause a service.stop to occur. Since
        # this is the way we currently implement things, it is best to make service
        # stop scripts a no-op if the service is already stopped. service.started
        # doesn't quite work as one would expect since it will just tell us the
        # current state of the process, not if it was stopped or started already.
        # What this means is when a process becomes available again, and started
        # was previously false, it now becomes true (without actually restarting
        # the process), so it's not reliable.
        #

        started = self.middleware.call('service.started', name)
        enabled = self.isEnabled(name)

        self.logger.debug("[ServiceMonitorThread] started=%s enabled=%s connected=%s", started, enabled, self.connected)

        #
        # XXX black magic, needs better architecture
        #
        if (self.connected == False) and (started == False):
            self.logger.debug("[ServiceMonitorThread] doing nothing for service %s", name)

        elif (self.connected != connected) and (self.connected == False):
            self.logger.debug("[ServiceMonitorThread] disabling service %s", name)
            try:
                self.middleware.call('service.stop', name)
            except CallTimeout:
                pass

        elif (self.connected != connected) and (self.connected == True):
            self.logger.debug("[ServiceMonitorThread] [0] enabling service %s", name)
            try:
                self.middleware.call('service.start', name)
            except CallTimeout:
                pass

        elif (self.connected == True) and (started == False):
            self.logger.debug("[ServiceMonitorThread] [1] enabling service %s", name)
            try:
                self.middleware.call('service.start', name)
            except CallTimeout:
                pass


    @private
    def timerCallback(self):
        """This is a recursive method where will launch a thread with timer
        calling another method.
        """

        if self.forever is True:
            self.counter = 100
            self.retry = 100

        if self.connected is False:
            self.counter -= 1

            _random = str(random.randint(1, 1000))
            file_error = '/tmp/.' + _random + self.name + '.service_monitor'
            with open(file_error, 'w') as _file:
                _file.write("We tried %d attempts to recover service %s\n" % (self.retry - self.counter, self.name))
        else:
            self.counter = self.retry

        if self.existsFunc(self.name) and self.counter > 0:
            self.destroyFunc(self.name)
            self.func(self.host, self.port, self.name)

            self.thread_args['retry'] = self.counter
            self.thread_args['connected'] = self.connected

            thread = self.createFunc(**self.thread_args)

        elif self.counter <= 0:
            self.logger.debug("[ServiceMonitorThread] We reached the maximum number of attempts to recover service %s, we won't try again" % (self.name))
            self.destroyFunc(self.name)

            file_error = '/tmp/.' + self.name + '.service_monitor'
            with open(file_error, 'w') as _file:
                _file.write("We reached the maximum number of %d attempts to recover service %s, we won't try again\n" % (self.retry, self.name))


class ServiceMonitorService(Service):
    """Main-Class for service monitoring."""

    def __init__(self, *args):
        super(ServiceMonitorService, self).__init__(*args)
        #self.middleware.event_subscribe('core', self.start)
        self.threads = {}

    @private
    def threadExists(self, name):
        """Verify if a service monitoring is already running for a given service.

        Args:
                    name (str): Same name used to start/stop/restart method.

        Returns:
                    bool: True if it is already running or False otherwise.
        """
        thread = self.threads.get(name)
        if thread:
            return True
        return False

    @private
    def createThread(self, **kwargs):
        thread = ServiceMonitorThread(**kwargs)
        thread.thread_args = kwargs
        thread.start()

        self.threads[thread.name] = thread
        return thread

    @private
    def destroyThread(self, name):
        thread = self.threads.get(name)
        if thread:
            thread.cancel()
            del self.threads[thread.name]

    def start(self):
        services = self.middleware.call('datastore.query', 'services.servicemonitor')
        for s in services:
            thread_name = s['sm_name']

            if not s['sm_enable']:
                self.logger.debug("[ServiceMonitorService] skipping %s", thread_name)
                continue

            self.logger.debug("[ServiceMonitorService] monitoring %s", thread_name)

            if self.threadExists(thread_name):
                self.destroyThread(thread_name)

            self.createThread(id=s['id'], frequency=s['sm_frequency'],retry=s['sm_retry'],
                host=s['sm_host'], port=s['sm_port'], name=thread_name, logger=self.logger,
                middleware=self.middleware, createFunc=self.createThread,
                destroyFunc=self.destroyThread, existsFunc=self.threadExists)

    def stop(self):
        for thread in self.threads.copy():
            self.destroyThread(thread)
        self.threads = {}


    def restart(self):
        self.stop()
        self.start()


def setup(middleware):
    middleware.call('servicemonitor.start')
