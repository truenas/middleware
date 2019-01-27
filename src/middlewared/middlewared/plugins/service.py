import asyncio
import errno
import inspect
import os
import signal
import sysctl
import threading
import time
from subprocess import DEVNULL, PIPE

from middlewared.schema import accepts, Bool, Dict, Ref, Str
from middlewared.service import filterable, CallError, CRUDService
from middlewared.utils import Popen, filter_list


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
        'ups': ServiceDefinition('upsd', '/var/db/nut/upsd.pid'),
        'upsmon': ServiceDefinition('upsmon', '/var/db/nut/upsmon.pid'),
        'smartd': ServiceDefinition('smartd', 'smartd-daemon', '/var/run/smartd-daemon.pid'),
        'webshell': ServiceDefinition(None, '/var/run/webshell.pid'),
        'webdav': ServiceDefinition('httpd', '/var/run/httpd.pid'),
        'netdata': ServiceDefinition('netdata', '/var/db/netdata/netdata.pid'),
        'asigra': ServiceDefinition('asigra', '/var/run/dssystem.pid')
    }

    @filterable
    async def query(self, filters=None, options=None):
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

        return await self.middleware.call('datastore.update', 'services.services', id_or_name, {'srv_enable': data['enable']})

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

    async def _system(self, cmd, options=None):
        stdout = DEVNULL
        if options and 'stdout' in options:
            stdout = options['stdout']
        stderr = DEVNULL
        if options and 'stderr' in options:
            stderr = options['stderr']

        proc = await Popen(cmd, stdout=stdout, stderr=stderr, shell=True, close_fds=True)
        await proc.communicate()
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
        ), options)

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
            proc = await Popen(pgrep, shell=True, stdout=PIPE, stderr=PIPE, close_fds=True)
            data = (await proc.communicate())[0].decode()

            if proc.returncode == 0:
                return True, [
                    int(i)
                    for i in data.strip().split('\n') if i.isdigit()
                ]
        return False, []

    async def _start_asigra(self, **kwargs):
        await self.middleware.call('asigra.setup_filesystems')
        await self.middleware.call('asigra.setup_postgresql')
        await self._service("postgresql", "start", force=True, **kwargs)
        await self.middleware.call('asigra.setup_asigra')
        await self.middleware.call('etc.generate', 'asigra')
        await self._service("dssystem", "start", force=True, **kwargs)

    async def _stop_asigra(self, **kwargs):
        await self._service("dssystem", "stop", force=True, **kwargs)
        await self._service("postgresql", "stop", force=True, **kwargs)

    async def _restart_asigra(self, **kwargs):
        await self._stop_asigra(**kwargs)
        await self._start_asigra(**kwargs)

    async def _started_asigra(self, **kwargs):
        if await self._service("dssystem", "status", force=True, **kwargs) != 0:
            return False, []
        return True, []

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

    async def _restart_django(self, **kwargs):
        await self._service("django", "restart", **kwargs)

    async def _start_webshell(self, **kwargs):
        await self._system("/usr/local/bin/python /usr/local/www/freenasUI/tools/webshell.py")

    async def _restart_webshell(self, **kwargs):
        try:
            with open('/var/run/webshell.pid', 'r') as f:
                pid = f.read()
                os.kill(int(pid), signal.SIGTERM)
                time.sleep(0.2)
                os.kill(int(pid), signal.SIGKILL)
        except Exception:
            pass
        await self._system("ulimit -n 1024 && /usr/local/bin/python /usr/local/www/freenasUI/tools/webshell.py")

    async def _restart_iscsitarget(self, **kwargs):
        await self._service("ix-ctld", "start", force=True, **kwargs)
        await self._service("ctld", "stop", force=True, **kwargs)
        await self._service("ix-ctld", "start", quiet=True, **kwargs)
        await self._service("ctld", "restart", **kwargs)

    async def _start_iscsitarget(self, **kwargs):
        await self._service("ix-ctld", "start", quiet=True, **kwargs)
        await self._service("ctld", "start", **kwargs)

    async def _stop_iscsitarget(self, **kwargs):
        await self._service("ix-ctld", "stop", force=True, **kwargs)
        await self._service("ctld", "stop", force=True, **kwargs)

    async def _reload_iscsitarget(self, **kwargs):
        await self._service("ix-ctld", "start", quiet=True, **kwargs)
        await self._service("ctld", "reload", **kwargs)

    async def _start_collectd(self, **kwargs):
        await self.middleware.call('etc.generate', 'collectd')
        await self._service("collectd", "restart", **kwargs)

    async def _restart_collectd(self, **kwargs):
        await self._service("collectd", "stop", **kwargs)
        await self._start_collectd(**kwargs)

    async def _start_sysctl(self, **kwargs):
        await self._service("ix-sysctl", "start", quiet=True, **kwargs)

    async def _reload_sysctl(self, **kwargs):
        await self._service("ix-sysctl", "reload", **kwargs)

    async def _start_network(self, **kwargs):
        await self.middleware.call('interface.sync')
        await self.middleware.call('route.sync')

    async def _reload_named(self, **kwargs):
        await self._service("named", "reload", **kwargs)

    async def _reload_hostname(self, **kwargs):
        await self._system('/bin/hostname ""')
        await self._service("ix-hostname", "start", quiet=True, **kwargs)
        await self._service("hostname", "start", quiet=True, **kwargs)
        await self._service("mdnsd", "restart", quiet=True, **kwargs)
        await self._restart_collectd(**kwargs)

    async def _reload_resolvconf(self, **kwargs):
        await self._reload_hostname()
        await self._service("ix-resolv", "start", quiet=True, **kwargs)

    async def _reload_networkgeneral(self, **kwargs):
        await self._reload_resolvconf()
        await self._service("routing", "restart", **kwargs)

    async def _reload_timeservices(self, **kwargs):
        await self._service("ix-localtime", "start", quiet=True, **kwargs)
        await self._service("ix-ntpd", "start", quiet=True, **kwargs)
        await self._service("ntpd", "restart", **kwargs)
        settings = await self.middleware.call(
            'datastore.query',
            'system.settings',
            [],
            {'order_by': ['-id'], 'get': True}
        )
        os.environ['TZ'] = settings['stg_timezone']
        time.tzset()

    async def _start_smartd(self, **kwargs):
        await self.middleware.call("etc.generate", "smartd")
        await self._service("smartd-daemon", "start", **kwargs)

    async def _reload_smartd(self, **kwargs):
        await self.middleware.call("etc.generate", "smartd")
        await self._service("smartd-daemon", "reload", **kwargs)

    async def _restart_smartd(self, **kwargs):
        await self.middleware.call("etc.generate", "smartd")
        await self._service("smartd-daemon", "stop", force=True, **kwargs)
        await self._service("smartd-daemon", "restart", **kwargs)

    async def _reload_ssh(self, **kwargs):
        await self._service("ix-sshd", "start", quiet=True, **kwargs)
        await self._service("ix_register", "reload", **kwargs)
        await self._service("openssh", "reload", **kwargs)
        await self._service("ix_sshd_save_keys", "start", quiet=True, **kwargs)

    async def _start_ssh(self, **kwargs):
        await self._service("ix-sshd", "start", quiet=True, **kwargs)
        await self._service("ix_register", "reload", **kwargs)
        await self._service("openssh", "start", **kwargs)
        await self._service("ix_sshd_save_keys", "start", quiet=True, **kwargs)

    async def _stop_ssh(self, **kwargs):
        await self._service("openssh", "stop", force=True, **kwargs)
        await self._service("ix_register", "reload", **kwargs)

    async def _restart_ssh(self, **kwargs):
        await self._service("ix-sshd", "start", quiet=True, **kwargs)
        await self._service("openssh", "stop", force=True, **kwargs)
        await self._service("ix_register", "reload", **kwargs)
        await self._service("openssh", "restart", **kwargs)
        await self._service("ix_sshd_save_keys", "start", quiet=True, **kwargs)

    async def _start_ssl(self, **kwargs):
        await self.middleware.call('etc.generate', 'ssl')

    async def _start_s3(self, **kwargs):
        await self.middleware.call('etc.generate', 's3')
        await self._service("minio", "start", quiet=True, stdout=None, stderr=None, **kwargs)

    async def _reload_s3(self, **kwargs):
        await self.middleware.call('etc.generate', 's3')
        await self._service("minio", "restart", quiet=True, stdout=None, stderr=None, **kwargs)

    async def _reload_rsync(self, **kwargs):
        await self._service("ix-rsyncd", "start", quiet=True, **kwargs)
        await self._service("rsyncd", "restart", **kwargs)

    async def _restart_rsync(self, **kwargs):
        await self._stop_rsync()
        await self._start_rsync()

    async def _start_rsync(self, **kwargs):
        await self._service("ix-rsyncd", "start", quiet=True, **kwargs)
        await self._service("rsyncd", "start", **kwargs)

    async def _stop_rsync(self, **kwargs):
        await self._service("rsyncd", "stop", force=True, **kwargs)

    async def _started_nis(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/NIS/ctl status"):
            res = True
        return res, []

    async def _start_nis(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/NIS/ctl start"):
            res = True
        return res

    async def _restart_nis(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/NIS/ctl restart"):
            res = True
        return res

    async def _stop_nis(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/NIS/ctl stop"):
            res = True
        return res

    async def _started_ldap(self, **kwargs):
        if (await self._system('/usr/sbin/service ix-ldap status') != 0):
            return False, []
        return await self.middleware.call('notifier.ldap_status'), []

    async def _start_ldap(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/LDAP/ctl start"):
            res = True
        return res

    async def _stop_ldap(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/LDAP/ctl stop"):
            res = True
        return res

    async def _restart_ldap(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/LDAP/ctl restart"):
            res = True
        return res

    async def _start_lldp(self, **kwargs):
        await self._service("ladvd", "start", **kwargs)

    async def _stop_lldp(self, **kwargs):
        await self._service("ladvd", "stop", force=True, **kwargs)

    async def _restart_lldp(self, **kwargs):
        await self._service("ladvd", "stop", force=True, **kwargs)
        await self._service("ladvd", "restart", **kwargs)

    async def _clear_activedirectory_config(self):
        await self._system("/bin/rm -f /etc/directoryservice/ActiveDirectory/config")

    async def _started_activedirectory(self, **kwargs):
        # Perform a wbinfo -t because it's the most accurate single test we have to
        # detect problems with AD join. The default winbind timeout is 60 seconds (as of Samba 4.7).
        # This can be controlled by the smb4.conf parameter "winbind request timeout = "
        if await self._system('/usr/local/bin/wbinfo -t') != 0:
                self.logger.debug('AD monitor: wbinfo -t failed')
                return False, []
        return True, []

    async def _start_activedirectory(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/ActiveDirectory/ctl start"):
            res = True
        return res

    async def _stop_activedirectory(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/ActiveDirectory/ctl stop"):
            res = True
        return res

    async def _restart_activedirectory(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/ActiveDirectory/ctl restart"):
            res = True
        return res

    async def _reload_activedirectory(self, **kwargs):
        # Steps required to force winbind to connect to new DC if DC it's connected to goes down
        # We may need to expand the list of operations below to include fresh kinit. Some
        # information about winbind connection is stored in samba's gencache. In test cases, flushing
        # gencache (net cache flush) was not required to do this.
        await self._service("samba_server", "stop", force=True, **kwargs)
        await self._service("samba_server", "start", quiet=True, **kwargs)

    async def _started_domaincontroller(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/DomainController/ctl status"):
            res = True
        return res, []

    async def _start_domaincontroller(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/DomainController/ctl start"):
            res = True
        return res

    async def _stop_domaincontroller(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/DomainController/ctl stop"):
            res = True
        return res

    async def _restart_domaincontroller(self, **kwargs):
        res = False
        if not await self._system("/etc/directoryservice/DomainController/ctl restart"):
            res = True
        return res

    async def _restart_syslogd(self, **kwargs):
        await self._service("ix-syslogd", "start", quiet=True, **kwargs)
        await self._system("/etc/local/rc.d/syslog-ng restart")

    async def _start_syslogd(self, **kwargs):
        await self._service("ix-syslogd", "start", quiet=True, **kwargs)
        await self._system("/etc/local/rc.d/syslog-ng start")

    async def _stop_syslogd(self, **kwargs):
        await self._system("/etc/local/rc.d/syslog-ng stop")

    async def _reload_syslogd(self, **kwargs):
        await self._service("ix-syslogd", "start", quiet=True, **kwargs)
        await self._system("/etc/local/rc.d/syslog-ng reload")

    async def _start_tftp(self, **kwargs):
        await self._service("ix-inetd", "start", quiet=True, **kwargs)
        await self._service("inetd", "start", **kwargs)

    async def _reload_tftp(self, **kwargs):
        await self._service("ix-inetd", "start", quiet=True, **kwargs)
        await self._service("inetd", "stop", force=True, **kwargs)
        await self._service("inetd", "restart", **kwargs)

    async def _restart_tftp(self, **kwargs):
        await self._service("ix-inetd", "start", quiet=True, **kwargs)
        await self._service("inetd", "stop", force=True, **kwargs)
        await self._service("inetd", "restart", **kwargs)

    async def _restart_cron(self, **kwargs):
        await self._service("ix-crontab", "start", quiet=True, **kwargs)

    async def _start_motd(self, **kwargs):
        await self._service("ix-motd", "start", quiet=True, **kwargs)
        await self._service("motd", "start", quiet=True, **kwargs)

    async def _start_ttys(self, **kwargs):
        await self._service("ix-ttys", "start", quiet=True, **kwargs)

    async def _reload_ftp(self, **kwargs):
        await self._service("ix-proftpd", "start", quiet=True, **kwargs)
        await self._service("proftpd", "restart", **kwargs)

    async def _restart_ftp(self, **kwargs):
        await self._stop_ftp()
        await self._start_ftp()

    async def _start_ftp(self, **kwargs):
        await self._service("ix-proftpd", "start", quiet=True, **kwargs)
        await self._service("proftpd", "start", **kwargs)

    async def _stop_ftp(self, **kwargs):
        await self._service("proftpd", "stop", force=True, **kwargs)

    async def _start_ups(self, **kwargs):
        await self._service("ix-ups", "start", quiet=True, **kwargs)
        await self._service("nut", "start", **kwargs)
        await self._service("nut_upsmon", "start", **kwargs)
        await self._service("nut_upslog", "start", **kwargs)
        # FIXME: Is it ideal restarting collectd like this ? If the system dataset is not configured
        # this will fail
        asyncio.ensure_future(self.restart('collectd'))

    async def _stop_ups(self, **kwargs):
        await self._service("nut_upslog", "stop", force=True, **kwargs)
        await self._service("nut_upsmon", "stop", force=True, **kwargs)
        await self._service("nut", "stop", force=True, **kwargs)
        asyncio.ensure_future(self.restart('collectd'))

    async def _restart_ups(self, **kwargs):
        await self._service("ix-ups", "start", quiet=True, **kwargs)
        await self._service("nut", "stop", force=True, **kwargs)
        await self._service("nut_upsmon", "stop", force=True, **kwargs)
        await self._service("nut_upslog", "stop", force=True, **kwargs)
        await self._service("nut", "restart", **kwargs)
        await self._service("nut_upsmon", "restart", **kwargs)
        await self._service("nut_upslog", "restart", **kwargs)
        asyncio.ensure_future(self.restart('collectd'))

    async def _started_ups(self, **kwargs):
        mode = (await self.middleware.call('datastore.query', 'services.ups', [], {'order_by': ['-id'], 'get': True}))['ups_mode']
        if mode == "master":
            svc = "ups"
        else:
            svc = "upsmon"
        return await self._started(svc)

    async def _start_afp(self, **kwargs):
        await self._service("ix-afpd", "start", **kwargs)
        await self._service("netatalk", "start", **kwargs)

    async def _stop_afp(self, **kwargs):
        await self._service("netatalk", "stop", force=True, **kwargs)
        # when netatalk stops if afpd or cnid_metad is stuck
        # they'll get left behind, which can cause issues
        # restarting netatalk.
        await self._system("pkill -9 afpd")
        await self._system("pkill -9 cnid_metad")

    async def _restart_afp(self, **kwargs):
        await self._stop_afp()
        await self._start_afp()

    async def _reload_afp(self, **kwargs):
        await self._service("ix-afpd", "start", quiet=True, **kwargs)
        await self._system("killall -1 netatalk")

    async def _reload_nfs(self, **kwargs):
        await self.middleware.call("etc.generate", "nfsd")

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
        nfs = await self.middleware.call('datastore.config', 'services.nfs')
        await self.middleware.call("etc.generate", "nfsd")
        await self._service("rpcbind", "start", quiet=True, **kwargs)
        await self._service("gssd", "start", quiet=True, **kwargs)
        # Workaround to work with "onetime", since the rc scripts depend on rc flags.
        if nfs['nfs_srv_v4']:
            sysctl.filter('vfs.nfsd.server_max_nfsvers')[0].value = 4
            if nfs['nfs_srv_v4_v3owner']:
                # Per RFC7530, sending NFSv3 style UID/GIDs across the wire is now allowed
                # You must have both of these sysctl's set to allow the desired functionality
                sysctl.filter('vfs.nfsd.enable_stringtouid')[0].value = 1
                sysctl.filter('vfs.nfs.enable_uidtostring')[0].value = 1
                await self._service("nfsuserd", "stop", force=True, **kwargs)
            else:
                sysctl.filter('vfs.nfsd.enable_stringtouid')[0].value = 0
                sysctl.filter('vfs.nfs.enable_uidtostring')[0].value = 0
                await self._service("nfsuserd", "start", quiet=True, **kwargs)
        else:
            sysctl.filter('vfs.nfsd.server_max_nfsvers')[0].value = 3
            if nfs['nfs_srv_16']:
                await self._service("nfsuserd", "start", quiet=True, **kwargs)
        await self._service("mountd", "start", quiet=True, **kwargs)
        await self._service("nfsd", "start", quiet=True, **kwargs)
        await self._service("statd", "start", quiet=True, **kwargs)
        await self._service("lockd", "start", quiet=True, **kwargs)

    async def _start_dynamicdns(self, **kwargs):
        await self._service("ix-inadyn", "start", quiet=True, **kwargs)
        await self._service("inadyn", "start", **kwargs)

    async def _restart_dynamicdns(self, **kwargs):
        await self._service("ix-inadyn", "start", quiet=True, **kwargs)
        await self._service("inadyn", "stop", force=True, **kwargs)
        await self._service("inadyn", "restart", **kwargs)

    async def _reload_dynamicdns(self, **kwargs):
        await self._service("ix-inadyn", "start", quiet=True, **kwargs)
        await self._service("inadyn", "stop", force=True, **kwargs)
        await self._service("inadyn", "restart", **kwargs)

    async def _restart_system(self, **kwargs):
        asyncio.ensure_future(self._system("/bin/sleep 3 && /sbin/shutdown -r now"))

    async def _stop_system(self, **kwargs):
        asyncio.ensure_future(self._system("/bin/sleep 3 && /sbin/shutdown -p now"))

    async def _reload_cifs(self, **kwargs):
        await self.middleware.call("etc.generate", "smb_share")
        await self._service("samba_server", "reload", force=True, **kwargs)
        await self._service("mdnsd", "restart", **kwargs)
        # After mdns is restarted we need to reload netatalk to have it rereregister
        # with mdns. Ticket #7133
        await self._service("netatalk", "reload", **kwargs)

    async def _restart_cifs(self, **kwargs):
        await self.middleware.call("etc.generate", "smb")
        await self.middleware.call("etc.generate", "smb_share")
        await self._service("samba_server", "stop", force=True, **kwargs)
        await self._service("samba_server", "restart", quiet=True, **kwargs)
        await self._service("mdnsd", "restart", **kwargs)
        # After mdns is restarted we need to reload netatalk to have it rereregister
        # with mdns. Ticket #7133
        await self._service("netatalk", "reload", **kwargs)

    async def _start_cifs(self, **kwargs):
        await self.middleware.call("etc.generate", "smb")
        await self.middleware.call("etc.generate", "smb_share")
        await self._service("samba_server", "start", quiet=True, **kwargs)

    async def _stop_cifs(self, **kwargs):
        await self._service("samba_server", "stop", force=True, **kwargs)

    async def _started_cifs(self, **kwargs):
        if await self._service("samba_server", "status", quiet=True, onetime=True, **kwargs):
            return False, []
        else:
            return True, []

    async def _start_snmp(self, **kwargs):
        await self._service("ix-snmpd", "start", quiet=True, **kwargs)
        await self._service("snmpd", "start", quiet=True, **kwargs)
        await self._service("snmp-agent", "start", quiet=True, **kwargs)

    async def _stop_snmp(self, **kwargs):
        await self._service("snmp-agent", "stop", quiet=True, **kwargs)
        await self._service("snmpd", "stop", quiet=True, **kwargs)

    async def _restart_snmp(self, **kwargs):
        await self._service("snmp-agent", "stop", quiet=True, **kwargs)
        await self._service("snmpd", "stop", force=True, **kwargs)
        await self._service("ix-snmpd", "start", quiet=True, **kwargs)
        await self._service("snmpd", "start", quiet=True, **kwargs)
        await self._service("snmp-agent", "start", quiet=True, **kwargs)

    async def _reload_snmp(self, **kwargs):
        await self._service("snmp-agent", "stop", quiet=True, **kwargs)
        await self._service("snmpd", "stop", force=True, **kwargs)
        await self._service("ix-snmpd", "start", quiet=True, **kwargs)
        await self._service("snmpd", "start", quiet=True, **kwargs)
        await self._service("snmp-agent", "start", quiet=True, **kwargs)

    async def _restart_http(self, **kwargs):
        await self.middleware.call("etc.generate", "nginx")
        await self._service("ix_register", "reload", **kwargs)
        await self._service("nginx", "restart", **kwargs)

    async def _reload_http(self, **kwargs):
        await self.middleware.call("etc.generate", "nginx")
        await self._service("ix_register", "reload", **kwargs)
        await self._service("nginx", "reload", **kwargs)

    async def _reload_loader(self, **kwargs):
        await self._service("ix-loader", "reload", **kwargs)

    async def _start_loader(self, **kwargs):
        await self._service("ix-loader", "start", quiet=True, **kwargs)

    async def _restart_disk(self, **kwargs):
        await self._reload_disk(**kwargs)

    async def _reload_disk(self, **kwargs):
        await self._service("ix-fstab", "start", quiet=True, **kwargs)
        await self._service("mountlate", "start", quiet=True, **kwargs)
        # Restarting collectd may take a long time and there is no
        # benefit in waiting for it since even if it fails it wont
        # tell the user anything useful.
        asyncio.ensure_future(self.restart("collectd", kwargs))

    async def _reload_user(self, **kwargs):
        await self.middleware.call("etc.generate", "user")
        await self._service("ix-aliases", "start", quiet=True, **kwargs)
        await self._service("ix-sudoers", "start", quiet=True, **kwargs)
        await self.reload("cifs", kwargs)

    async def _restart_system_datasets(self, **kwargs):
        systemdataset = await self.middleware.call('systemdataset.setup')
        if not systemdataset:
            return None
        if systemdataset['syslog']:
            await self.restart("syslogd", kwargs)
        await self.restart("cifs", kwargs)

        # Restarting rrdcached may take a long time and there is no
        # benefit in waiting for it since even if it fails it wont
        # tell the user anything useful.
        asyncio.ensure_future(self.restart("rrdcached", kwargs))
        asyncio.ensure_future(self.start("collectd", kwargs))

    async def _start_netdata(self, **kwargs):
        await self.middleware.call('etc.generate', 'netdata')
        await self._service('netdata', 'start', **kwargs)

    async def _restart_netdata(self, **kwargs):
        await self._service('netdata', 'stop')
        await self._start_netdata(**kwargs)
