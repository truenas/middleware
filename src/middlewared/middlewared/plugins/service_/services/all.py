from .cifs import CIFSService
from .ftp import FTPService
from .iscsitarget import ISCSITargetService
from .kuberouter import KubeRouterService
from .kubernetes import KubernetesService
from .mdns import MDNSService
from .netbios import NetBIOSService
from .netdata import NetdataService
from .nfs import NFSService
from .nscd import NSCDService
from .nslcd import NSSPamLdapdService
from .smartd import SMARTDService
from .snmp import SNMPService
from .ssh import SSHService
from .truecommand import TruecommandService
from .ups import UPSService
from .wsd import WSDService
from .keepalived import KeepalivedService
from .idmap import IdmapService
from .openipmi import OpenIpmiService

from .pseudo.directory_service import ActiveDirectoryService, LdapService
from .pseudo.libvirtd import LibvirtdService, LibvirtGuestService
from .pseudo.misc import (
    CronService,
    DSCacheService,
    KmipService,
    LoaderService,
    HostnameService,
    HttpService,
    NetworkService,
    NetworkGeneralService,
    NtpdService,
    OpenVmToolsService,
    PowerdService,
    RcService,
    ResolvConfService,
    RoutingService,
    SslService,
    SyslogdService,
    SystemService,
    TimeservicesService,
    UserService,
)

all_services = [
    CIFSService,
    DSCacheService,
    FTPService,
    ISCSITargetService,
    MDNSService,
    NetBIOSService,
    NFSService,
    NSCDService,
    NSSPamLdapdService,
    SMARTDService,
    SNMPService,
    SSHService,
    UPSService,
    WSDService,
    ActiveDirectoryService,
    LdapService,
    NetdataService,
    IdmapService,
    OpenIpmiService,
    KeepalivedService,
    KubernetesService,
    KubeRouterService,
    OpenVmToolsService,
    LibvirtdService,
    LibvirtGuestService,
    CronService,
    KmipService,
    LoaderService,
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
    SyslogdService,
    SystemService,
    TimeservicesService,
    TruecommandService,
    UserService,
]
