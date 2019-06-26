import threading
import time
import enum
import os
import pybonjour
import select
import subprocess

from bsd.threading import set_thread_name

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
    ISCSI = ('_iscsi._tcp.', 3260)
    MIDDLEWARE = ('_middleware._tcp.', 6000)
    MIDDLEWARE_SSL = ('_middleware-ssl._tcp.', 443)
    NFS = ('_nfs._tcp.', 2049)
    SSH = ('_ssh._tcp.', 22)
    SFTP_SSH = ('_sftp-ssh._tcp.', 22)
    SMB = ('_smb._tcp.', 445)


class SrvToThread(enum.Enum):
    ADISK = 'mDNSServiceAdiskThread'
    AFP = 'mDNSServiceAFPThread'
    DEV_INFO = 'mDNSServiceDevInfoThread'
    FTP = 'mDNSServiceFTPThread'
    HTTP = 'mDNSServiceHTTPThread'
    HTTPS = 'mDNSServiceHTTPSThread'
    ISCSI = 'mDNSServiceISCSIThread'
    MIDDLEWARE = 'mDNSServiceMiddlewareThread'
    MIDDLEWARE_SSL = 'mDNSServiceMiddlewareSSLThread'
    NFS = 'mDNSServiceNFSThread'
    SSH = 'mDNSServiceSSHThread'
    SFTP_SSH = 'mDNSServiceSFTP_SSHThread'
    SMB = 'mDNSServiceSMBThread'

    def __str__(self):
        return self.value


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
        self.middleware = kwargs.get('middleware')
        self.logger = self.middleware.logger
        self.hostname = kwargs.get('hostname')
        self.service = kwargs.get('service')
        self.regtype = kwargs.get('regtype')
        self.is_running = kwargs.get('is_running', True)
        self.txtrecord = kwargs.get('txtrecord', '')
        self.port = kwargs.get('port')
        self.finished = threading.Event()

    def _register(self, name, regtype, port, txtrecord, is_running):
        """
        An instance of DNSServiceRef (sdRef) represents an active connection to mdnsd.

        DNSServiceRef class supports the context management protocol, sdRef
        is closed automatically when block is exited.
        """
        if not is_running:
            return

        sdRef = pybonjour.DNSServiceRegister(
            name=name,
            regtype=regtype,
            port=port,
            txtRecord=txtrecord,
            callBack=None
        )
        with sdRef:
            self.finished.wait()
            self.logger.trace(f'Unregistering {name} {regtype}')

    def register(self):
        if self.hostname and self.regtype and self.port:
            self._register(self.hostname, self.regtype, self.port, self.txtrecord, self.is_running)

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


class mDNSServiceSMBThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        if 'service' not in kwargs:
            kwargs['service'] = 'smb'
        super(mDNSServiceSMBThread, self).__init__(**kwargs)
        self.is_running = any(filter_list(
            kwargs.get('services'), [('service', '=', 'cifs'), ('state', '=', 'RUNNING')]
        ))

    def setup(self):
        self.regtype, self.port = ServiceType.SMB.value


class mDNSServiceFTPThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        if 'service' not in kwargs:
            kwargs['service'] = 'ftp'
        super(mDNSServiceFTPThread, self).__init__(**kwargs)
        self.is_running = any(filter_list(
            kwargs.get('services'), [('service', '=', 'ftp'), ('state', '=', 'RUNNING')]
        ))

    def setup(self):
        self.regtype, self.port = ServiceType.FTP.value


class mDNSServiceISCSIThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        if 'service' not in kwargs:
            kwargs['service'] = 'iscsi'
        super(mDNSServiceISCSIThread, self).__init__(**kwargs)
        self.is_running = any(filter_list(
            kwargs.get('services'), [('service', '=', 'iscsitarget'), ('state', '=', 'RUNNING')]
        ))

    def setup(self):
        self.regtype, self.port = ServiceType.ISCSI.value


class mDNSServiceAFPThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        if 'service' not in kwargs:
            kwargs['service'] = 'afp'
        super(mDNSServiceAFPThread, self).__init__(**kwargs)
        self.is_running = any(filter_list(
            kwargs.get('services'), [('service', '=', 'afp'), ('state', '=', 'RUNNING')]
        ))

    def setup(self):
        self.regtype, self.port = ServiceType.AFPOVERTCP.value


class mDNSServiceDevInfoThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        if 'service' not in kwargs:
            kwargs['service'] = 'dev_info'
        super(mDNSServiceDevInfoThread, self).__init__(**kwargs)

    def setup(self):
        self.regtype, self.port = ServiceType.DEV_INFO.value
        self.txtrecord = pybonjour.TXTRecord()
        self.txtrecord['model'] = DevType.RACKMAC


class mDNSServiceAdiskThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        if 'service' not in kwargs:
            kwargs['service'] = 'adisk'
        super(mDNSServiceAdiskThread, self).__init__(**kwargs)

    def setup(self):
        """
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
        afp_shares = self.middleware.call_sync('sharing.afp.query', [('timemachine', '=', True)])
        smb_shares = self.middleware.call_sync('sharing.smb.query', [('timemachine', '=', True)])
        afp = set([(x['name'], x['path']) for x in afp_shares])
        smb = set([(x['name'], x['path']) for x in smb_shares])
        mixed_shares = afp & smb
        afp.difference_update(mixed_shares)
        smb.difference_update(mixed_shares)
        if afp_shares or smb_shares:
            dkno = 0
            self.regtype, self.port = ServiceType.ADISK.value
            self.txtrecord = pybonjour.TXTRecord()
            self.txtrecord['sys'] = 'waMa=0,adVF=0x100'
            for i in mixed_shares:
                smb_advu = (list(filter(lambda x: i[0] == x['name'], smb_shares)))[0]['vuid']
                self.txtrecord[f'dk{dkno}'] = f'adVN={i[0]},adVF=0x83,adVU={smb_advu}'
                dkno += 1

            for i in smb:
                smb_advu = (list(filter(lambda x: i[0] == x['name'], smb_shares)))[0]['vuid']
                self.txtrecord[f'dk{dkno}'] = f'adVN={i[0]},adVF=0x82,adVU={smb_advu}'
                dkno += 1

            for i in afp:
                afp_advu = (list(filter(lambda x: i[0] == x['name'], afp_shares)))[0]['vuid']
                self.txtrecord[f'dk{dkno}'] = f'adVN={i[0]},adVF=0x81,adVU={afp_advu}'
                dkno += 1


class mDNSServiceSSHThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        if 'service' not in kwargs:
            kwargs['service'] = 'ssh'
        super(mDNSServiceSSHThread, self).__init__(**kwargs)
        self.is_running = any(filter_list(
            kwargs.get('services'), [('service', '=', 'ssh'), ('state', '=', 'RUNNING')]
        ))

    def setup(self):
        if self.is_running:
            self.regtype, self.port = ServiceType.SSH.value
            response = self.middleware.call_sync('datastore.query', 'services.ssh', [], {'get': True})
            if response:
                self.port = response['ssh_tcpport']


class mDNSServiceSFTP_SSHThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'sftp'
        super(mDNSServiceSFTP_SSHThread, self).__init__(**kwargs)
        self.is_running = any(filter_list(
            kwargs.get('services'), [('service', '=', 'ssh'), ('state', '=', 'RUNNING')]
        ))

    def setup(self):
        if self.is_running:
            self.regtype, self.port = ServiceType.SFTP_SSH.value
            response = self.middleware.call_sync('datastore.query', 'services.ssh', [], {'get': True})
            if response:
                self.port = response['ssh_tcpport']


class mDNSServiceHTTPThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'http'
        super(mDNSServiceHTTPThread, self).__init__(**kwargs)

    def setup(self):
        self.regtype, self.port = ServiceType.HTTP.value
        webui = self.middleware.call_sync('datastore.query', 'system.settings')
        self.port = int(webui[0]['stg_guiport'] or self.port)


class mDNSServiceHTTPSThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'https'
        super(mDNSServiceHTTPSThread, self).__init__(**kwargs)

    def setup(self):
        self.regtype, self.port = ServiceType.HTTPS.value
        webui = self.middleware.call_sync('datastore.query', 'system.settings')
        self.port = int(webui[0]['stg_guihttpsport'] or self.port)


class mDNSServiceMiddlewareThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'middleware'
        super(mDNSServiceMiddlewareThread, self).__init__(**kwargs)
        set_thread_name(f'mdns_{self.service}')

    def setup(self):
        self.regtype, self.port = ServiceType.MIDDLEWARE.value


class mDNSServiceMiddlewareSSLThread(mDNSServiceThread):
    def __init__(self, **kwargs):
        kwargs['service'] = 'middleware_ssl'
        super(mDNSServiceMiddlewareSSLThread, self).__init__(**kwargs)

    def setup(self):
        self.regtype, self.port = ServiceType.MIDDLEWARE_SSL.value
        webui = self.middleware.call_sync('datastore.query', 'system.settings')
        self.port = int(webui[0]['stg_guihttpsport'] or self.port)


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

        services = self.middleware.call_sync('service.query')
        hostname = self.middleware.call_sync('mdnsadvertise.get_hostname')
        if hostname is None:
            return

        mdns_advertise_services = [
            mDNSServiceAdiskThread,
            mDNSServiceAFPThread,
            mDNSServiceDevInfoThread,
            mDNSServiceFTPThread,
            mDNSServiceISCSIThread,
            mDNSServiceSSHThread,
            mDNSServiceSFTP_SSHThread,
            mDNSServiceSMBThread,
            mDNSServiceHTTPThread,
            mDNSServiceHTTPSThread,
            mDNSServiceMiddlewareThread,
            mDNSServiceMiddlewareSSLThread
        ]

        for service in mdns_advertise_services:
            if self.threads.get(SrvToThread(service.__name__).name.lower()):
                self.logger.debug('mDNS advertise thread is already started for service: %s', service.__name__)
                continue

            thread = service(middleware=self.middleware, hostname=hostname, services=services)
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
        mdns_advertise_services = [
            mDNSServiceAdiskThread,
            mDNSServiceAFPThread,
            mDNSServiceFTPThread,
            mDNSServiceISCSIThread,
            mDNSServiceSSHThread,
            mDNSServiceSFTP_SSHThread,
            mDNSServiceSMBThread,
            mDNSServiceHTTPThread,
            mDNSServiceHTTPSThread,
        ]
        services = self.middleware.call_sync('service.query')
        hostname = self.middleware.call_sync('mdnsadvertise.get_hostname')
        if hostname is None:
            return

        normalized_service_names = [SrvToThread[x].value for x in service_list]
        for srvthread in mdns_advertise_services:
            if srvthread.__name__ in normalized_service_names:
                service_name = SrvToThread(srvthread.__name__).name.lower()
                old_thread = self.threads.get(service_name)
                if old_thread is not None:
                    old_thread.cancel()
                    del self.threads[service_name]
                thread = srvthread(middleware=self.middleware, hostname=hostname, services=services)
                thread.setup()
                thread_name = thread.service
                self.threads[thread_name] = thread
                thread.start()


async def dns_post_sync(middleware):
    mDNSDaemonMonitor.instance.dns_sync.set()


def setup(middleware):
    mDNSDaemonMonitor(middleware)
    middleware.register_hook('dns.post_sync', dns_post_sync)
