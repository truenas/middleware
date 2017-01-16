import gevent
import os
import signal
import threading
import time
from subprocess import PIPE

from middlewared.schema import accepts, Bool, Dict, Int, Str
from middlewared.service import filterable, Service
from middlewared.utils import Popen, filter_list
from middlewared.plugins.service_monitor import ServiceMonitor


class StartNotify(threading.Thread):

    def __init__(self, pidfile, verb, *args, **kwargs):
        self._pidfile = pidfile
        self._verb = verb
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
                if (
                    os.path.exists(self._pidfile) and
                    os.stat(self._pidfile).st_size > 0
                ):
                    break
            elif self._verb == "stop" and not os.path.exists(self._pidfile):
                break
            tries += 1


class ServiceService(Service):

    SERVICE_DEFS = {
        'ssh': ('sshd', '/var/run/sshd.pid'),
        'rsync': ('rsync', '/var/run/rsyncd.pid'),
        'nfs': ('nfsd', None),
        'afp': ('netatalk', None),
        'cifs': ('smbd', '/var/run/samba/smbd.pid'),
        'dynamicdns': ('inadyn-mt', None),
        'snmp': ('snmpd', '/var/run/net_snmpd.pid'),
        'ftp': ('proftpd', '/var/run/proftpd.pid'),
        'tftp': ('inetd', '/var/run/inetd.pid'),
        'iscsitarget': ('ctld', '/var/run/ctld.pid'),
        'lldp': ('ladvd', '/var/run/ladvd.pid'),
        'ups': ('upsd', '/var/db/nut/upsd.pid'),
        'upsmon': ('upsmon', '/var/db/nut/upsmon.pid'),
        'smartd': ('smartd', '/var/run/smartd.pid'),
        'webshell': (None, '/var/run/webshell.pid'),
        'webdav': ('httpd', '/var/run/httpd.pid'),
        'backup': (None, '/var/run/backup.pid')
    }

    @filterable
    def query(self, filters=None, options=None):
        if options is None:
            options = {}
        options['suffix'] = 'srv_'

        services = self.middleware.call('datastore.query', 'services.services', filters, options)

        # In case a single service has been requested
        if not isinstance(services, list):
            services = [services]

        jobs = {
            gevent.spawn(self._get_status, entry): entry
            for entry in services
        }
        gevent.joinall(list(jobs.keys()), timeout=15)

        def result(greenlet):
            """
            Method to handle results of the greenlets.
            In case a greenlet has timed out, provide UNKNOWN state
            """
            if greenlet.value is None:
                entry = jobs.get(greenlet)
                entry['state'] = 'UNKNOWN'
                entry['pids'] = []
                return entry
            else:
                return greenlet.value

        services = gevent.pool.Group().map(result, jobs)
        return filter_list(services, filters, options)

    @accepts(
        Int('id'),
        Dict(
            'service-update',
            Bool('enable'),
        ),
    )
    def update(self, id, data):
        """
        Update service entry of `id`.

        Currently it only accepts `enable` option which means whether the
        service should start on boot.

        """
        return self.middleware.call('datastore.update', 'services.services', id, {'srv_enable': data['enable']})

    @accepts(
        Str('service'),
        Dict(
            'service-control',
            Bool('onetime'),
        ),
    )
    def start(self, service, options=None):
        """ Start the service specified by `service`.

        The helper will use method self._start_[service]() to start the service.
        If the method does not exist, it would fallback using service(8)."""
        if options is None:
            options = {
                'onetime': True,
            }
        self.middleware.call_hook('service.pre_start', service)
        sn = self._started_notify("start", service)
        self._simplecmd("start", service, options)
        return self.started(service, sn)

    def started(self, service, sn=None):
        """
        Test if service specified by `service` has been started.
        """
        if sn:
            sn.join()

        try:
            svc = self.query([('service', '=', service)], {'get': True})
            self.middleware.send_event('service.query', 'CHANGED', fields=svc)
            return svc['state'] == 'RUNNING'
        except IndexError:
            f = getattr(self, '_started_' + service, None)
            if callable(f):
                return f()[0]
            else:
                return self._started(service)[0]

    @accepts(
        Str('service'),
        Dict(
            'service-control',
            Bool('onetime'),
        ),
    )
    def stop(self, service, options=None):
        """ Stop the service specified by `service`.

        The helper will use method self._stop_[service]() to stop the service.
        If the method does not exist, it would fallback using service(8)."""
        if options is None:
            options = {
                'onetime': True,
            }
        self.middleware.call_hook('service.pre_stop', service)
        sn = self._started_notify("stop", service)
        self._simplecmd("stop", service, options)
        return self.started(service, sn)

    @accepts(
        Str('service'),
        Dict(
            'service-control',
            Bool('onetime'),
        ),
    )
    def restart(self, service, options=None):
        """
        Restart the service specified by `service`.

        The helper will use method self._restart_[service]() to restart the service.
        If the method does not exist, it would fallback using service(8)."""
        if options is None:
            options = {
                'onetime': True,
            }
        self.middleware.call_hook('service.pre_restart', service)
        sn = self._started_notify("restart", service)
        self._simplecmd("restart", service, options)
        return self.started(service, sn)

    @accepts(
        Str('service'),
        Dict(
            'service-control',
            Bool('onetime'),
        ),
    )
    def reload(self, service, options=None):
        """
        Reload the service specified by `service`.

        The helper will use method self._reload_[service]() to reload the service.
        If the method does not exist, the helper will try self.restart of the
        service instead."""
        if options is None:
            options = {
                'onetime': True,
            }
        self.middleware.call_hook('service.pre_reload', service)
        try:
            self._simplecmd("reload", service, options)
        except:
            self.restart(service, options)
        return self.started(service)

    def _get_status(self, service):
        f = getattr(self, '_started_' + service['service'], None)
        if callable(f):
            running, pids = f()
        else:
            running, pids = self._started(service['service'])

        if running:
            state = 'RUNNING'
        else:
            if service['enable']:
                state = 'CRASHED'
            else:
                state = 'STOPPED'

        service['state'] = state
        service['pids'] = pids
        return service

    def _simplecmd(self, action, what, options=None):
        self.logger.debug("Calling: %s(%s) ", action, what)
        f = getattr(self, '_' + action + '_' + what, None)
        if f is None:
            # Provide generic start/stop/restart verbs for rc.d scripts
            if what in self.SERVICE_DEFS:
                procname, pidfile = self.SERVICE_DEFS[what]
                if procname:
                    what = procname
            if action in ("start", "stop", "restart", "reload"):
                if action == 'restart':
                    self._system("/usr/sbin/service " + what + " forcestop ")
                self._system("/usr/sbin/service " + what + " " + action)
            else:
                raise ValueError("Internal error: Unknown command")
        else:
            f(**(options or {}))

    def _system(self, cmd):
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)
        proc.communicate()
        return proc.returncode

    def _service(self, service, verb, **options):
        onetime = options.get('onetime')
        force = options.get('force')
        quiet = options.get('quiet')

        # force comes before one which comes before quiet
        # they are mutually exclusive
        preverb = ''
        if force:
            preverb = 'force'
        elif onetime:
            preverb = 'one'
        elif quiet:
            preverb = 'quiet'

        return self._system('/usr/sbin/service {} {}{}'.format(
            service,
            preverb,
            verb,
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
            procname, pidfile = self.SERVICE_DEFS[what]
            sn = StartNotify(verb=verb, pidfile=pidfile)
            sn.start()
            return sn
        else:
            return None

    def _started(self, what, notify=None):
        """
        This is the second step::
        Wait for the StartNotify thread to finish and then check for the
        status of pidfile/procname using pgrep

        Returns:
            True whether the service is alive, False otherwise
        """

        if what in self.SERVICE_DEFS:
            procname, pidfile = self.SERVICE_DEFS[what]
            if notify:
                notify.join()

            if pidfile:
                pgrep = "/bin/pgrep -F {}{}".format(
                    pidfile,
                    ' ' + procname if procname else '',
                )
            else:
                pgrep = "/bin/pgrep {}".format(procname)
            proc = Popen(pgrep, shell=True, stdout=PIPE, stderr=PIPE, close_fds=True)
            data = proc.communicate()[0]

            if proc.returncode == 0:
                return True, [
                    int(i)
                    for i in data.strip().split('\n') if i.isdigit()
                ]
        return False, []

    def _start_webdav(self, **kwargs):
        self._service("ix-apache", "start", force=True, **kwargs)
        self._service("apache24", "start", **kwargs)

    def _stop_webdav(self, **kwargs):
        self._service("apache24", "stop", **kwargs)

    def _restart_webdav(self, **kwargs):
        self._service("apache24", "stop", force=True, **kwargs)
        self._service("ix-apache", "start", force=True, **kwargs)
        self._service("apache24", "restart", **kwargs)

    def _reload_webdav(self, **kwargs):
        self._service("ix-apache", "start", force=True, **kwargs)
        self._service("apache24", "reload", **kwargs)

    def _restart_django(self, **kwargs):
        self._service("django", "restart", **kwargs)

    def _start_webshell(self, **kwargs):
        self._system("/usr/local/bin/python /usr/local/www/freenasUI/tools/webshell.py")

    def _start_backup(self, **kwargs):
        self._system("/usr/local/bin/python /usr/local/www/freenasUI/tools/backup.py")

    def _restart_webshell(self, **kwargs):
        try:
            with open('/var/run/webshell.pid', 'r') as f:
                pid = f.read()
                os.kill(int(pid), signal.SIGHUP)
                time.sleep(0.2)
        except:
            pass
        self._system("ulimit -n 1024 && /usr/local/bin/python /usr/local/www/freenasUI/tools/webshell.py")

    def _restart_iscsitarget(self, **kwargs):
        self._service("ix-ctld", "start", force=True, **kwargs)
        self._service("ctld", "stop", force=True, **kwargs)
        self._service("ix-ctld", "start", quiet=True, **kwargs)
        self._service("ctld", "restart", **kwargs)

    def _start_iscsitarget(self, **kwargs):
        self._service("ix-ctld", "start", quiet=True, **kwargs)
        self._service("ctld", "start", **kwargs)

    def _stop_iscsitarget(self, **kwargs):
        self._service("ix-ctld", "stop", force=True, **kwargs)
        self._service("ctld", "stop", force=True, **kwargs)

    def _reload_iscsitarget(self, **kwargs):
        self._service("ix-ctld", "start", quiet=True, **kwargs)
        self._service("ctld", "reload", **kwargs)

    def _start_collectd(self, **kwargs):
        self._service("ix-collectd", "start", quiet=True, **kwargs)
        self._service("collectd", "restart", **kwargs)

    def _restart_collectd(self, **kwargs):
        self._service("collectd", "stop", **kwargs)
        self._service("ix-collectd", "start", quiet=True, **kwargs)
        self._service("collectd", "start", **kwargs)

    def _start_sysctl(self, **kwargs):
        self._service("sysctl", "start", **kwargs)
        self._service("ix-sysctl", "start", quiet=True, **kwargs)

    def _reload_sysctl(self, **kwargs):
        self._service("sysctl", "start", **kwargs)
        self._service("ix-sysctl", "reload", **kwargs)

    def _start_network(self, **kwargs):
        self.middleware.call('interfaces.sync')
        self.middleware.call('routes.sync')

    def _stop_jails(self, **kwargs):
        for jail in self.middleware.call('datastore.query', 'jails.jails'):
            self.middleware.call('notifier.warden', 'stop', [], {'jail': jail['jail_host']})

    def _start_jails(self, **kwargs):
        self._service("ix-warden", "start", **kwargs)
        for jail in self.middleware.call('datastore.query', 'jails.jails'):
            if jail['jail_autostart']:
                self.middleware.call('notifier.warden', 'start', [], {'jail': jail['jail_host']})
        self._service("ix-plugins", "start", **kwargs)
        self.reload("http", kwargs)

    def _restart_jails(self, **kwargs):
        self._stop_jails()
        self._start_jails()

    def _stop_pbid(self, **kwargs):
        self._service("pbid", "stop", **kwargs)

    def _start_pbid(self, **kwargs):
        self._service("pbid", "start", **kwargs)

    def _restart_pbid(self, **kwargs):
        self._service("pbid", "restart", **kwargs)

    def _reload_named(self, **kwargs):
        self._service("named", "reload", **kwargs)

    def _reload_hostname(self, **kwargs):
        self._system('/bin/hostname ""')
        self._service("ix-hostname", "start", quiet=True, **kwargs)
        self._service("hostname", "start", quiet=True, **kwargs)
        self._service("collectd", "stop", **kwargs)
        self._service("ix-collectd", "start", quiet=True, **kwargs)
        self._service("collectd", "start", **kwargs)

    def _reload_resolvconf(self, **kwargs):
        self._reload_hostname()
        self._service("ix-resolv", "start", quiet=True, **kwargs)

    def _reload_networkgeneral(self, **kwargs):
        self._reload_resolvconf()
        self._service("routing", "restart", **kwargs)

    def _reload_timeservices(self, **kwargs):
        self._service("ix-localtime", "start", quiet=True, **kwargs)
        self._service("ix-ntpd", "start", quiet=True, **kwargs)
        self._service("ntpd", "restart", **kwargs)
        os.environ['TZ'] = self.middleware.call('datastore.query', 'system.settings', [], {'order_by': ['-id'], 'get': True})['stg_timezone']
        time.tzset()

    def _restart_smartd(self, **kwargs):
        self._service("ix-smartd", "start", quiet=True, **kwargs)
        self._service("smartd", "stop", force=True, **kwargs)
        self._service("smartd", "restart", **kwargs)

    def _reload_ssh(self, **kwargs):
        self._service("ix-sshd", "start", quiet=True, **kwargs)
        self._service("ix_register", "reload", **kwargs)
        self._service("openssh", "reload", **kwargs)
        self._service("ix_sshd_save_keys", "start", quiet=True, **kwargs)

    def _start_ssh(self, **kwargs):
        self._service("ix-sshd", "start", quiet=True, **kwargs)
        self._service("ix_register", "reload", **kwargs)
        self._service("openssh", "start", **kwargs)
        self._service("ix_sshd_save_keys", "start", quiet=True, **kwargs)

    def _stop_ssh(self, **kwargs):
        self._service("openssh", "stop", force=True, **kwargs)
        self._service("ix_register", "reload", **kwargs)

    def _restart_ssh(self, **kwargs):
        self._service("ix-sshd", "start", quiet=True, **kwargs)
        self._service("openssh", "stop", force=True, **kwargs)
        self._service("ix_register", "reload", **kwargs)
        self._service("openssh", "restart", **kwargs)
        self._service("ix_sshd_save_keys", "start", quiet=True, **kwargs)

    def _reload_rsync(self, **kwargs):
        self._service("ix-rsyncd", "start", quiet=True, **kwargs)
        self._service("rsyncd", "restart", **kwargs)

    def _restart_rsync(self, **kwargs):
        self._stop_rsync()
        self._start_rsync()

    def _start_rsync(self, **kwargs):
        self._service("ix-rsyncd", "start", quiet=True, **kwargs)
        self._service("rsyncd", "start", **kwargs)

    def _stop_rsync(self, **kwargs):
        self._service("rsyncd", "stop", force=True, **kwargs)

    def _started_nis(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/NIS/ctl status"):
            res = True
        return res, []

    def _start_nis(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/NIS/ctl start"):
            res = True
        return res

    def _restart_nis(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/NIS/ctl restart"):
            res = True
        return res

    def _stop_nis(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/NIS/ctl stop"):
            res = True
        return res

    def _started_ldap(self, **kwargs):
        if (self._system('/usr/sbin/service ix-ldap status') != 0):
            return False, []
        return self.middleware.call('notifier.ldap_status'), []

    def _start_ldap(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/LDAP/ctl start"):
            res = True
        return res

    def _stop_ldap(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/LDAP/ctl stop"):
            res = True
        return res

    def _restart_ldap(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/LDAP/ctl restart"):
            res = True
        return res

    def _start_lldp(self, **kwargs):
        self._service("ladvd", "start", **kwargs)

    def _stop_lldp(self, **kwargs):
        self._service("ladvd", "stop", force=True, **kwargs)

    def _restart_lldp(self, **kwargs):
        self._service("ladvd", "stop", force=True, **kwargs)
        self._service("ladvd", "restart", **kwargs)

    def _clear_activedirectory_config(self):
        self._system("/bin/rm -f /etc/directoryservice/ActiveDirectory/config")

    def _started_nt4(self):
        res = False
        ret = self._system("service ix-nt4 status")
        if not ret:
            res = True
        return res, []

    def _start_nt4(self, **kwargs):
        res = False
        ret = self._system("/etc/directoryservice/NT4/ctl start")
        if not ret:
            res = True
        return res

    def _restart_nt4(self, **kwargs):
        res = False
        ret = self._system("/etc/directoryservice/NT4/ctl restart")
        if not ret:
            res = True
        return res

    def _stop_nt4(self, **kwargs):
        res = False
        self._system("/etc/directoryservice/NT4/ctl stop")
        return res

    def _started_activedirectory(self, **kwargs):
        for srv in ('kinit', 'activedirectory', ):
            if self._system('/usr/sbin/service ix-%s status' % (srv, )) != 0:
                return False, []
        return self.middleware.call('notifier.ad_status'), []

    def _start_activedirectory(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/ActiveDirectory/ctl start"):
            res = True
        return res

    def _stop_activedirectory(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/ActiveDirectory/ctl stop"):
            res = True
        return res

    def _restart_activedirectory(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/ActiveDirectory/ctl restart"):
            res = True
        return res

    def _started_domaincontroller(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/DomainController/ctl status"):
            res = True
        return res, []

    def _start_domaincontroller(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/DomainController/ctl start"):
            res = True
        return res

    def _stop_domaincontroller(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/DomainController/ctl stop"):
            res = True
        return res

    def _restart_domaincontroller(self, **kwargs):
        res = False
        if not self._system("/etc/directoryservice/DomainController/ctl restart"):
            res = True
        return res

    def _restart_syslogd(self, **kwargs):
        self._service("ix-syslogd", "start", quiet=True, **kwargs)
        self._system("/etc/local/rc.d/syslog-ng restart")

    def _start_syslogd(self, **kwargs):
        self._service("ix-syslogd", "start", quiet=True, **kwargs)
        self._system("/etc/local/rc.d/syslog-ng start")

    def _stop_syslogd(self, **kwargs):
        self._system("/etc/local/rc.d/syslog-ng stop")

    def _reload_syslogd(self, **kwargs):
        self._service("ix-syslogd", "start", quiet=True, **kwargs)
        self._system("/etc/local/rc.d/syslog-ng reload")

    def _start_tftp(self, **kwargs):
        self._service("ix-inetd", "start", quiet=True, **kwargs)
        self._service("inetd", "start", **kwargs)

    def _reload_tftp(self, **kwargs):
        self._service("ix-inetd", "start", quiet=True, **kwargs)
        self._service("inetd", "stop", force=True, **kwargs)
        self._service("inetd", "restart", **kwargs)

    def _restart_tftp(self, **kwargs):
        self._service("ix-inetd", "start", quiet=True, **kwargs)
        self._service("inetd", "stop", force=True, **kwargs)
        self._service("inetd", "restart", **kwargs)

    def _restart_cron(self, **kwargs):
        self._service("ix-crontab", "start", quiet=True, **kwargs)

    def _start_motd(self, **kwargs):
        self._service("ix-motd", "start", quiet=True, **kwargs)
        self._service("motd", "start", quiet=True, **kwargs)

    def _start_ttys(self, **kwargs):
        self._service("ix-ttys", "start", quiet=True, **kwargs)

    def _reload_ftp(self, **kwargs):
        self._service("ix-proftpd", "start", quiet=True, **kwargs)
        self._service("proftpd", "restart", **kwargs)

    def _restart_ftp(self, **kwargs):
        self._stop_ftp()
        self._start_ftp()

    def _start_ftp(self, **kwargs):
        self._service("ix-proftpd", "start", quiet=True, **kwargs)
        self._service("proftpd", "start", **kwargs)

    def _stop_ftp(self, **kwargs):
        self._service("proftpd", "stop", force=True, **kwargs)

    def _start_ups(self, **kwargs):
        self._service("ix-ups", "start", quiet=True, **kwargs)
        self._service("nut", "start", **kwargs)
        self._service("nut_upsmon", "start", **kwargs)
        self._service("nut_upslog", "start", **kwargs)

    def _stop_ups(self, **kwargs):
        self._service("nut_upslog", "stop", force=True, **kwargs)
        self._service("nut_upsmon", "stop", force=True, **kwargs)
        self._service("nut", "stop", force=True, **kwargs)

    def _restart_ups(self, **kwargs):
        self._service("ix-ups", "start", quiet=True, **kwargs)
        self._service("nut", "stop", force=True, **kwargs)
        self._service("nut_upsmon", "stop", force=True, **kwargs)
        self._service("nut_upslog", "stop", force=True, **kwargs)
        self._service("nut", "restart", **kwargs)
        self._service("nut_upsmon", "restart", **kwargs)
        self._service("nut_upslog", "restart", **kwargs)

    def _started_ups(self, **kwargs):
        mode = self.middleware.call('datastore.query', 'services.ups', [], {'order_by': ['-id'], 'get': True})['ups_mode']
        if mode == "master":
            svc = "ups"
        else:
            svc = "upsmon"
        return self._started(svc)

    def _start_afp(self, **kwargs):
        self._service("ix-afpd", "start", **kwargs)
        self._service("netatalk", "start", **kwargs)

    def _stop_afp(self, **kwargs):
        self._service("netatalk", "stop", force=True, **kwargs)
        # when netatalk stops if afpd or cnid_metad is stuck
        # they'll get left behind, which can cause issues
        # restarting netatalk.
        self._system("pkill -9 afpd")
        self._system("pkill -9 cnid_metad")

    def _restart_afp(self, **kwargs):
        self._stop_afp()
        self._start_afp()

    def _reload_afp(self, **kwargs):
        self._service("ix-afpd", "start", quiet=True, **kwargs)
        self._system("killall -1 netatalk")

    def _reload_nfs(self, **kwargs):
        self._service("ix-nfsd", "start", quiet=True, **kwargs)

    def _restart_nfs(self, **kwargs):
        self._stop_nfs(**kwargs)
        self._start_nfs(**kwargs)

    def _stop_nfs(self, **kwargs):
        self._service("lockd", "stop", force=True, **kwargs)
        self._service("statd", "stop", force=True, **kwargs)
        self._service("nfsd", "stop", force=True, **kwargs)
        self._service("mountd", "stop", force=True, **kwargs)
        self._service("nfsuserd", "stop", force=True, **kwargs)
        self._service("gssd", "stop", force=True, **kwargs)
        self._service("rpcbind", "stop", force=True, **kwargs)

    def _start_nfs(self, **kwargs):
        self._service("ix-nfsd", "start", quiet=True, **kwargs)
        self._service("rpcbind", "start", quiet=True, **kwargs)
        self._service("gssd", "start", quiet=True, **kwargs)
        self._service("nfsuserd", "start", quiet=True, **kwargs)
        self._service("mountd", "start", quiet=True, **kwargs)
        self._service("nfsd", "start", quiet=True, **kwargs)
        self._service("statd", "start", quiet=True, **kwargs)
        self._service("lockd", "start", quiet=True, **kwargs)

    def _force_stop_jail(self, **kwargs):
        self._service("jail", "stop", force=True, **kwargs)

    def _start_plugins(self, jail=None, plugin=None, **kwargs):
        if jail and plugin:
            self._system("/usr/sbin/service ix-plugins forcestart %s:%s" % (jail, plugin))
        else:
            self._service("ix-plugins", "start", force=True, **kwargs)

    def _stop_plugins(self, jail=None, plugin=None, **kwargs):
        if jail and plugin:
            self._system("/usr/sbin/service ix-plugins forcestop %s:%s" % (jail, plugin))
        else:
            self._service("ix-plugins", "stop", force=True, **kwargs)

    def _restart_plugins(self, jail=None, plugin=None):
        self._stop_plugins(jail=jail, plugin=plugin)
        self._start_plugins(jail=jail, plugin=plugin)

    def _started_plugins(self, jail=None, plugin=None, **kwargs):
        res = False
        if jail and plugin:
            if self._system("/usr/sbin/service ix-plugins status %s:%s" % (jail, plugin)) == 0:
                res = True
        else:
            if self._service("ix-plugins", "status", **kwargs) == 0:
                res = True
        return res, []

    def _restart_dynamicdns(self, **kwargs):
        self._service("ix-inadyn", "start", quiet=True, **kwargs)
        self._service("inadyn-mt", "stop", force=True, **kwargs)
        self._service("inadyn-mt", "restart", **kwargs)

    def _restart_system(self, **kwargs):
        self._system("/bin/sleep 3 && /sbin/shutdown -r now &")

    def _stop_system(self, **kwargs):
        self._system("/sbin/shutdown -p now")

    def _reload_cifs(self, **kwargs):
        self._service("ix-pre-samba", "start", quiet=True, **kwargs)
        self._service("samba_server", "reload", force=True, **kwargs)
        self._service("ix-post-samba", "start", quiet=True, **kwargs)
        self._service("mdnsd", "restart", **kwargs)
        # After mdns is restarted we need to reload netatalk to have it rereregister
        # with mdns. Ticket #7133
        self._service("netatalk", "reload", **kwargs)

    def _restart_cifs(self, **kwargs):
        self._service("ix-pre-samba", "start", quiet=True, **kwargs)
        self._service("samba_server", "stop", force=True, **kwargs)
        self._service("samba_server", "restart", quiet=True, **kwargs)
        self._service("ix-post-samba", "start", quiet=True, **kwargs)
        self._service("mdnsd", "restart", **kwargs)
        # After mdns is restarted we need to reload netatalk to have it rereregister
        # with mdns. Ticket #7133
        self._service("netatalk", "reload", **kwargs)

    def _start_cifs(self, **kwargs):
        self._service("ix-pre-samba", "start", quiet=True, **kwargs)
        self._service("samba_server", "start", quiet=True, **kwargs)
        self._service("ix-post-samba", "start", quiet=True, **kwargs)

    def _stop_cifs(self, **kwargs):
        self._service("samba_server", "stop", force=True, **kwargs)
        self._service("ix-post-samba", "start", quiet=True, **kwargs)

    def _start_snmp(self, **kwargs):
        self._service("ix-snmpd", "start", quiet=True, **kwargs)
        self._service("snmpd", "start", quiet=True, **kwargs)

    def _stop_snmp(self, **kwargs):
        self._service("snmpd", "stop", quiet=True, **kwargs)
        # The following is required in addition to just `snmpd`
        # to kill the `freenas-snmpd.py` daemon
        self._service("ix-snmpd", "stop", quiet=True, **kwargs)

    def _restart_snmp(self, **kwargs):
        self._service("ix-snmpd", "start", quiet=True, **kwargs)
        self._service("snmpd", "stop", force=True, **kwargs)
        self._service("snmpd", "start", quiet=True, **kwargs)

    def _restart_http(self, **kwargs):
        self._service("ix-nginx", "start", quiet=True, **kwargs)
        self._service("ix_register", "reload", **kwargs)
        self._service("nginx", "restart", **kwargs)

    def _reload_http(self, **kwargs):
        self._service("ix-nginx", "start", quiet=True, **kwargs)
        self._service("ix_register", "reload", **kwargs)
        self._service("nginx", "reload", **kwargs)

    def _reload_loader(self, **kwargs):
        self._service("ix-loader", "reload", **kwargs)

    def _start_loader(self, **kwargs):
        self._service("ix-loader", "start", quiet=True, **kwargs)

    def __saver_loaded(self):
        pipe = os.popen("kldstat|grep daemon_saver")
        out = pipe.read().strip('\n')
        pipe.close()
        return (len(out) > 0)

    def _start_saver(self, **kwargs):
        if not self.__saver_loaded():
            self._system("kldload daemon_saver")

    def _stop_saver(self, **kwargs):
        if self.__saver_loaded():
            self._system("kldunload daemon_saver")

    def _restart_saver(self, **kwargs):
        self._stop_saver()
        self._start_saver()

    def _reload_disk(self, **kwargs):
        self._service("ix-fstab", "start", quiet=True, **kwargs)
        self._service("ix-swap", "start", quiet=True, **kwargs)
        self._service("swap", "start", quiet=True, **kwargs)
        self._service("mountlate", "start", quiet=True, **kwargs)
        self.restart("collectd", kwargs)

    def _reload_user(self, **kwargs):
        self._service("ix-passwd", "start", quiet=True, **kwargs)
        self._service("ix-aliases", "start", quiet=True, **kwargs)
        self._service("ix-sudoers", "start", quiet=True, **kwargs)
        self.reload("cifs", kwargs)

    def _restart_system_datasets(self, **kwargs):
        systemdataset = self.middleware.call('notifier.system_dataset_create')
        if not systemdataset:
            return None
        systemdataset = self.middleware.call('datastore.query', 'system.systemdataset', [], {'get': True})
        if systemdataset['sys_syslog_usedataset']:
            self.restart("syslogd", kwargs)
        self.restart("cifs", kwargs)
        if systemdataset['sys_rrd_usedataset']:
            self.restart("collectd", kwargs)

    def enable_test_service_connection(self, frequency, retry, fqdn, service_port, service_name):
        """Enable service monitoring.

        Args:
                frequency (int): How often we will check the connection.
                retry (int): How many times we will try to restart the service.
                fqdn (str): The hostname and domainname where we will try to connect.
                service_port (int): The service port number.
                service_name (str): Same name used to start/stop/restart method.

        """
        self.logger.debug("[ServiceMonitoring] Add %s service, frequency: %d, retry: %d" % (service_name, frequency, retry))
        t = ServiceMonitor(frequency, retry, fqdn, service_port, service_name)
        t.createServiceThread()
        t.start()

    def disable_test_service_connection(self, frequency, retry, fqdn, service_port, service_name):
        """Disable service monitoring.

        XXX: This method will be simplified.

        Args:
                frequency (int): How often we will check the connection.
                retry (int): How many times we will try to restart the service.
                fqdn (str): The hostname and domainname where we will try to connect.
                service_port (int): The service port number.
                service_name (str): Same name used to start/stop/restart method.

        """
        self.logger.debug("[ServiceMonitoring] Remove %s service, frequency: %d, retry: %d" % (service_name, frequency, retry))
        t = ServiceMonitor(frequency, retry, fqdn, service_port, service_name)
        t.destroyServiceThread(service_name)
