import asyncio
import os
import sys
import threading
import time
import tempfile
import datetime
import ntplib

from middlewared.service import Service, private

if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')

from freenasUI.common.freenasldap import FreeNAS_ActiveDirectory


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
        self.config = kwargs.get('config')
        self.middleware = kwargs.get('middleware')
        self.finished = threading.Event()
        # Reset stale alerts
        ServiceMonitorThread.reset_alerts(self.name)

        self.logger.debug("[ServiceMonitorThread] name=%s frequency=%d retry=%d", self.name, self.frequency, self.retry)

    @staticmethod
    def reset_alerts(service):
        for _file in os.listdir('/tmp'):
            if _file.startswith(f'.alert.{service}.') and _file.endswith('.service_monitor'):
                try:
                    os.remove(os.path.join('/tmp', _file))
                except OSError:
                    pass

    @private
    def alert(self, service, message):
        self.reset_alerts(service)
        with tempfile.NamedTemporaryFile(
            dir='/tmp', prefix=f'.alert.{service}.', suffix='.service_monitor',
            mode='w', encoding='utf-8', delete=False
        ) as _file:
            _file.write(message)

    @private
    def isEnabled(self, service):
        enabled = False
        #
        # XXX yet another hack. We need a generic mechanism/interface that we can use that tells
        # us if a service is enabled or not. When the service monitor starts up, it assumes
        # self.connected is True. If the service is down, but enabled, and we restart the middleware,
        # and the service becomes available, we do not see a transition occur and therefore do not
        # start the service.
        #
        if service in ('activedirectory', 'ldap', 'nis'):
            if service == 'activedirectory':
                service = 'ad'
            enabled = self.config[f'{service}_enable']

        return enabled

    @private
    def validate_time(self, ntp_server, permitted_clockskew):
        nas_time = datetime.datetime.now()
        service = self.name
        c = ntplib.NTPClient()
        try:
            response = c.request(ntp_server)
        except Exception as e:
            self.alert(service, f'{service}: Failed to query time from {ntp_server}. Domain may not be in connectable state.')
            self.logger.debug(f'[ServiceMonitorThread] Failed to query time from {ntp_server}: ({e})')
            return False

        ntp_time = datetime.datetime.fromtimestamp(response.tx_time)
        clockskew = abs(ntp_time - nas_time)
        if clockskew > permitted_clockskew:
            self.alert(service, f'{service}: Domain is not in connectable state. Current clockskew {clockskew} exceeds permitted clockskew of {permitted_clockskew}.')
            self.logger.debug(f'[ServiceMonitorThread] current clockskew of {clockskew} exceeds permitted clockskew of {permitted_clockskew}')
            return False
        else:
            return True

    @private
    def check_AD(self, host, port):
        """
        Basic health checks to determine whether we can recover the AD service if a disruption occurs.
        Current tests:
        - Clockskew from DC is not greater than 5 minutes (MIT default). Kerberos has strict time requirements.
          This can vary based on the kerberos configuration, and so this may need to be a configurable field.
        - DC connectivity. We check this by using DNS to get SRV records for LDAP, and then trying to open a socket
          to the LDAP(S) port on each of the LDAP servers in the list.
        Future tests:
        - Validate service account password
        - Verify presence of computer object in DA
        """
        connected = False
        permitted_clockskew = datetime.timedelta(minutes=5)
        sm_timeout = 30

        host_list = FreeNAS_ActiveDirectory.get_ldap_servers(host, self.config['ad_site'])

        if not host_list:
            self.alert(self.name, f'{self.name}: {host} not in connectable state. DNS query for SRV records for {host} failed.')
            self.logger.debug(f'[ServiceMonitorThread] DNS query for SRV records for {host} failed')
            return False

        for h in host_list:
            port_is_listening = FreeNAS_ActiveDirectory.port_is_listening(str(h.target),
                                                                          h.port,
                                                                          errors=[],
                                                                          timeout=sm_timeout)
            if port_is_listening:
                clockskew_within_spec = self.validate_time(str(h.target), permitted_clockskew)
                if not clockskew_within_spec:
                    return False

                return True
            else:
                self.logger.debug(f'[ServiceMonitorThread] Cannot connect: {h.target}:{h.port}')
                connected = False

        if not connected:
            self.alert(self.name, f'{self.name}: Unable to contact domain controller for {host}. Domain not in connectable state.')

        return connected

    @private
    def tryConnect(self, host, port):
        if self.name == 'activedirectory':
            domain_is_healthy = self.check_AD(host, port)
            if not domain_is_healthy:
                return False
            else:
                return True

        else:
            self.logger.debug(f'[ServiceMonitorThread] no monitoring has been written for {self.name}')
            return False

    @private
    def getStarted(self, service):
        max_tries = 3

        for i in range(0, max_tries):
            if service == 'activedirectory':
                if not self.middleware.call_sync('service.started', 'cifs'):
                    self.logger.debug("[ServiceMonitorThread] restarting Samba service")
                    self.middleware.call_sync('service.start', 'cifs')
            if self.middleware.call_sync('service.started', service):
                return True
            time.sleep(1)

        return False

    def run(self):
        ntries = 0

        service = self.name

        while True:
            self.finished.wait(self.frequency)
            #
            # We should probably have a configurable threshold for number of
            # failures before starting or stopping the service
            #
            if self.finished.is_set():
                # Thread.cancel() takes a while to propagate here
                ServiceMonitorThread.reset_alerts(service)
                return

            if os.path.exists('/tmp/.ad_start'):
                """
                 Check to see if the file .ad_start file is stale. This file is generated
                 by /etc/directoryservice/ActiveDirectory/ctl and indicates that an AD start
                 is in progress. We should not restart while AD is initializing.
                """
                self.logger.debug(f'[ServiceMonitorThread] AD is starting. Temporarily delaying service checks.')
                continue

            connected = self.tryConnect(self.host, self.port)
            if not connected:
                self.logger.debug(f'[ServiceMonitorThread] AD domain is not in connectable state. Delaying further checks.')
                continue

            started = self.getStarted(service)
            enabled = self.isEnabled(service)

            # Try less disruptive recovery attempt first before restarting AD service
            if not started and service == 'activedirectory':
                self.logger.debug("[ServiceMonitorThread] reloading Active Directory")
                self.middleware.call_sync('service.reload', 'activedirectory')
                started = self.getStarted(service)

            self.logger.trace("[ServiceMonitorThread] connected=%s started=%s enabled=%s", connected, started, enabled)
            # Everything is OK
            if connected and started and enabled:
                # Do we want to reset all alerts when things get back to normal?
                ServiceMonitorThread.reset_alerts(service)
                ntries = 0
                continue

            start_service = False
            stop_service = False
            ntries += 1

            self.alert(service, "attempt %d to recover service %s\n" % (ntries, service))

            if enabled:
                if not started:
                    start_service = True
            else:
                stop_service = True

            if stop_service:
                self.logger.debug("[ServiceMonitorThread] disabling service %s", service)
                try:
                    self.middleware.call_sync('service.stop', service)
                except Exception:
                    self.logger.debug(
                        "[ServiceMonitorThread] failed stopping service", exc_info=True
                    )

            if start_service:
                self.logger.debug("[ServiceMonitorThread] enabling service %s", service)
                try:
                    self.middleware.call_sync('service.start', service)
                except Exception:
                    self.logger.debug(
                        "[ServiceMonitorThread] failed starting service", exc_info=True
                    )

            if self.retry == 0:
                continue

            if ntries >= self.retry:
                break

        if not connected or not enabled or not started:
            # Clear all intermediate alerts
            ServiceMonitorThread.reset_alerts(service)
            # We gave up to restore service here
            self.alert(service, "Failed to recover service %s after %d tries" % (service, ntries))
            # Disable monitoring here?

    def cancel(self):
        self.finished.set()


