import os
import enum
import xml.etree.ElementTree as xml
import socket

from middlewared.utils import filter_list, osc

GENERATE_SERVICE_FILTER = ['OR', [('state', '=', 'RUNNING'), ('enable', '=', True)]]
AVAHI_SERVICE_PATH = '/etc/avahi/services'
if osc.IS_FREEBSD:
    AVAHI_SERVICE_PATH = f'/usr/local{AVAHI_SERVICE_PATH}'


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


class AvahiConst(enum.Enum):
    AVAHI_IF_UNSPEC = -1


class mDNSService(object):
    def __init__(self, **kwargs):
        super(mDNSService, self).__init__()
        self.service_info = kwargs.get('service_info')
        self.middleware = kwargs.get('middleware')
        self.logger = self.middleware.logger
        self.hostname = kwargs.get('hostname')
        self.service = None
        self.regtype = None
        self.port = None

    def _is_system_service(self):
        if self.service in ['DEV_INFO', 'HTTP', 'HTTPS', 'MIDDLEWARE', 'MIDDLEWARE_SSL']:
            return True
        else:
            return False

    def _is_running(self):
        if self._is_system_service():
            return True

        if self.service == 'ADISK':
            smb_is_running = any(filter_list(
                self.service_info, [('service', '=', 'cifs'), GENERATE_SERVICE_FILTER]
            ))
            if smb_is_running:
                return True
            else:
                return False

        if self.service == 'SMB':
            return any(filter_list(self.service_info, [('service', '=', 'cifs'), GENERATE_SERVICE_FILTER]))

        if self.service == 'SFTP_SSH':
            return any(filter_list(self.service_info, [('service', '=', 'ssh'), GENERATE_SERVICE_FILTER]))

        return any(filter_list(self.service_info, [('service', '=', self.service.lower()), GENERATE_SERVICE_FILTER]))

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
            return ({}, self._get_interfaceindex())

        txtrecord = {}
        if self.service == 'DEV_INFO':
            txtrecord['model'] = DevType.RACKMAC
            return (txtrecord, [AvahiConst.AVAHI_IF_UNSPEC])

        if self.service == 'ADISK':
            iindex = [AvahiConst.AVAHI_IF_UNSPEC]
            smb_is_running = any(filter_list(
                self.service_info, [('service', '=', 'cifs'), GENERATE_SERVICE_FILTER]
            ))

            if smb_is_running:
                smb_shares = self.middleware.call_sync('sharing.smb.query', [('timemachine', '=', True)])
            else:
                smb_shares = []

            smb = set([(x['name'], x['path']) for x in smb_shares])
            if len(smb) == 0:
                return (None, [AvahiConst.AVAHI_IF_UNSPEC])

            if smb_shares:
                iindex = []
                dkno = 0
                txtrecord['sys'] = 'waMa=0,adVF=0x100'
                for i in smb:
                    smb_advu = (list(filter(lambda x: i[0] == x['name'], smb_shares)))[0]['vuid']
                    txtrecord[f'dk{dkno}'] = f'adVN={i[0]},adVF=0x82,adVU={smb_advu}'
                    dkno += 1

                if smb:
                    smb_iindex = self._get_interfaceindex('SMB')
                    if smb_iindex != [AvahiConst.AVAHI_IF_UNSPEC]:
                        iindex.extend(smb_iindex)

                if not iindex:
                    iindex = [AvahiConst.AVAHI_IF_UNSPEC]

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
        AvahiConst.AVAHI_IF_UNSPEC (0) will register on all available interfaces.
        This function will return AvahiConst.AVAHI_IF_UNSPEC if the service is
        not configured to bind on a particular interface. Otherwise it will return
        a list of interfaces on which to register mDNS.
        """
        iindex = []
        bind_ip = []
        if service is None:
            service = self.service
        if service in ['NFS', 'SMB']:
            bind_ip = self.middleware.call_sync(f'{service.lower()}.config')['bindip']

        if service in ['HTTP', 'HTTPS']:
            ui_address = self.middleware.call_sync('system.general.config')['ui_address']
            if ui_address[0] != "0.0.0.0":
                bind_ip = ui_address

        if service in ['SSH', 'SFTP_SSH']:
            for iface in self.middleware.call_sync('ssh.config')['bindiface']:
                try:
                    iindex.append(socket.if_nametoindex(iface))
                except OSError:
                    self.logger.debug('Failed to determine interface index for [%s], service [%s]',
                                      iface, service, exc_info=True)

            return iindex if iindex else [AvahiConst.AVAHI_IF_UNSPEC]

        if bind_ip is None:
            return [AvahiConst.AVAHI_IF_UNSPEC]

        for ip in bind_ip:
            for intobj in self.middleware.call_sync('interface.query'):
                if any(filter(lambda x: ip in x['address'], intobj['aliases'])):
                    try:
                        iindex.append(socket.if_nametoindex(intobj['name']))
                    except OSError:
                        self.logger.debug('Failed to determine interface index for [%s], service [%s]',
                                          iface, service, exc_info=True)

                    break

        return iindex if iindex else [AvahiConst.AVAHI_IF_UNSPEC]

    def generate_services(self):
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
            # write header of service file
            config_file = f"{AVAHI_SERVICE_PATH}/{srv.name}.service"
            with open(config_file, "w") as f:
                f.write('<?xml version="1.0" standalone="no"?>')
                f.write('<!DOCTYPE service-group SYSTEM "avahi-service.dtd">')

            root = xml.Element("service-group")
            srv_name = xml.Element('name')
            srv_name.text = self.hostname
            root.append(srv_name)
            for i in interfaceIndex:
                service = xml.Element('service')
                root.append(service)
                regtype = xml.SubElement(service, 'type')
                regtype.text = self.regtype
                srvport = xml.SubElement(service, 'port')
                srvport.text = str(port)
                if i != AvahiConst.AVAHI_IF_UNSPEC:
                    iindex = xml.SubElement(service, 'interface')
                    iindex.text = str(i)

                for t, v in txtrecord.items():
                    txt = xml.SubElement(service, 'txt-record')
                    txt.text = f'{t}={v}'
            xml_service_config = xml.ElementTree(root)
            with open(config_file, "a") as f:
                xml_service_config.write(f, 'unicode')
                f.write('\n')


def remove_service_configs(middleware):
    for file in os.listdir(AVAHI_SERVICE_PATH):
        servicefile = f'{AVAHI_SERVICE_PATH}/{file}'
        if os.path.isfile(servicefile):
            try:
                os.unlink(servicefile)
            except Exception as e:
                middleware.logger.debug('Filed to delete [%s]: (%s)', servicefile, e)


def get_hostname(middleware):
    """
    Return virtual hostname if the server is HA and this is the active controller.
    Return None if this is the standby controller.
    In all other cases return the hostname_local.
    This is to ensure that the correct hostname is used for mdns advertisements.
    """
    ngc = middleware.call_sync('network.configuration.config')
    if 'hostname_virtual' in ngc:
        failover_status = middleware.call_sync('failover.status')
        if failover_status == 'MASTER':
            return ngc['hostname_virtual']
        elif failover_status == 'BACKUP':
            return None
        else:
            return ngc['hostname_local']

    else:
        return ngc['hostname_local']


def generate_avahi_config(middleware):
    service_info = middleware.call_sync('service.query')
    hostname = get_hostname(middleware)
    if hostname is None:
        return

    remove_service_configs(middleware)
    announce = middleware.call_sync('network.configuration.config')['service_announcement']
    if not announce['mdns']:
        return
    mdns_configs = mDNSService(
        middleware=middleware,
        hostname=hostname,
        service_info=service_info
    )
    mdns_configs.generate_services()


def render(service, middleware):
    generate_avahi_config(middleware)
