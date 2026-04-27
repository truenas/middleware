from .cifs import CIFSService
from .ctdb import CTDBService
from .discovery import DiscoveryService
from .docker import DockerService
from .ftp import FTPService
from .iscsitarget import ISCSITargetService
from .netdata import NetdataService
from .nfs import NFSService
from .nscd import NSCDService
from .snmp import SNMPService
from .ssh import SSHService
from .sssd import SSSDService
from .truecommand import TruecommandService
from .truesearch import TruesearchService
from .ups import UPSService
from .keepalived import KeepalivedService
from .idmap import IdmapService
from .openipmi import OpenIpmiService
from .webshare import WebShareService

from .pseudo.libvirtd import LibvirtdService, LibvirtGuestService
from .pseudo.misc import (
    CronService,
    KmipService,
    LoaderService,
    HostnameService,
    HttpService,
    NetworkService,
    NetworkGeneralService,
    NfsMountdService,
    NtpdService,
    NVMETargetService,
    NVMfService,
    OpenVmToolsService,
    PowerdService,
    RcService,
    ResolvConfService,
    RoutingService,
    RpcGssService,
    SslService,
    SyslogdService,
    TimeservicesService,
    UserService,
)

all_services = [
    CIFSService,
    CTDBService,
    DiscoveryService,
    DockerService,
    FTPService,
    ISCSITargetService,
    NFSService,
    NSCDService,
    SNMPService,
    SSHService,
    SSSDService,
    UPSService,
    NetdataService,
    IdmapService,
    OpenIpmiService,
    KeepalivedService,
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
    NfsMountdService,
    NtpdService,
    NVMETargetService,
    NVMfService,
    PowerdService,
    RcService,
    ResolvConfService,
    RoutingService,
    RpcGssService,
    SslService,
    SyslogdService,
    TimeservicesService,
    TruecommandService,
    TruesearchService,
    UserService,
    WebShareService,
]
