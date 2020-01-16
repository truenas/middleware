import asyncio
import contextlib
import errno
import inspect
import os
import psutil
import signal
try:
    import sysctl
except ImportError:
    sysctl = None
import threading
import time
import subprocess

from middlewared.schema import accepts, Bool, Dict, Int, Ref, Str
from middlewared.service import filterable, CallError, CRUDService, private
import middlewared.sqlalchemy as sa
from middlewared.utils import Popen, filter_list, run
from middlewared.utils.contextlib import asyncnullcontext


class ServiceDefinition:
    def __init__(self, *args):
        if len(args) == 2:
            self.procname = args[0]
            self.rc_script = args[0]
            self.pidfile = args[1]

        elif len(args) == 3:
            self.procname = args[0]
            self.rc_script = args[1]
            self.pidfile = args[2]

        else:
            raise ValueError("Invalid number of arguments passed (must be 2 or 3)")


class StartNotify(threading.Thread):

    def __init__(self, pidfile, verb, *args, **kwargs):
        self._pidfile = pidfile
        self._verb = verb

        if self._pidfile:
            try:
                with open(self._pidfile) as f:
                    self._pid = f.read()
            except IOError:
                self._pid = None

        super(StartNotify, self).__init__(*args, **kwargs)

    def run(self):
        """
        If we are using start or restart we expect that a .pid file will
        exists at the end of the process, so we wait for said pid file to
        be created and check if its contents are non-zero.
        Otherwise we will be stopping and expect the .pid to be deleted,
        so wait for it to be removed
        """
        if not self._pidfile:
            return None

        tries = 1
        while tries < 6:
            time.sleep(1)
            if self._verb in ('start', 'restart'):
                if os.path.exists(self._pidfile):
                    # The file might have been created but it may take a
                    # little bit for the daemon to write the PID
                    time.sleep(0.1)
                try:
                    with open(self._pidfile) as f:
                        pid = f.read()
                except IOError:
                    pid = None

                if pid:
                    if self._verb == 'start':
                        break
                    if self._verb == 'restart':
                        if pid != self._pid:
                            break
                        # Otherwise, service has not restarted yet
            elif self._verb == "stop" and not os.path.exists(self._pidfile):
                break
            tries += 1


class ServiceModel(sa.Model):
    __tablename__ = 'services_services'

    id = sa.Column(sa.Integer(), primary_key=True)
    srv_service = sa.Column(sa.String(120))
    srv_enable = sa.Column(sa.Boolean(), default=False)


