from .afp import AFPService
from .cifs import CIFSService
from .dynamicdns import DynamicDNSService
from .ftp import FTPService
from .iscsitarget import ISCSITargetService
from .kubernetes_linux import KubernetesService
from .lldp import LLDPService
from .mdns import MDNSService
from .netbios import NetBIOSService
from .nfs import NFSService
from .openvpn_client import OpenVPNClientService
from .openvpn_server import OpenVPNServerService
from .rsync import RsyncService
from .s3 import S3Service
from .smartd import SMARTDService
from .snmp import SNMPService
from .ssh import SSHService
from .tftp import TFTPService
from .truecommand import TruecommandService
from .ups import UPSService
from .webdav import WebDAVService
from .wsd import WSDService
from .keepalived import KeepalivedService

from .pseudo.ad import ActiveDirectoryService, LdapService, NisService
from .pseudo.collectd import CollectDService, RRDCacheDService
from .pseudo.docker_linux import DockerService
from .pseudo.kuberouter_linux import KubeRouterService
from .pseudo.libvirtd import LibvirtdService
from .pseudo.misc import (
    CronService,
    DiskService,
    FailoverService,
    KmipService,
    LoaderService,
    MOTDService,
    HostnameService,
    HttpService,
    NetworkService,
    NetworkGeneralService,
    NtpdService,
    PowerdService,
    RcService,
    ResolvConfService,
    RoutingService,
    SslService,
    SysconsService,
    SysctlService,
    SyslogdService,
    SystemService,
    SystemDatasetsService,
    TimeservicesService,
    TtysService,
    UserService,
)

all_services = [
    AFPService,
    CIFSService,
    DockerService,
    DynamicDNSService,
    FTPService,
    ISCSITargetService,
    LLDPService,
    MDNSService,
    NetBIOSService,
    NFSService,
    OpenVPNClientService,
    OpenVPNServerService,
    RsyncService,
    S3Service,
    SMARTDService,
    SNMPService,
    SSHService,
    TFTPService,
    UPSService,
    WebDAVService,
    WSDService,
    KeepalivedService,
    ActiveDirectoryService,
    KubeRouterService,
    LdapService,
    NisService,
    CollectDService,
    RRDCacheDService,
    KubernetesService,
    LibvirtdService,
    CronService,
    DiskService,
    FailoverService,
    KmipService,
    LoaderService,
    MOTDService,
    HostnameService,
    HttpService,
    NetworkService,
    NetworkGeneralService,
    NtpdService,
    PowerdService,
    RcService,
    ResolvConfService,
    RoutingService,
    SslService,
    SysconsService,
    SysctlService,
    SyslogdService,
    SystemService,
    SystemDatasetsService,
    TimeservicesService,
    TruecommandService,
    TtysService,
    UserService,
]
