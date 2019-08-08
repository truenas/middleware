import threading
import time
import enum
import os
import pybonjour
import select
import socket
import subprocess

from bsd.threading import set_thread_name
from pybonjour import kDNSServiceInterfaceIndexAny

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
        self.service_info = kwargs.get('service_info')
        self.middleware = kwargs.get('middleware')
        self.logger = self.middleware.logger
        self.hostname = kwargs.get('hostname')
        self.service = None
        self.regtype = None
        self.port = None
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
            if not self.middleware.call_sync('smb.config')['zeroconf']:
                return False

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
        sys=adVF=0x100 -- this is required when _adisk._tcp is present on device. When it is
        set, the MacOS client will send a NetShareEnumAll IOCTL and shares will be visible.
        Otherwise, Finder will only see the Time Machine share. In the absence of _adisk._tcp
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
            return ('', self._get_interfaceindex())

        txtrecord = pybonjour.TXTRecord()
        if self.service == 'DEV_INFO':
            txtrecord['model'] = DevType.RACKMAC
            return (txtrecord, [kDNSServiceInterfaceIndexAny])

        if self.service == 'ADISK':
            iindex = [kDNSServiceInterfaceIndexAny]
            afp_shares = self.middleware.call_sync('sharing.afp.query', [('timemachine', '=', True)])
            smb_shares = self.middleware.call_sync('sharing.smb.query', [('timemachine', '=', True)])
            afp = set([(x['name'], x['path']) for x in afp_shares])
            smb = set([(x['name'], x['path']) for x in smb_shares])
            if len(afp | smb) == 0:
                return (None, [kDNSServiceInterfaceIndexAny])

            mixed_shares = afp & smb
            afp.difference_update(mixed_shares)
            smb.difference_update(mixed_shares)
            if afp_shares or smb_shares:
                iindex = []
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

                if smb:
                    smb_iindex = self._get_interfaceindex('SMB')
                    if smb_iindex != [kDNSServiceInterfaceIndexAny]:
                        iindex.extend(smb_iindex)
                if afp:
                    afp_iindex = self._get_interfaceindex('AFP')
                    if afp_iindex != [kDNSServiceInterfaceIndexAny]:
                        iindex.extend(afp_iindex)

                if not iindex:
                    iindex = [kDNSServiceInterfaceIndexAny]

            return (txtrecord, iindex)

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

    def _get_interfaceindex(self, service=None):
        """
        interfaceIndex specifies the interface on which to register the sdRef.
        kDNSServiceInterfaceIndexAny (0) will register on all available interfaces.
        This function will return kDNSServiceInterfaceIndexAny if the service is
        not configured to bind on a particular interface. Otherwise it will return
        a list of interfaces on which to register mDNS.
        """
        iindex = []
        bind_ip = []
        if service is None:
            service = self.service
        if service in ['AFP', 'NFS', 'SMB']:
            bind_ip = self.middleware.call_sync(f'{service.lower()}.config')['bindip']

        if service in ['HTTP', 'HTTPS']:
            ui_address = self.middleware.call_sync('system.general.config')['ui_address']
            if ui_address[0] != "0.0.0.0":
                bind_ip = ui_address

        if service in ['SSH', 'SFTP_SSH']:
            for iface in self.middleware.call_sync('ssh.config')['bindiface']:
                iindex.append(socket.if_nametoindex(iface))

            return iindex if iindex else [kDNSServiceInterfaceIndexAny]

        if bind_ip is None:
            return [kDNSServiceInterfaceIndexAny]

        for ip in bind_ip:
            for intobj in self.middleware.call_sync('interface.query'):
                if any(filter(lambda x: ip in x['address'], intobj['aliases'])):
                    iindex.append(socket.if_nametoindex(intobj['name']))
                    break

        return iindex if iindex else [kDNSServiceInterfaceIndexAny]

    def register(self):
        """
        An instance of DNSServiceRef (sdRef) represents an active connection to mdnsd.
        """
        mDNSServices = {}
        for srv in ServiceType:
            mDNSServices.update({srv.name: {}})
            self.service = srv.name
            self.regtype, self.port = ServiceType[self.service].value
            if not self._is_running():
                continue

            txtrecord, interfaceIndex = self._generate_txtRecord()
            if txtrecord is None:
                continue

            port = self._get_port()

            self.logger.trace(
                'Registering mDNS service host: %s,  regtype: %s, port: %s, interface: %s, TXTRecord: %s',
                self.hostname, self.regtype, port, interfaceIndex, txtrecord
            )
            for i in interfaceIndex:
                mDNSServices[srv.name].update({i: {
                    'sdRef': None,
                    'interfaceIndex': i,
                    'regtype': self.regtype,
                    'port': port,
                    'txtrecord': txtrecord,
                    'name': self.hostname
                }})

                mDNSServices[srv.name][i]['sdRef'] = pybonjour.DNSServiceRegister(
                    name=self.hostname,
                    regtype=self.regtype,
                    interfaceIndex=i,
                    port=port,
                    txtRecord=txtrecord,
                    callBack=None
                )

        self.finished.wait()
        for srv in mDNSServices.keys():
            for i in mDNSServices[srv].keys():
                self.logger.trace('Unregistering %s %s.',
                                  mDNSServices[srv][i]['name'], mDNSServices[srv][i]['regtype'])
                mDNSServices[srv][i]['sdRef'].close()

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
        if 'hostname_virtual' in ngc:
            failover_status = await self.middleware.call('failover.status')
            if failover_status == 'MASTER':
                return ngc['hostname_virtual']
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

        if self.threads.get('mDNSThread'):
            self.logger.debug('mDNS advertise thread is already started.')
            return

        thread = mDNSServiceThread(
            middleware=self.middleware,
            hostname=hostname,
            service_info=service_info
        )
        thread.setup()
        thread_name = 'mDNSThread'
        self.threads[thread_name] = thread
        thread.start()

        with self.lock:
            self.initialized = True

    @private
    def stop(self):
        thread = self.threads.get('mDNSThread')
        if thread is None:
            return

        thread.cancel()
        del self.threads['mDNSThread']
        self.threads = {}

        with self.lock:
            self.initialized = False

    @private
    def restart(self):
        self.stop()
        self.start()


async def dns_post_sync(middleware):
    mDNSDaemonMonitor.instance.dns_sync.set()


def setup(middleware):
    mDNSDaemonMonitor(middleware)
    middleware.register_hook('dns.post_sync', dns_post_sync)