class ServiceService(CRUDService):

    SERVICE_DEFS = {
        's3': ServiceDefinition('minio', '/var/run/minio.pid'),
        'ssh': ServiceDefinition('sshd', '/var/run/sshd.pid'),
        'rsync': ServiceDefinition('rsync', '/var/run/rsyncd.pid'),
        'nfs': ServiceDefinition('nfsd', None),
        'afp': ServiceDefinition('netatalk', None),
        'cifs': ServiceDefinition('smbd', '/var/run/samba4/smbd.pid'),
        'dynamicdns': ServiceDefinition('inadyn', None),
        'snmp': ServiceDefinition('snmpd', '/var/run/net_snmpd.pid'),
        'ftp': ServiceDefinition('proftpd', '/var/run/proftpd.pid'),
        'tftp': ServiceDefinition('inetd', '/var/run/inetd.pid'),
        'iscsitarget': ServiceDefinition('ctld', '/var/run/ctld.pid'),
        'lldp': ServiceDefinition('ladvd', '/var/run/ladvd.pid'),
        'mdns': ServiceDefinition('avahi-daemon', '/var/run/avahi-daemon/pid'),
        'netbios': ServiceDefinition('nmbd', '/var/run/samba4/nmbd.pid'),
        'ups': ServiceDefinition('upsd', '/var/db/nut/upsd.pid'),
        'upsmon': ServiceDefinition('upsmon', '/var/db/nut/upsmon.pid'),
        'smartd': ServiceDefinition('smartd', 'smartd-daemon', '/var/run/smartd-daemon.pid'),
        'webdav': ServiceDefinition('httpd', '/var/run/httpd.pid'),
        'wsd': ServiceDefinition('wsdd', '/var/run/samba4/wsdd.pid'),
        'openvpn_server': ServiceDefinition('openvpn', '/var/run/openvpn_server.pid'),
        'openvpn_client': ServiceDefinition('openvpn', '/var/run/openvpn_client.pid')
    }

    @filterable
    async def query(self, filters=None, options=None):
        """
        Query all system services with `query-filters` and `query-options`.
        """
        if options is None:
            options = {}
        options['prefix'] = 'srv_'

        services = await self.middleware.call('datastore.query', 'services.services', filters, options)

        # In case a single service has been requested
        if not isinstance(services, list):
            services = [services]

        jobs = {
            asyncio.ensure_future(self._get_status(entry)): entry
            for entry in services
        }
        if jobs:
            done, pending = await asyncio.wait(list(jobs.keys()), timeout=15)

        def result(task):
            """
            Method to handle results of the coroutines.
            In case of error or timeout, provide UNKNOWN state.
            """
            result = None
            try:
                if task in done:
                    result = task.result()
            except Exception:
                pass
            if result is None:
                entry = jobs.get(task)
                self.logger.warn('Failed to get status for %s', entry['service'])
                entry['state'] = 'UNKNOWN'
                entry['pids'] = []
                return entry
            else:
                return result

        services = list(map(result, jobs))
        return filter_list(services, filters, options)

    @accepts(
        Str('id_or_name'),
        Dict(
            'service-update',
            Bool('enable', default=False),
        ),
    )
    async def do_update(self, id_or_name, data):
        """
        Update service entry of `id_or_name`.

        Currently it only accepts `enable` option which means whether the
        service should start on boot.

        """
        if not id_or_name.isdigit():
            svc = await self.middleware.call('datastore.query', 'services.services', [('srv_service', '=', id_or_name)])
            if not svc:
                raise CallError(f'Service {id_or_name} not found.', errno.ENOENT)
            id_or_name = svc[0]['id']

        rv = await self.middleware.call('datastore.update', 'services.services', id_or_name, {'srv_enable': data['enable']})
        await self.middleware.call('etc.generate', 'rc')
        return rv

    @accepts(
        Str('service'),
        Dict(
            'service-control',
            Bool('onetime', default=True),
            Bool('wait', default=None, null=True),
            Bool('sync', default=None, null=True),
            register=True,
        ),
    )
    async def start(self, service, options=None):
        """ Start the service specified by `service`.

        The helper will use method self._start_[service]() to start the service.
        If the method does not exist, it would fallback using service(8)."""
        await self.middleware.call_hook('service.pre_action', service, 'start', options)
        sn = self._started_notify("start", service)
        await self._simplecmd("start", service, options)
        return await self.started(service, sn)

    async def started(self, service, sn=None):
        """
        Test if service specified by `service` has been started.
        """
        if sn:
            await self.middleware.run_in_thread(sn.join)

        try:
            svc = await self.query([('service', '=', service)], {'get': True})
            self.middleware.send_event('service.query', 'CHANGED', fields=svc)
            return svc['state'] == 'RUNNING'
        except IndexError:
            f = getattr(self, '_started_' + service, None)
            if callable(f):
                if inspect.iscoroutinefunction(f):
                    return (await f())[0]
                else:
                    return f()[0]
            else:
                return (await self._started(service))[0]

    @accepts(
        Str('service'),
        Ref('service-control'),
    )
    async def stop(self, service, options=None):
        """ Stop the service specified by `service`.

        The helper will use method self._stop_[service]() to stop the service.
        If the method does not exist, it would fallback using service(8)."""
        await self.middleware.call_hook('service.pre_action', service, 'stop', options)
        sn = self._started_notify("stop", service)
        await self._simplecmd("stop", service, options)
        return await self.started(service, sn)

    @accepts(
        Str('service'),
        Ref('service-control'),
    )
    async def restart(self, service, options=None):
        """
        Restart the service specified by `service`.

        The helper will use method self._restart_[service]() to restart the service.
        If the method does not exist, it would fallback using service(8)."""
        await self.middleware.call_hook('service.pre_action', service, 'restart', options)
        sn = self._started_notify("restart", service)
        await self._simplecmd("restart", service, options)
        return await self.started(service, sn)

    @accepts(
        Str('service'),
        Ref('service-control'),
    )
    async def reload(self, service, options=None):
        """
        Reload the service specified by `service`.

        The helper will use method self._reload_[service]() to reload the service.
        If the method does not exist, the helper will try self.restart of the
        service instead."""
        await self.middleware.call_hook('service.pre_action', service, 'reload', options)
        try:
            await self._simplecmd("reload", service, options)
        except Exception as e:
            await self.restart(service, options)
        return await self.started(service)

    async def _get_status(self, service):
        f = getattr(self, '_started_' + service['service'], None)
        if callable(f):
            if inspect.iscoroutinefunction(f):
                running, pids = await f()
            else:
                running, pids = f()
        else:
            running, pids = await self._started(service['service'])

        if running:
            state = 'RUNNING'
        else:
            state = 'STOPPED'

        service['state'] = state
        service['pids'] = pids
        return service

    async def _simplecmd(self, action, what, options=None):
        self.logger.debug("Calling: %s(%s) ", action, what)
        f = getattr(self, '_' + action + '_' + what, None)
        if f is None:
            # Provide generic start/stop/restart verbs for rc.d scripts
            if what in self.SERVICE_DEFS:
                if self.SERVICE_DEFS[what].rc_script:
                    what = self.SERVICE_DEFS[what].rc_script
            if action in ("start", "stop", "restart", "reload"):
                if action == 'restart':
                    await self._system("/usr/sbin/service " + what + " forcestop ")
                await self._service(what, action, **options)
            else:
                raise ValueError("Internal error: Unknown command")
        else:
            call = f(**(options or {}))
            if inspect.iscoroutinefunction(f):
                await call

    async def _system(self, cmd):
        proc = await Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, close_fds=True)
        stdout = (await proc.communicate())[0]
        if proc.returncode != 0 and "status" not in cmd:
            self.logger.warning("Command %r failed with code %d: %r", cmd, proc.returncode, stdout)
        return proc.returncode

    async def _service(self, service, verb, **options):
        onetime = options.pop('onetime', None)
        force = options.pop('force', None)
        quiet = options.pop('quiet', None)
        extra = options.pop('extra', '')

        # force comes before one which comes before quiet
        # they are mutually exclusive
        preverb = ''
        if force:
            preverb = 'force'
        elif onetime:
            preverb = 'one'
        elif quiet:
            preverb = 'quiet'

        return await self._system('/usr/sbin/service {} {}{} {}'.format(
            service,
            preverb,
            verb,
            extra,
        ))

    def _started_notify(self, verb, what):
        """
        The check for started [or not] processes is currently done in 2 steps
        This is the first step which involves a thread StartNotify that watch for event
        before actually start/stop rc.d scripts

        Returns:
            StartNotify object if the service is known or None otherwise
        """

        if what in self.SERVICE_DEFS:
            sn = StartNotify(verb=verb, pidfile=self.SERVICE_DEFS[what].pidfile)
            sn.start()
            return sn
        else:
            return None

    async def _started(self, what, notify=None):
        """
        This is the second step::
        Wait for the StartNotify thread to finish and then check for the
        status of pidfile/procname using pgrep

        Returns:
            True whether the service is alive, False otherwise
        """

        if what in self.SERVICE_DEFS:
            if notify:
                await self.middleware.run_in_thread(notify.join)

            if self.SERVICE_DEFS[what].pidfile:
                pgrep = "/bin/pgrep -F {}{}".format(
                    self.SERVICE_DEFS[what].pidfile,
                    ' ' + self.SERVICE_DEFS[what].procname if self.SERVICE_DEFS[what].procname else '',
                )
            else:
                pgrep = "/bin/pgrep {}".format(self.SERVICE_DEFS[what].procname)
            proc = await Popen(pgrep, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
            data = (await proc.communicate())[0].decode()

            if proc.returncode == 0:
                return True, [
                    int(i)
                    for i in data.strip().split('\n') if i.isdigit()
                ]
        return False, []

    async def _started_libvirtd(self, **kwargs):
        if await self._service('libvirtd', 'status', onetime=True, **kwargs):
            return False, []
        else:
            return True, []

    async def _start_libvirtd(self, **kwargs):
        kwargs.setdefault('onetime', True)
        await self._service('libvirtd', 'start', **kwargs)

    async def _stop_libvirtd(self, **kwargs):
        kwargs.setdefault('onetime', True)
        await self._service('libvirtd', 'stop', **kwargs)

    async def _start_openvpn_server(self, **kwargs):
        kwargs.setdefault('onetime', True)
        await self.middleware.call('etc.generate', 'ssl')
        await self.middleware.call('etc.generate', 'openvpn_server')
        await self._service('openvpn_server', 'start', **kwargs)

    async def _stop_openvpn_server(self, **kwargs):
        kwargs.setdefault('onetime', True)
        await self._service('openvpn_server', 'stop', **kwargs)

    async def _restart_openvpn_server(self, **kwargs):
        await self._stop_openvpn_server(**kwargs)
        await self._start_openvpn_server(**kwargs)

    async def _start_openvpn_client(self, **kwargs):
        kwargs.setdefault('onetime', True)
        await self.middleware.call('etc.generate', 'openvpn_client')
        await self._service('openvpn_client', 'start', **kwargs)

    async def _stop_openvpn_client(self, **kwargs):
        kwargs.setdefault('onetime', True)
        await self._service('openvpn_client', 'stop', **kwargs)

    async def _restart_openvpn_client(self, **kwargs):
        await self._stop_openvpn_client(**kwargs)
        await self._start_openvpn_client(**kwargs)

    async def _start_mdns(self, **kwargs):
        announce = (await self.middleware.call('network.configuration.config')
                    )['service_announcement']
        if not announce['mdns']:
            return

        kwargs.setdefault('onetime', True)
        await self.middleware.call('etc.generate', 'mdns')
        await self._service('avahi-daemon', 'start', **kwargs)

    async def _stop_mdns(self, **kwargs):
        kwargs.setdefault('onetime', True)
        await self._service('avahi-daemon', 'stop', **kwargs)

    async def _restart_mdns(self, **kwargs):
        kwargs.setdefault('onetime', True)
        await self._stop_mdns(**kwargs)
        await self._start_mdns(**kwargs)

    async def _reload_mdns(self, **kwargs):
        announce = (await self.middleware.call('network.configuration.config')
                    )['service_announcement']
        if not announce['mdns']:
            return

        kwargs.setdefault('onetime', True)
        await self.middleware.call('etc.generate', 'mdns')
        await self._service('avahi-daemon', 'reload', **kwargs)

    async def _start_webdav(self, **kwargs):
        await self.middleware.call('etc.generate', 'webdav')
        await self._service("apache24", "start", **kwargs)

    async def _stop_webdav(self, **kwargs):
        await self._service("apache24", "stop", **kwargs)

    async def _restart_webdav(self, **kwargs):
        await self._service("apache24", "stop", force=True, **kwargs)
        await self.middleware.call('etc.generate', 'webdav')
        await self._service("apache24", "restart", **kwargs)

    async def _reload_webdav(self, **kwargs):
        await self.middleware.call('etc.generate', 'webdav')
        await self._service("apache24", "reload", **kwargs)

    async def _restart_iscsitarget(self, **kwargs):
        await self.middleware.call("etc.generate", "ctld")
        await self._service("ctld", "stop", force=True, **kwargs)
        await self.middleware.call("etc.generate", "ctld")
        await self._service("ctld", "restart", **kwargs)

    async def _start_iscsitarget(self, **kwargs):
        await self.middleware.call("etc.generate", "ctld")
        await self._service("ctld", "start", **kwargs)

    async def _stop_iscsitarget(self, **kwargs):
        with contextlib.suppress(IndexError):
            sysctl.filter("kern.cam.ctl.ha_peer")[0].value = ""

        await self._service("ctld", "stop", force=True, **kwargs)

    async def _reload_iscsitarget(self, **kwargs):
        await self.middleware.call("etc.generate", "ctld")
        await self._service("ctld", "reload", **kwargs)

    collectd_lock = asyncio.Lock()

    async def _start_collectd(self, **kwargs):
        async with (self.collectd_lock if kwargs.pop('_lock', True) else asyncnullcontext()):
            await self.middleware.call('etc.generate', 'collectd')

            if not await self.started('rrdcached'):
                # Let's ensure that before we start collectd, rrdcached is always running
                await self.start('rrdcached')

            await self._service("collectd-daemon", "restart", **kwargs)

    async def _stop_collectd(self, **kwargs):
        async with (self.collectd_lock if kwargs.pop('_lock', True) else asyncnullcontext()):
            await self._service("collectd-daemon", "stop", **kwargs)

    async def _restart_collectd(self, **kwargs):
        async with self.collectd_lock:
            await self._stop_collectd(_lock=False, **kwargs)
            await self._start_collectd(_lock=False, **kwargs)

    async def _started_collectd(self, **kwargs):
        if await self._service('collectd-daemon', 'status', quiet=True, **kwargs):
            return False, []
        else:
            return True, []

    async def _started_rrdcached(self, **kwargs):
        if await self._service('rrdcached', 'status', quiet=True, **kwargs):
            return False, []
        else:
            return True, []

    async def _stop_rrdcached(self, **kwargs):
        await self.stop('collectd')
        await self._service('rrdcached', 'stop', **kwargs)

    async def _restart_rrdcached(self, **kwargs):
        await self._stop_rrdcached(**kwargs)
        await self.start('rrdcached')
        await self.start('collectd')

    async def _reload_rc(self, **kwargs):
        await self.middleware.call('etc.generate', 'rc')

    async def _restart_powerd(self, **kwargs):
        await self.middleware.call('etc.generate', 'rc')
        await self._service('powerd', 'restart', **kwargs)

    async def _reload_sysctl(self, **kwargs):
        await self.middleware.call('etc.generate', 'sysctl')

    async def _start_network(self, **kwargs):
        await self.middleware.call('interface.sync')
        await self.middleware.call('route.sync')

    async def _reload_named(self, **kwargs):
        await self._service("named", "reload", **kwargs)

    async def _restart_syscons(self, **kwargs):
        await self.middleware.call('etc.generate', 'rc')
        await self._service('syscons', 'restart', **kwargs)

    async def _reload_hostname(self, **kwargs):
        await self._system('/bin/hostname ""')
        await self.middleware.call('etc.generate', 'hostname')
        await self.middleware.call('etc.generate', 'rc')
        await self._service("hostname", "start", quiet=True, **kwargs)
        await self.reload("mdns", kwargs)
        await self._restart_collectd(**kwargs)

    async def _reload_resolvconf(self, **kwargs):
        await self._reload_hostname()
        await self.middleware.call('dns.sync')

    async def _reload_networkgeneral(self, **kwargs):
        await self._reload_resolvconf()
        await self._service("routing", "restart", **kwargs)

    async def _start_routing(self, **kwargs):
        await self.middleware.call('etc.generate', 'rc')
        await self._service('routing', 'start', **kwargs)

    async def _reload_timeservices(self, **kwargs):
        await self.middleware.call('etc.generate', 'localtime')
        await self.middleware.call('etc.generate', 'ntpd')
        await self._service("ntpd", "restart", **kwargs)
        settings = await self.middleware.call(
            'datastore.query',
            'system.settings',
            [],
            {'order_by': ['-id'], 'get': True}
        )
        os.environ['TZ'] = settings['stg_timezone']
        time.tzset()

    async def _restart_ntpd(self, **kwargs):
        await self.middleware.call('etc.generate', 'ntpd')
        await self._service('ntpd', 'restart', **kwargs)

    async def _start_smartd(self, **kwargs):
        await self.middleware.call("etc.generate", "rc")
        await self.middleware.call("etc.generate", "smartd")
        await self._service("smartd-daemon", "start", **kwargs)

    def _initializing_smartd_pid(self):
        """
        smartd initialization can take a long time if lots of disks are present
        It only writes pidfile at the end of the initialization but forks immediately
        This method returns PID of smartd process that is still initializing and has not written pidfile yet
        """
        if os.path.exists(self.SERVICE_DEFS["smartd"].pidfile):
            # Already started, no need for special handling
            return

        for process in psutil.process_iter(attrs=["cmdline", "create_time"]):
            if process.info["cmdline"][:1] == ["/usr/local/sbin/smartd"]:
                break
        else:
            # No smartd process present
            return

        lifetime = time.time() - process.info["create_time"]
        if lifetime < 300:
            # Looks like just the process we need
            return process.pid

        self.logger.warning("Got an orphan smartd process: pid=%r, lifetime=%r", process.pid, lifetime)

    async def _started_smartd(self, **kwargs):
        result = await self._started("smartd")
        if result[0]:
            return result

        if await self.middleware.run_in_thread(self._initializing_smartd_pid) is not None:
            return True, []

        return False, []

    async def _reload_smartd(self, **kwargs):
        await self.middleware.call("etc.generate", "rc")
        await self.middleware.call("etc.generate", "smartd")

        pid = await self.middleware.run_in_thread(self._initializing_smartd_pid)
        if pid is None:
            await self._service("smartd-daemon", "reload", **kwargs)
            return

        os.kill(pid, signal.SIGKILL)
        await self._service("smartd-daemon", "start", **kwargs)

    async def _restart_smartd(self, **kwargs):
        await self.middleware.call("etc.generate", "rc")
        await self.middleware.call("etc.generate", "smartd")

        pid = await self.middleware.run_in_thread(self._initializing_smartd_pid)
        if pid is None:
            await self._service("smartd-daemon", "stop", force=True, **kwargs)
            await self._service("smartd-daemon", "restart", **kwargs)
            return

        os.kill(pid, signal.SIGKILL)
        await self._service("smartd-daemon", "start", **kwargs)

    async def _stop_smartd(self, **kwargs):
        pid = await self.middleware.run_in_thread(self._initializing_smartd_pid)
        if pid is None:
            await self._service("smartd-daemon", "stop", force=True, **kwargs)
            return

        os.kill(pid, signal.SIGKILL)

    async def _reload_ssh(self, **kwargs):
        await self.middleware.call('etc.generate', 'ssh')
        await self.reload("mdns", kwargs)
        await self._service("openssh", "reload", **kwargs)
        await self._service("ix_sshd_save_keys", "start", quiet=True, **kwargs)

    async def _start_ssh(self, **kwargs):
        await self.middleware.call('etc.generate', 'ssh')
        await self.reload("mdns", kwargs)
        await self._service("openssh", "start", **kwargs)
        await self._service("ix_sshd_save_keys", "start", quiet=True, **kwargs)

    async def _stop_ssh(self, **kwargs):
        await self._service("openssh", "stop", force=True, **kwargs)
        await self.reload("mdns", kwargs)

    async def _restart_ssh(self, **kwargs):
        await self.middleware.call('etc.generate', 'ssh')
        await self._service("openssh", "stop", force=True, **kwargs)
        await self._service("openssh", "restart", **kwargs)
        await self.reload("mdns", kwargs)
        await self._service("ix_sshd_save_keys", "start", quiet=True, **kwargs)

    async def _start_ssl(self, **kwargs):
        await self.middleware.call('etc.generate', 'ssl')

    async def _start_kmip(self, **kwargs):
        await self._start_ssl(**kwargs)
        await self.middleware.call('etc.generate', 'kmip')

    async def _start_s3(self, **kwargs):
        await self.middleware.call('etc.generate', 's3')
        await self._service("minio", "start", quiet=True, **kwargs)

    async def _reload_s3(self, **kwargs):
        await self.middleware.call('etc.generate', 's3')
        await self._service("minio", "restart", quiet=True, **kwargs)

    async def _reload_rsync(self, **kwargs):
        await self.middleware.call('etc.generate', 'rsync')
        await self._service("rsyncd", "restart", **kwargs)

    async def _restart_rsync(self, **kwargs):
        await self._stop_rsync()
        await self._start_rsync()

    async def _start_rsync(self, **kwargs):
        await self.middleware.call('etc.generate', 'rsync')
        await self._service("rsyncd", "start", **kwargs)

    async def _stop_rsync(self, **kwargs):
        await self._service("rsyncd", "stop", force=True, **kwargs)

    async def _started_nis(self, **kwargs):
        return (await self.middleware.call('nis.started')), []

    async def _start_nis(self, **kwargs):
        return (await self.middleware.call('nis.start')), []

    async def _restart_nis(self, **kwargs):
        await self.middleware.call('nis.stop')
        return (await self.middleware.call('nis.start')), []

    async def _stop_nis(self, **kwargs):
        return (await self.middleware.call('nis.stop')), []

    async def _started_ldap(self, **kwargs):
        return await self.middleware.call('ldap.started'), []

    async def _start_ldap(self, **kwargs):
        return await self.middleware.call('ldap.start'), []

    async def _stop_ldap(self, **kwargs):
        return await self.middleware.call('ldap.stop'), []

    async def _restart_ldap(self, **kwargs):
        await self.middleware.call('ldap.stop')
        return await self.middleware.call('ldap.start'), []

    async def _start_lldp(self, **kwargs):
        await self._service("ladvd", "start", **kwargs)

    async def _stop_lldp(self, **kwargs):
        await self._service("ladvd", "stop", force=True, **kwargs)

    async def _restart_lldp(self, **kwargs):
        await self._service("ladvd", "stop", force=True, **kwargs)
        await self._service("ladvd", "restart", **kwargs)

    async def _started_activedirectory(self, **kwargs):
        return await self.middleware.call('activedirectory.started'), []

    async def _start_activedirectory(self, **kwargs):
        return await self.middleware.call('activedirectory.start'), []

    async def _stop_activedirectory(self, **kwargs):
        return await self.middleware.call('activedirectory.stop'), []

    async def _restart_activedirectory(self, **kwargs):
        await self.middleware.call('kerberos.stop'), []
        return await self.middleware.call('activedirectory.start'), []

    async def _reload_activedirectory(self, **kwargs):
        await self._service("winbindd", "reload", quiet=True, **kwargs)

    async def _restart_syslogd(self, **kwargs):
        await self.middleware.call("etc.generate", "syslogd")
        await self._system("/etc/local/rc.d/syslog-ng restart")

    async def _start_syslogd(self, **kwargs):
        await self.middleware.call("etc.generate", "syslogd")
        await self._system("/etc/local/rc.d/syslog-ng start")

    async def _stop_syslogd(self, **kwargs):
        await self._system("/etc/local/rc.d/syslog-ng stop")

    async def _reload_syslogd(self, **kwargs):
        await self.middleware.call("etc.generate", "syslogd")
        await self._system("/etc/local/rc.d/syslog-ng reload")

    async def _start_tftp(self, **kwargs):
        await self.middleware.call('etc.generate', 'inetd')
        await self._service("inetd", "start", **kwargs)

    async def _reload_tftp(self, **kwargs):
        await self.middleware.call('etc.generate', 'inetd')
        await self._service("inetd", "stop", force=True, **kwargs)
        await self._service("inetd", "restart", **kwargs)

    async def _restart_tftp(self, **kwargs):
        await self.middleware.call('etc.generate', 'inetd')
        await self._service("inetd", "stop", force=True, **kwargs)
        await self._service("inetd", "restart", **kwargs)

    async def _restart_cron(self, **kwargs):
        await self.middleware.call('etc.generate', 'cron')

    async def _start_motd(self, **kwargs):
        await self.middleware.call('etc.generate', 'motd')
        await self._service("motd", "start", quiet=True, **kwargs)

    async def _start_ttys(self, **kwargs):
        await self.middleware.call('etc.generate', 'ttys')

    async def _reload_ftp(self, **kwargs):
        await self.middleware.call("etc.generate", "ftp")
        await self._service("proftpd", "restart", **kwargs)

    async def _restart_ftp(self, **kwargs):
        await self._stop_ftp()
        await self._start_ftp()

    async def _start_ftp(self, **kwargs):
        await self.middleware.call("etc.generate", "ftp")
        await self._service("proftpd", "start", **kwargs)

    async def _stop_ftp(self, **kwargs):
        await self._service("proftpd", "stop", force=True, **kwargs)

    async def _start_ups(self, **kwargs):
        await self.middleware.call('ups.dismiss_alerts')
        await self.middleware.call('etc.generate', 'ups')
        if (await self.middleware.call('ups.config'))['mode'] == 'MASTER':
            await self._service("nut", "start", **kwargs)
        await self._service("nut_upsmon", "start", **kwargs)
        await self._service("nut_upslog", "start", **kwargs)
        if await self.started('collectd'):
            asyncio.ensure_future(self.restart('collectd'))

    async def _stop_ups(self, **kwargs):
        await self.middleware.call('ups.dismiss_alerts')
        await self._service("nut_upslog", "stop", force=True, **kwargs)
        await self._service("nut_upsmon", "stop", force=True, **kwargs)
        await self._service("nut", "stop", force=True, **kwargs)
        if await self.started('collectd'):
            asyncio.ensure_future(self.restart('collectd'))

    async def _restart_ups(self, **kwargs):
        await self.middleware.call('ups.dismiss_alerts')
        await self.middleware.call('etc.generate', 'ups')
        await self._service("nut", "stop", force=True, onetime=True)
        # We need to wait on upsmon service to die properly as multiple processes are
        # associated with it and in most cases they haven't exited when a restart is initiated
        # for upsmon which fails as the older process is still running.
        await self._service("nut_upsmon", "stop", force=True, onetime=True)
        upsmon_processes = await run(['pgrep', '-x', 'upsmon'], encoding='utf8', check=False)
        if upsmon_processes.returncode == 0:
            gone, alive = await self.middleware.run_in_thread(
                psutil.wait_procs,
                map(
                    lambda v: psutil.Process(int(v)),
                    upsmon_processes.stdout.split()
                ),
                timeout=10
            )
            if alive:
                for pid in map(int, upsmon_processes.stdout.split()):
                    with contextlib.suppress(ProcessLookupError):
                        os.kill(pid, signal.SIGKILL)

        await self._service("nut_upslog", "stop", force=True, onetime=True)

        if (await self.middleware.call('ups.config'))['mode'] == 'MASTER':
            await self._service("nut", "restart", onetime=True)
        await self._service("nut_upsmon", "restart", onetime=True)
        await self._service("nut_upslog", "restart", onetime=True)
        if await self.started('collectd'):
            asyncio.ensure_future(self.restart('collectd'))

    async def _started_ups(self, **kwargs):
        return await self._started('upsmon')

    async def _start_afp(self, **kwargs):
        await self.middleware.call("etc.generate", "afpd")
        await self._service("netatalk", "start", **kwargs)
        await self.reload("mdns", kwargs)

    async def _stop_afp(self, **kwargs):
        await self._service("netatalk", "stop", force=True, **kwargs)
        # when netatalk stops if afpd or cnid_metad is stuck
        # they'll get left behind, which can cause issues
        # restarting netatalk.
        await self._system("pkill -9 afpd")
        await self._system("pkill -9 cnid_metad")
        await self.reload("mdns", kwargs)

    async def _restart_afp(self, **kwargs):
        await self._stop_afp()
        await self._start_afp()

    async def _reload_afp(self, **kwargs):
        await self.middleware.call("etc.generate", "afpd")
        await self._system("killall -1 netatalk")
        await self.reload("mdns", kwargs)

    async def _reload_nfs(self, **kwargs):
        await self.middleware.call("etc.generate", "nfsd")
        await self.middleware.call("nfs.setup_v4")
        await self._service("mountd", "reload", force=True, **kwargs)

    async def _restart_nfs(self, **kwargs):
        await self._stop_nfs(**kwargs)
        await self._start_nfs(**kwargs)

    async def _stop_nfs(self, **kwargs):
        await self._service("lockd", "stop", force=True, **kwargs)
        await self._service("statd", "stop", force=True, **kwargs)
        await self._service("nfsd", "stop", force=True, **kwargs)
        await self._service("mountd", "stop", force=True, **kwargs)
        await self._service("nfsuserd", "stop", force=True, **kwargs)
        await self._service("gssd", "stop", force=True, **kwargs)
        await self._service("rpcbind", "stop", force=True, **kwargs)

    async def _start_nfs(self, **kwargs):
        await self.middleware.call("etc.generate", "nfsd")
        await self._service("rpcbind", "start", quiet=True, **kwargs)
        await self.middleware.call("nfs.setup_v4")
        await self._service("mountd", "start", quiet=True, **kwargs)
        await self._service("nfsd", "start", quiet=True, **kwargs)
        await self._service("statd", "start", quiet=True, **kwargs)
        await self._service("lockd", "start", quiet=True, **kwargs)

    async def _start_dynamicdns(self, **kwargs):
        await self.middleware.call('etc.generate', 'inadyn')
        await self._service("inadyn", "start", **kwargs)

    async def _restart_dynamicdns(self, **kwargs):
        await self.middleware.call('etc.generate', 'inadyn')
        await self._service("inadyn", "stop", force=True, **kwargs)
        await self._service("inadyn", "restart", **kwargs)

    async def _reload_dynamicdns(self, **kwargs):
        await self.middleware.call('etc.generate', 'inadyn')
        await self._service("inadyn", "stop", force=True, **kwargs)
        await self._service("inadyn", "restart", **kwargs)

    async def _restart_system(self, **kwargs):
        asyncio.ensure_future(self.middleware.call('system.reboot', {'delay': 3}))

    async def _stop_system(self, **kwargs):
        asyncio.ensure_future(self.middleware.call('system.shutdown', {'delay': 3}))

    async def _reload_cifs(self, **kwargs):
        """
        Reload occurs when SMB shares change. This does not require
        restarting nmbd, winbindd, or wsdd. mDNS advertisement may
        change due to time machine.
        """
        await self._service("smbd", "reload", force=True, **kwargs)
        await self.reload("mdns", kwargs)

    async def _restart_cifs(self, **kwargs):
        announce = (await self.middleware.call('network.configuration.config')
                    )['service_announcement']
        await self.middleware.call("etc.generate", "smb")
        await self.middleware.call("etc.generate", "smb_share")
        await self._service("smbd", "restart", force=True, **kwargs)
        await self._service("winbindd", "restart", force=True, **kwargs)
        if announce['netbios']:
            await self._service("nmbd", "restart", force=True, **kwargs)
        if announce['wsd']:
            await self._service("wsdd", "restart", force=True, **kwargs)
        await self.reload("mdns", kwargs)

    async def _start_cifs(self, **kwargs):
        announce = (await self.middleware.call('network.configuration.config')
                    )['service_announcement']
        await self.middleware.call("etc.generate", "smb")
        await self.middleware.call("etc.generate", "smb_share")
        await self._service("smbd", "start", force=True, **kwargs)
        await self._service("winbindd", "start", force=True, **kwargs)
        if announce['netbios']:
            await self._service("nmbd", "start", force=True, **kwargs)
        if announce['wsd']:
            await self._service("wsdd", "start", force=True, **kwargs)

        await self.reload("mdns", kwargs)
        try:
            await self.middleware.call("smb.add_admin_group", "", True)
        except Exception as e:
            raise CallError(e)

    async def _stop_cifs(self, **kwargs):
        await self._service("smbd", "stop", force=True, **kwargs)
        await self._service("winbindd", "stop", force=True, **kwargs)
        await self._service("nmbd", "stop", force=True, **kwargs)
        await self._service("wsdd", "stop", force=True, **kwargs)
        await self.reload("mdns", kwargs)

    async def _started_cifs(self, **kwargs):
        if await self._service("smbd", "status", quiet=True, onetime=True, **kwargs):
            return False, []
        else:
            return True, []

    async def _start_snmp(self, **kwargs):
        await self.middleware.call("etc.generate", "snmpd")
        await self._service("snmpd", "start", quiet=True, **kwargs)
        await self._service("snmp-agent", "start", quiet=True, **kwargs)

    async def _stop_snmp(self, **kwargs):
        await self._service("snmp-agent", "stop", quiet=True, **kwargs)
        await self._service("snmpd", "stop", quiet=True, **kwargs)

    async def _restart_snmp(self, **kwargs):
        await self._service("snmp-agent", "stop", quiet=True, **kwargs)
        await self._service("snmpd", "stop", force=True, **kwargs)
        await self.middleware.call("etc.generate", "snmpd")
        await self._service("snmpd", "start", quiet=True, **kwargs)
        await self._service("snmp-agent", "start", quiet=True, **kwargs)

    async def _reload_snmp(self, **kwargs):
        await self._service("snmp-agent", "stop", quiet=True, **kwargs)
        await self._service("snmpd", "stop", force=True, **kwargs)
        await self.middleware.call("etc.generate", "snmpd")
        await self._service("snmpd", "start", quiet=True, **kwargs)
        await self._service("snmp-agent", "start", quiet=True, **kwargs)

    async def _restart_http(self, **kwargs):
        await self.middleware.call("etc.generate", "nginx")
        await self.reload("mdns", kwargs)
        await self._service("nginx", "restart", **kwargs)

    async def _reload_http(self, **kwargs):
        await self.middleware.call("etc.generate", "nginx")
        await self.reload("mdns", kwargs)
        await self._service("nginx", "reload", **kwargs)

    async def _reload_loader(self, **kwargs):
        await self.middleware.call("etc.generate", "loader")

    async def _restart_disk(self, **kwargs):
        await self._reload_disk(**kwargs)

    async def _reload_disk(self, **kwargs):
        await self.middleware.call('etc.generate', 'fstab')
        await self._service("mountlate", "start", quiet=True, **kwargs)
        # Restarting rrdcached can take a long time. There is no
        # benefit in waiting for it, since even if it fails it will not
        # tell the user anything useful.
        asyncio.ensure_future(self.restart("collectd", kwargs))

    async def _reload_user(self, **kwargs):
        await self.middleware.call("etc.generate", "user")
        await self.middleware.call('etc.generate', 'aliases')
        await self.middleware.call('etc.generate', 'sudoers')
        await self.reload("cifs", kwargs)

    async def _restart_system_datasets(self, **kwargs):
        systemdataset = await self.middleware.call('systemdataset.setup')
        if not systemdataset:
            return None
        if systemdataset['syslog']:
            await self.restart("syslogd", kwargs)
        await self.restart("cifs", {'onetime': False})

        # Restarting rrdcached can take a long time. There is no
        # benefit in waiting for it, since even if it fails it will not
        # tell the user anything useful.
        # Restarting rrdcached will make sure that we start/restart collectd as well
        asyncio.ensure_future(self.restart("rrdcached", kwargs))

    @private
    async def identify_process(self, name):
        for service, definition in self.SERVICE_DEFS.items():
            if definition.procname == name:
                return service

    @accepts(Int("pid"), Int("timeout", default=10))
    def terminate_process(self, pid, timeout):
        """
        Terminate process by `pid`.

        First send `TERM` signal, then, if was not terminated in `timeout` seconds, send `KILL` signal.

        Returns `true` is process has been successfully terminated with `TERM` and `false` if we had to use `KILL`.
        """
        try:
            process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            raise CallError("Process does not exist")

        process.terminate()

        gone, alive = psutil.wait_procs([process], timeout)
        if not alive:
            return True

        alive[0].kill()
        return False


def setup(middleware):
    middleware.event_register('service.query', 'Sent on service changes.')
