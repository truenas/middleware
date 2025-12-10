from .cifs import CIFSService
from .ctdb import CTDBService
from .docker import DockerService
from .ftp import FTPService
from .iscsitarget import ISCSITargetService
from .mdns import MDNSService
from .netbios import NetBIOSService
from .netdata import NetdataService
from .nfs import NFSService
from .nscd import NSCDService
from .snmp import SNMPService
from .ssh import SSHService
from .sssd import SSSDService
from .truecommand import TruecommandService
from .truesearch import TruesearchService
from .ups import UPSService
from .wsd import WSDService
from .keepalived import KeepalivedService
from .idmap import IdmapService
from .openipmi import OpenIpmiService
from .ransomwared import RansomwaredService
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
    DockerService,
    FTPService,
    ISCSITargetService,
    MDNSService,
    NetBIOSService,
    NFSService,
    NSCDService,
    SNMPService,
    SSHService,
    SSSDService,
    UPSService,
    WSDService,
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
    RansomwaredService,
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
