import os
import signal
import threading
import time
from subprocess import PIPE

from middlewared.service import Service
from middlewared.utils import Popen


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
                    os.path.exists(self._pidfile)
                    and os.stat(self._pidfile).st_size > 0
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
        'ctld': ('ctld', '/var/run/ctld.pid'),
        'lldp': ('ladvd', '/var/run/ladvd.pid'),
        'ups': ('upsd', '/var/db/nut/upsd.pid'),
        'upsmon': ('upsmon', '/var/db/nut/upsmon.pid'),
        'smartd': ('smartd', '/var/run/smartd.pid'),
        'webshell': (None, '/var/run/webshell.pid'),
        'webdav': ('httpd', '/var/run/httpd.pid'),
        'backup': (None, '/var/run/backup.pid')
    }

    def query(self, filters=None, options=None):
        pass

    def _simplecmd(self, action, what):
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
        if f is not None:
            f()

    def _system(self, cmd):
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)
        proc.communicate()
        return proc.returncode

    def _started_notify(self, verb, what):
        """
        The check for started [or not] processes is currently done in 2 steps
        This is the first step which involves a thread StartNotify that watch for event
        before actually start/stop rc.d scripts

        Returns:
            StartNotify object if the service is known or None otherwise
        """

        # FIXME: Ugly workaround for one service and multiple backend
        if what == 'iscsitarget':
            what = 'ctld'

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

        # FIXME: Ugly workaround for one service and multiple backend
        if what == 'iscsitarget':
            what = 'ctld'

        if what in self.SERVICE_DEFS:
            procname, pidfile = self.SERVICE_DEFS[what]
            if notify:
                notify.join()

            if pidfile:
                procname = " " + procname if procname else ""
                retval = self._pipeopen("/bin/pgrep -F %s%s" % (pidfile, procname)).wait()
            else:
                retval = self._pipeopen("/bin/pgrep %s" % (procname,)).wait()

            if retval == 0:
                return True
            else:
                return False
        else:
            return False

    def start(self, what):
        """ Start the service specified by "what".

        The helper will use method self._start_[what]() to start the service.
        If the method does not exist, it would fallback using service(8)."""
        sn = self._started_notify("start", what)
        self._simplecmd("start", what)
        return self.started(what, sn)

    def started(self, what, sn=None):
        """ Test if service specified by "what" has been started. """
        f = getattr(self, '_started_' + what, None)
        if callable(f):
            return f()
        else:
            return self._started(what, sn)

    def stop(self, what):
        """ Stop the service specified by "what".

        The helper will use method self._stop_[what]() to stop the service.
        If the method does not exist, it would fallback using service(8)."""
        sn = self._started_notify("stop", what)
        self._simplecmd("stop", what)
        return self.started(what, sn)

    def restart(self, what):
        """ Restart the service specified by "what".

        The helper will use method self._restart_[what]() to restart the service.
        If the method does not exist, it would fallback using service(8)."""
        sn = self._started_notify("restart", what)
        self._simplecmd("restart", what)
        return self.started(what, sn)

    def reload(self, what):
        """ Reload the service specified by "what".

        The helper will use method self._reload_[what]() to reload the service.
        If the method does not exist, the helper will try self.restart of the
        service instead."""
        try:
            self._simplecmd("reload", what)
        except:
            self.restart(what)
        return self.started(what)

    def _start_webdav(self):
        self._system("/usr/sbin/service ix-apache onestart")
        self._system("/usr/sbin/service apache24 start")

    def _stop_webdav(self):
        self._system("/usr/sbin/service apache24 stop")

    def _restart_webdav(self):
        self._system("/usr/sbin/service apache24 forcestop")
        self._system("/usr/sbin/service ix-apache onestart")
        self._system("/usr/sbin/service apache24 restart")

    def _reload_webdav(self):
        self._system("/usr/sbin/service ix-apache onestart")
        self._system("/usr/sbin/service apache24 reload")

    def _restart_django(self):
        self._system("/usr/sbin/service django restart")

    def _start_webshell(self):
        self._system_nolog("/usr/local/bin/python /usr/local/www/freenasUI/tools/webshell.py")

    def _start_backup(self):
        self._system_nolog("/usr/local/bin/python /usr/local/www/freenasUI/tools/backup.py")

    def _restart_webshell(self):
        try:
            with open('/var/run/webshell.pid', 'r') as f:
                pid = f.read()
                os.kill(int(pid), signal.SIGHUP)
                time.sleep(0.2)
        except:
            pass
        self._system_nolog("ulimit -n 1024 && /usr/local/bin/python /usr/local/www/freenasUI/tools/webshell.py")

    def _restart_iscsitarget(self):
        self._system("/usr/sbin/service ix-ctld forcestart")
        self._system("/usr/sbin/service ctld forcestop")
        self._system("/usr/sbin/service ix-ctld quietstart")
        self._system("/usr/sbin/service ctld restart")

    def _start_iscsitarget(self):
        self._system("/usr/sbin/service ix-ctld quietstart")
        self._system("/usr/sbin/service ctld start")

    def _stop_iscsitarget(self):
        self._system("/usr/sbin/service ix-ctld forcestop")
        self._system("/usr/sbin/service ctld forcestop")

    def _reload_iscsitarget(self):
        self._system("/usr/sbin/service ix-ctld quietstart")
        self._system("/usr/sbin/service ctld reload")

    def _start_collectd(self):
        self._system("/usr/sbin/service ix-collectd quietstart")
        self._system("/usr/sbin/service collectd restart")

    def _restart_collectd(self):
        self._system("/usr/sbin/service collectd stop")
        self._system("/usr/sbin/service ix-collectd quietstart")
        self._system("/usr/sbin/service collectd start")

    def _start_sysctl(self):
        self._system("/usr/sbin/service sysctl start")
        self._system("/usr/sbin/service ix-sysctl quietstart")

    def _reload_sysctl(self):
        self._system("/usr/sbin/service sysctl start")
        self._system("/usr/sbin/service ix-sysctl reload")

    def _start_network(self):
        self.middleware.call('interfaces.sync')
        self.middleware.call('routes.sync')

    def _stop_jails(self):
        from freenasUI.jails.models import Jails
        for jail in Jails.objects.all():
            Warden().stop(jail=jail.jail_host)

    def _start_jails(self):
        self._system("/usr/sbin/service ix-warden start")
        from freenasUI.jails.models import Jails
        for jail in Jails.objects.all():
            if jail.jail_autostart:
                Warden().start(jail=jail.jail_host)
        self._system("/usr/sbin/service ix-plugins start")
        self.reload("http")

    def _restart_jails(self):
        self._stop_jails()
        self._start_jails()

    def _stop_pbid(self):
        self._system_nolog("/usr/sbin/service pbid stop")

    def _start_pbid(self):
        self._system_nolog("/usr/sbin/service pbid start")

    def _restart_pbid(self):
        self._system_nolog("/usr/sbin/service pbid restart")

    def _reload_named(self):
        self._system("/usr/sbin/service named reload")

    def _reload_hostname(self):
        self._system('/bin/hostname ""')
        self._system("/usr/sbin/service ix-hostname quietstart")
        self._system("/usr/sbin/service hostname quietstart")
        self._system("/usr/sbin/service collectd stop")
        self._system("/usr/sbin/service ix-collectd quietstart")
        self._system("/usr/sbin/service collectd start")

    def _reload_resolvconf(self):
        self._reload_hostname()
        self._system("/usr/sbin/service ix-resolv quietstart")

    def _reload_networkgeneral(self):
        self._reload_resolvconf()
        self._system("/usr/sbin/service routing restart")

    def _reload_timeservices(self):
        self._system("/usr/sbin/service ix-localtime quietstart")
        self._system("/usr/sbin/service ix-ntpd quietstart")
        self._system("/usr/sbin/service ntpd restart")
        c = self._open_db()
        c.execute("SELECT stg_timezone FROM system_settings ORDER BY -id LIMIT 1")
        os.environ['TZ'] = c.fetchone()[0]
        time.tzset()

    def _restart_smartd(self):
        self._system("/usr/sbin/service ix-smartd quietstart")
        self._system("/usr/sbin/service smartd forcestop")
        self._system("/usr/sbin/service smartd restart")

    def _reload_ssh(self):
        self._system("/usr/sbin/service ix-sshd quietstart")
        self._system("/usr/sbin/service ix_register reload")
        self._system("/usr/sbin/service openssh reload")
        self._system("/usr/sbin/service ix_sshd_save_keys quietstart")

    def _start_ssh(self):
        self._system("/usr/sbin/service ix-sshd quietstart")
        self._system("/usr/sbin/service ix_register reload")
        self._system("/usr/sbin/service openssh start")
        self._system("/usr/sbin/service ix_sshd_save_keys quietstart")

    def _stop_ssh(self):
        self._system("/usr/sbin/service openssh forcestop")
        self._system("/usr/sbin/service ix_register reload")

    def _restart_ssh(self):
        self._system("/usr/sbin/service ix-sshd quietstart")
        self._system("/usr/sbin/service openssh forcestop")
        self._system("/usr/sbin/service ix_register reload")
        self._system("/usr/sbin/service openssh restart")
        self._system("/usr/sbin/service ix_sshd_save_keys quietstart")

    def _reload_rsync(self):
        self._system("/usr/sbin/service ix-rsyncd quietstart")
        self._system("/usr/sbin/service rsyncd restart")

    def _restart_rsync(self):
        self._stop_rsync()
        self._start_rsync()

    def _start_rsync(self):
        self._system("/usr/sbin/service ix-rsyncd quietstart")
        self._system("/usr/sbin/service rsyncd start")

    def _stop_rsync(self):
        self._system("/usr/sbin/service rsyncd forcestop")

    def _started_nis(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/NIS/ctl status"):
            res = True
        return res

    def _start_nis(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/NIS/ctl start"):
            res = True
        return res

    def _restart_nis(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/NIS/ctl restart"):
            res = True
        return res

    def _stop_nis(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/NIS/ctl stop"):
            res = True
        return res

    def _started_ldap(self):
        from freenasUI.common.freenasldap import FreeNAS_LDAP, FLAGS_DBINIT

        if (self._system_nolog('/usr/sbin/service ix-ldap status') != 0):
            return False

        ret = False
        try:
            f = FreeNAS_LDAP(flags=FLAGS_DBINIT)
            f.open()
            if f.isOpen():
                ret = True
            f.close()
        except:
            pass

        return ret

    def _start_ldap(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/LDAP/ctl start"):
            res = True
        return res

    def _stop_ldap(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/LDAP/ctl stop"):
            res = True
        return res

    def _restart_ldap(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/LDAP/ctl restart"):
            res = True
        return res

    def _start_lldp(self):
        self._system("/usr/sbin/service ladvd start")

    def _stop_lldp(self):
        self._system("/usr/sbin/service ladvd forcestop")

    def _restart_lldp(self):
        self._system("/usr/sbin/service ladvd forcestop")
        self._system("/usr/sbin/service ladvd restart")

    def _clear_activedirectory_config(self):
        self._system("/bin/rm -f /etc/directoryservice/ActiveDirectory/config")

    def _started_nt4(self):
        res = False
        ret = self._system_nolog("service ix-nt4 status")
        if not ret:
            res = True
        return res

    def _start_nt4(self):
        res = False
        ret = self._system_nolog("/etc/directoryservice/NT4/ctl start")
        if not ret:
            res = True
        return res

    def _restart_nt4(self):
        res = False
        ret = self._system_nolog("/etc/directoryservice/NT4/ctl restart")
        if not ret:
            res = True
        return res

    def _stop_nt4(self):
        res = False
        self._system_nolog("/etc/directoryservice/NT4/ctl stop")
        return res

    def _started_activedirectory(self):
        ret = False
        from freenasUI.common.freenasldap import (FreeNAS_ActiveDirectory, FLAGS_DBINIT)

        for srv in ('kinit', 'activedirectory', ):
            if self._system_nolog('/usr/sbin/service ix-%s status' % (srv, )) != 0:
                return False

        try:
            ret = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT).connected()
        except:
            pass

        return ret

    def _start_activedirectory(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/ActiveDirectory/ctl start"):
            res = True
        return res

    def _stop_activedirectory(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/ActiveDirectory/ctl stop"):
            res = True
        return res

    def _restart_activedirectory(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/ActiveDirectory/ctl restart"):
            res = True
        return res

    def _started_domaincontroller(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/DomainController/ctl status"):
            res = True
        return res

    def _start_domaincontroller(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/DomainController/ctl start"):
            res = True
        return res

    def _stop_domaincontroller(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/DomainController/ctl stop"):
            res = True
        return res

    def _restart_domaincontroller(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/DomainController/ctl restart"):
            res = True
        return res

    def _restart_syslogd(self):
        self._system("/usr/sbin/service ix-syslogd quietstart")
        self._system("/etc/local/rc.d/syslog-ng restart")

    def _start_syslogd(self):
        self._system("/usr/sbin/service ix-syslogd quietstart")
        self._system("/etc/local/rc.d/syslog-ng start")

    def _stop_syslogd(self):
        self._system("/etc/local/rc.d/syslog-ng stop")

    def _reload_syslogd(self):
        self._system("/usr/sbin/service ix-syslogd quietstart")
        self._system("/etc/local/rc.d/syslog-ng reload")

    def _start_tftp(self):
        self._system("/usr/sbin/service ix-inetd quietstart")
        self._system("/usr/sbin/service inetd start")

    def _reload_tftp(self):
        self._system("/usr/sbin/service ix-inetd quietstart")
        self._system("/usr/sbin/service inetd forcestop")
        self._system("/usr/sbin/service inetd restart")

    def _restart_tftp(self):
        self._system("/usr/sbin/service ix-inetd quietstart")
        self._system("/usr/sbin/service inetd forcestop")
        self._system("/usr/sbin/service inetd restart")

    def _restart_cron(self):
        self._system("/usr/sbin/service ix-crontab quietstart")

    def _start_motd(self):
        self._system("/usr/sbin/service ix-motd quietstart")
        self._system("/usr/sbin/service motd quietstart")

    def _start_ttys(self):
        self._system("/usr/sbin/service ix-ttys quietstart")

    def _reload_ftp(self):
        self._system("/usr/sbin/service ix-proftpd quietstart")
        self._system("/usr/sbin/service proftpd restart")

    def _restart_ftp(self):
        self._stop_ftp()
        self._start_ftp()
        self._system("sleep 1")

    def _start_ftp(self):
        self._system("/usr/sbin/service ix-proftpd quietstart")
        self._system("/usr/sbin/service proftpd start")

    def _stop_ftp(self):
        self._system("/usr/sbin/service proftpd forcestop")

    def _start_ups(self):
        self._system("/usr/sbin/service ix-ups quietstart")
        self._system("/usr/sbin/service nut start")
        self._system("/usr/sbin/service nut_upsmon start")
        self._system("/usr/sbin/service nut_upslog start")

    def _stop_ups(self):
        self._system("/usr/sbin/service nut_upslog forcestop")
        self._system("/usr/sbin/service nut_upsmon forcestop")
        self._system("/usr/sbin/service nut forcestop")

    def _restart_ups(self):
        self._system("/usr/sbin/service ix-ups quietstart")
        self._system("/usr/sbin/service nut forcestop")
        self._system("/usr/sbin/service nut_upsmon forcestop")
        self._system("/usr/sbin/service nut_upslog forcestop")
        self._system("/usr/sbin/service nut restart")
        self._system("/usr/sbin/service nut_upsmon restart")
        self._system("/usr/sbin/service nut_upslog restart")

    def _started_ups(self):
        from freenasUI.services.models import UPS
        mode = UPS.objects.order_by('-id')[0].ups_mode
        if mode == "master":
            svc = "ups"
        else:
            svc = "upsmon"
        sn = self._started_notify("start", "upsmon")
        return self._started(svc, sn)

    def _load_afp(self):
        self._system("/usr/sbin/service ix-afpd quietstart")
        self._system("/usr/sbin/service netatalk quietstart")

    def _start_afp(self):
        self._system("/usr/sbin/service ix-afpd start")
        self._system("/usr/sbin/service netatalk start")

    def _stop_afp(self):
        self._system("/usr/sbin/service netatalk forcestop")
        # when netatalk stops if afpd or cnid_metad is stuck
        # they'll get left behind, which can cause issues
        # restarting netatalk.
        self._system("pkill -9 afpd")
        self._system("pkill -9 cnid_metad")

    def _restart_afp(self):
        self._stop_afp()
        self._start_afp()

    def _reload_afp(self):
        self._system("/usr/sbin/service ix-afpd quietstart")
        self._system("killall -1 netatalk")

    def _reload_nfs(self):
        self._system("/usr/sbin/service ix-nfsd quietstart")

    def _restart_nfs(self):
        self._stop_nfs()
        self._start_nfs()

    def _stop_nfs(self):
        self._system("/usr/sbin/service lockd forcestop")
        self._system("/usr/sbin/service statd forcestop")
        self._system("/usr/sbin/service nfsd forcestop")
        self._system("/usr/sbin/service mountd forcestop")
        self._system("/usr/sbin/service nfsuserd forcestop")
        self._system("/usr/sbin/service gssd forcestop")
        self._system("/usr/sbin/service rpcbind forcestop")

    def _start_nfs(self):
        self._system("/usr/sbin/service ix-nfsd quietstart")
        self._system("/usr/sbin/service rpcbind quietstart")
        self._system("/usr/sbin/service gssd quietstart")
        self._system("/usr/sbin/service nfsuserd quietstart")
        self._system("/usr/sbin/service mountd quietstart")
        self._system("/usr/sbin/service nfsd quietstart")
        self._system("/usr/sbin/service statd quietstart")
        self._system("/usr/sbin/service lockd quietstart")

    def _force_stop_jail(self):
        self._system("/usr/sbin/service jail forcestop")

    def _start_plugins(self, jail=None, plugin=None):
        if jail and plugin:
            self._system_nolog("/usr/sbin/service ix-plugins forcestart %s:%s" % (jail, plugin))
        else:
            self._system_nolog("/usr/sbin/service ix-plugins forcestart")

    def _stop_plugins(self, jail=None, plugin=None):
        if jail and plugin:
            self._system_nolog("/usr/sbin/service ix-plugins forcestop %s:%s" % (jail, plugin))
        else:
            self._system_nolog("/usr/sbin/service ix-plugins forcestop")

    def _restart_plugins(self, jail=None, plugin=None):
        self._stop_plugins(jail=jail, plugin=plugin)
        self._start_plugins(jail=jail, plugin=plugin)

    def _started_plugins(self, jail=None, plugin=None):
        res = False
        if jail and plugin:
            if self._system_nolog("/usr/sbin/service ix-plugins status %s:%s" % (jail, plugin)) == 0:
                res = True
        else:
            if self._system_nolog("/usr/sbin/service ix-plugins status") == 0:
                res = True
        return res

    def pluginjail_running(self, pjail=None):
        running = False

        try:
            wlist = Warden().cached_list()
            for wj in wlist:
                wj = WardenJail(**wj)
                if pjail and wj.host == pjail:
                    if (
                        wj.type == WARDEN_TYPE_PLUGINJAIL and
                        wj.status == WARDEN_STATUS_RUNNING
                    ):
                        running = True
                        break

                elif (
                    not pjail and wj.type == WARDEN_TYPE_PLUGINJAIL and
                    wj.status == WARDEN_STATUS_RUNNING
                ):
                    running = True
                    break
        except:
            pass

        return running

    def start_ataidle(self, what=None):
        if what is not None:
            self._system("/usr/sbin/service ix-ataidle quietstart %s" % what)
        else:
            self._system("/usr/sbin/service ix-ataidle quietstart")

    def start_ssl(self, what=None):
        if what is not None:
            self._system("/usr/sbin/service ix-ssl quietstart %s" % what)
        else:
            self._system("/usr/sbin/service ix-ssl quietstart")

    def _restart_dynamicdns(self):
        self._system("/usr/sbin/service ix-inadyn quietstart")
        self._system("/usr/sbin/service inadyn-mt forcestop")
        self._system("/usr/sbin/service inadyn-mt restart")

    def _restart_system(self):
        self._system("/bin/sleep 3 && /sbin/shutdown -r now &")

    def _stop_system(self):
        self._system("/sbin/shutdown -p now")

    def _reload_cifs(self):
        self._system("/usr/sbin/service ix-pre-samba quietstart")
        self._system("/usr/sbin/service samba_server forcereload")
        self._system("/usr/sbin/service ix-post-samba quietstart")
        self._system("/usr/sbin/service mdnsd restart")
        # After mdns is restarted we need to reload netatalk to have it rereregister
        # with mdns. Ticket #7133
        self._system("/usr/sbin/service netatalk reload")

    def _restart_cifs(self):
        self._system("/usr/sbin/service ix-pre-samba quietstart")
        self._system("/usr/sbin/service samba_server forcestop")
        self._system("/usr/sbin/service samba_server quietrestart")
        self._system("/usr/sbin/service ix-post-samba quietstart")
        self._system("/usr/sbin/service mdnsd restart")
        # After mdns is restarted we need to reload netatalk to have it rereregister
        # with mdns. Ticket #7133
        self._system("/usr/sbin/service netatalk reload")

    def _start_cifs(self):
        self._system("/usr/sbin/service ix-pre-samba quietstart")
        self._system("/usr/sbin/service samba_server quietstart")
        self._system("/usr/sbin/service ix-post-samba quietstart")

    def _stop_cifs(self):
        self._system("/usr/sbin/service samba_server forcestop")
        self._system("/usr/sbin/service ix-post-samba quietstart")

    def _start_snmp(self):
        self._system("/usr/sbin/service ix-snmpd quietstart")
        self._system("/usr/sbin/service snmpd quietstart")

    def _stop_snmp(self):
        self._system("/usr/sbin/service snmpd quietstop")
        # The following is required in addition to just `snmpd`
        # to kill the `freenas-snmpd.py` daemon
        self._system("/usr/sbin/service ix-snmpd quietstop")

    def _restart_snmp(self):
        self._system("/usr/sbin/service ix-snmpd quietstart")
        self._system("/usr/sbin/service snmpd forcestop")
        self._system("/usr/sbin/service snmpd quietstart")

    def _restart_http(self):
        self._system("/usr/sbin/service ix-nginx quietstart")
        self._system("/usr/sbin/service ix_register reload")
        self._system("/usr/sbin/service nginx restart")

    def _reload_http(self):
        self._system("/usr/sbin/service ix-nginx quietstart")
        self._system("/usr/sbin/service ix_register reload")
        self._system("/usr/sbin/service nginx reload")

    def _reload_loader(self):
        self._system("/usr/sbin/service ix-loader reload")

    def _start_loader(self):
        self._system("/usr/sbin/service ix-loader quietstart")

    def __saver_loaded(self):
        pipe = os.popen("kldstat|grep daemon_saver")
        out = pipe.read().strip('\n')
        pipe.close()
        return (len(out) > 0)

    def _start_saver(self):
        if not self.__saver_loaded():
            self._system("kldload daemon_saver")

    def _stop_saver(self):
        if self.__saver_loaded():
            self._system("kldunload daemon_saver")

    def _restart_saver(self):
        self._stop_saver()
        self._start_saver()
