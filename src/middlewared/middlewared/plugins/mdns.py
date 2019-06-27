import threading
import time
import enum
import os
import pybonjour
import select
import subprocess

from bsd.threading import set_thread_name

from middlewared.service_exception import CallError
from middlewared.service import Service, private
from middlewared.utils import filter_list


class DevType(enum.Enum):
    AIRPORT = 'AirPort'
    APPLETV = 'AppleTv1,1'
    MACPRO = 'MacPro'
    RACKMAC = 'RackMac'
    TIMECAPSULE = 'TimeCapsule6,106'
    XSERVE = 'Xserve'

    def __str__(self):
        return self.value


class ServiceType(enum.Enum):
    ADISK = ('_adisk._tcp.', 9)
    AFPOVERTCP = ('_afpovertcp._tcp.', 548)
    DEV_INFO = ('_device-info._tcp.', 9)
    FTP = ('_ftp._tcp.', 21)
    HTTP = ('_http._tcp.', 80)
    HTTPS = ('_https._tcp.', 443)
    ISCSITARGET = ('_iscsi._tcp.', 3260)
    MIDDLEWARE = ('_middleware._tcp.', 6000)
    MIDDLEWARE_SSL = ('_middleware-ssl._tcp.', 443)
    NFS = ('_nfs._tcp.', 2049)
    SSH = ('_ssh._tcp.', 22)
    SFTP_SSH = ('_sftp-ssh._tcp.', 22)
    SMB = ('_smb._tcp.', 445)
    TFTP = ('_tftp._udp.', 69)
    WEBDAV = ('_webdav._tcp.', 8080)


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


class mDNSServiceThread(threading.Thread):
    def __init__(self, **kwargs):
        super(mDNSServiceThread, self).__init__()
        self.setDaemon(True)
        self.service = kwargs.get('service')
        self.service_info = kwargs.get('service_info')
        self.middleware = kwargs.get('middleware')
        self.logger = self.middleware.logger
        self.hostname = kwargs.get('hostname')
        self.service = kwargs.get('service')
        self.regtype, self.port = ServiceType[self.service].value
        self.finished = threading.Event()

    def _is_system_service(self):
        if self.service in ['DEV_INFO', 'HTTP', 'HTTPS', 'MIDDLEWARE', 'MIDDLEWARE_SSL']:
            return True
        else:
            return False

    def _is_running(self):
        if self._is_system_service():
            return True

        if self.service == 'ADISK':
            afp_is_running = any(filter_list(
                self.service_info, [('service', '=', 'afp'), ('state', '=', 'RUNNING')]
            ))
            smb_is_running = any(filter_list(
                self.service_info, [('service', '=', 'cifs'), ('state', '=', 'RUNNING')]
            ))
            if afp_is_running or smb_is_running:
                return True
            else:
                return False
        if self.service == 'SMB':
            return any(filter_list(self.service_info, [('service', '=', 'cifs'), ('state', '=', 'RUNNING')]))

        return any(filter_list(self.service_info, [('service', '=', self.service.lower()), ('state', '=', 'RUNNING')]))

    def _generate_txtRecord(self):
        """
        Device Info:
        -------------------------
        The TXTRecord string here determines the icon that will be displayed in Finder on MacOS
        clients. Default is to use MacRack which will display the icon for a rackmounted server.


        Time Machine (adisk):
        -------------------------
        sys=adVF=0x100 -- this is required when ._adisk._tcp is present on device. When it is
        set, the MacOS client will send a NetShareEnumAll IOCTL and shares will be visible.
        Otherwise, Finder will only see the Time Machine share. In the absence of ._adisk._tcp
        MacOS will _always_ send NetShareEnumAll IOCTL.

        waMa=0 -- MacOS server uses waMa=0, while embedded devices have it set to their Mac Address.
        Speculation in Samba-Technical indicates that this stands for "Wireless ADisk Mac Address".

        adVU -- ADisk Volume UUID.

        dk(n)=adVF=
        0xa1, 0x81 - AFP support
        0xa2, 0x82 - SMB support
        0xa3, 0x83 - AFP and SMB support

        adVN -- AirDisk Volume Name. We set this to the share name.
        network analysis indicates that current MacOS Time Machine shares set the port for adisk to 311.
        """
        if self.service not in ['ADISK', 'DEV_INFO']:
            return ''

        txtrecord = pybonjour.TXTRecord()
        if self.service == 'DEV_INFO':
            txtrecord['model'] = DevType.RACKMAC
            return txtrecord

        if self.service == 'ADISK':
            afp_shares = self.middleware.call_sync('sharing.afp.query', [('timemachine', '=', True)])
            smb_shares = self.middleware.call_sync('sharing.smb.query', [('timemachine', '=', True)])
            afp = set([(x['name'], x['path']) for x in afp_shares])
            smb = set([(x['name'], x['path']) for x in smb_shares])
            if len(afp | smb) == 0:
                return None

            mixed_shares = afp & smb
            afp.difference_update(mixed_shares)
            smb.difference_update(mixed_shares)
            if afp_shares or smb_shares:
                dkno = 0
                txtrecord['sys'] = 'waMa=0,adVF=0x100'
                for i in mixed_shares:
                    smb_advu = (list(filter(lambda x: i[0] == x['name'], smb_shares)))[0]['vuid']
                    txtrecord[f'dk{dkno}'] = f'adVN={i[0]},adVF=0x83,adVU={smb_advu}'
                    dkno += 1

                for i in smb:
                    smb_advu = (list(filter(lambda x: i[0] == x['name'], smb_shares)))[0]['vuid']
                    txtrecord[f'dk{dkno}'] = f'adVN={i[0]},adVF=0x82,adVU={smb_advu}'
                    dkno += 1

                for i in afp:
                    afp_advu = (list(filter(lambda x: i[0] == x['name'], afp_shares)))[0]['vuid']
                    txtrecord[f'dk{dkno}'] = f'adVN={i[0]},adVF=0x81,adVU={afp_advu}'
                    dkno += 1

            return txtrecord

    def _get_port(self):
        if self.service in ['FTP', 'TFPT']:
            return (self.middleware.call_sync(f'{self.service.lower()}.config'))['port']

        if self.service in ['SSH', 'SFTP_SSH']:
            return (self.middleware.call_sync('ssh.config'))['tcpport']

        if self.service == 'HTTP':
            return (self.middleware.call_sync('system.general.config'))['ui_port']

        if self.service in ['HTTPS', 'MIDDLEWARE_SSL']:
            return (self.middleware.call_sync('system.general.config'))['ui_httpsport']

        if self.service == 'WEBDAV':
            return (self.middleware.call_sync('webdav.config'))['tcpport']

        return self.port

    def register(self):
        """
        An instance of DNSServiceRef (sdRef) represents an active connection to mdnsd.

        DNSServiceRef class supports the context management protocol, sdRef
        is closed automatically when block is exited.
        """
        if not self._is_running():
            return

        txtrecord = self._generate_txtRecord()
        if txtrecord is None:
            return

        port = self._get_port()

        self.logger.debug(
            'Registering mDNS service hostnamename: %s,  regtype: %s, port: %s, TXTRecord: %s',
            self.hostname, self.regtype, port, txtrecord
        )

        sdRef = pybonjour.DNSServiceRegister(
            name=self.hostname,
            regtype=self.regtype,
            port=port,
            txtRecord=txtrecord,
            callBack=None
        )
        with sdRef:
            self.finished.wait()
            self.logger.trace('Unregistering %s %s.', self.hostname, self.regtype)

    def run(self):
        set_thread_name(f'mdns_svc_{self.service}')
        try:
            self.register()
        except pybonjour.BonjourError:
            self.logger.debug("ServiceThread: failed to register '%s', is mdnsd running?", self.service)

    def setup(self):
        pass

    def cancel(self):
        self.finished.set()