class ServiceMonitorService(Service):
    """Main-Class for service monitoring."""

    class Config:
        private = True

    def __init__(self, *args):
        super(ServiceMonitorService, self).__init__(*args)
        self.threads = {}

    async def start(self):
        services = await self.middleware.call('datastore.query', 'services.servicemonitor')
        for s in services:
            thread_name = s['sm_name']
            s_config = None
            service_enabled = False
            # Remove stale alerts
            ServiceMonitorThread.reset_alerts(thread_name)

            if thread_name in ('activedirectory', 'ldap', 'nis'):
                service_name = 'ad' if thread_name == 'activedirectory' else thread_name
                s_config = await self.middleware.call('datastore.query', f'directoryservice.{thread_name}', None, {'get': True})
                service_enabled = s_config[f"{service_name}_enable"]
            else:
                s_config = await self.middleware.call('service.query', [('service', '=', f"{thread_name}")], {'get': True})
                service_enabled = s_config['enable']

            if not s['sm_enable'] or not service_enabled:
                self.logger.debug("[ServiceMonitorService] skipping %s", thread_name)
                continue

            self.logger.debug("[ServiceMonitorService] monitoring %s", thread_name)

            thread = ServiceMonitorThread(
                id=s['id'], frequency=s['sm_frequency'], retry=s['sm_retry'],
                host=s['sm_host'], port=s['sm_port'], name=thread_name,
                logger=self.logger, config=s_config, middleware=self.middleware
            )
            self.threads[thread_name] = thread
            thread.start()

    async def stop(self):
        for thread in self.threads.copy():
            thread = self.threads.get(thread)
            await self.middleware.run_in_thread(thread.cancel)
            del self.threads[thread.name]
        self.threads = {}

    async def restart(self):
        await self.stop()
        await self.start()


def setup(middleware):
    asyncio.ensure_future(middleware.call('servicemonitor.start'))