class mDNSAdvertiseService(Service):
    def __init__(self, *args, **kwargs):
        super(mDNSAdvertiseService, self).__init__(*args, **kwargs)
        self.threads = {}
        self.initialized = False
        self.lock = threading.Lock()

    @private
    async def get_hostname(self):
        """
        Return virtual hostname if the server is HA and this is the active controller.
        Return None if this is the passive controller.
        In all other cases return the hostname_local.
        This is to ensure that the correct hostname is used for mdns advertisements.
        """
        ngc = await self.middleware.call('network.configuration.config')
        if not await self.middleware.call('system.is_freenas') and await self.middleware.call('notfier.failover_licensed'):
            failover_status = await self.middleware.call('notifier.failover_status')
            if failover_status == 'MASTER':
                return ngc['virtual_hostname']
            elif failover_status == 'BACKUP':
                return None
        else:
            return ngc['hostname_local']

    @private
    def start(self):
        with self.lock:
            if self.initialized:
                return

        if not mDNSDaemonMonitor.instance.mdnsd_running.wait(timeout=10):
            return

        service_info = self.middleware.call_sync('service.query')
        hostname = self.middleware.call_sync('mdnsadvertise.get_hostname')
        if hostname is None:
            return

        for srv in ServiceType:
            if self.threads.get(srv.name):
                self.logger.debug('mDNS advertise thread is already started for service: %s', srv.name)
                continue

            thread = mDNSServiceThread(middleware=self.middleware, hostname=hostname, service=srv.name, service_info=service_info)
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

    @private
    def reload(self, service_list):
        """
        Re-register a list of services. Available services are in ServiceType class.
        """
        service_info = self.middleware.call_sync('service.query')
        hostname = self.middleware.call_sync('mdnsadvertise.get_hostname')
        if hostname is None:
            return

        for service in service_list:
            try:
                srv = ServiceType[service]
            except KeyError:
                raise CallError(f'{service} is not valid service.')

            old_thread = self.threads.get(srv.name)
            if old_thread is not None:
                old_thread.cancel()
                del self.threads[srv.name]

            thread = mDNSServiceThread(middleware=self.middleware, hostname=hostname, service=srv.name, service_info=service_info)
            thread.setup()
            thread_name = thread.service
            self.threads[thread_name] = thread
            thread.start()


async def dns_post_sync(middleware):
    mDNSDaemonMonitor.instance.dns_sync.set()


def setup(middleware):
    mDNSDaemonMonitor(middleware)
    middleware.register_hook('dns.post_sync', dns_post_sync)
