from .cifs import CIFSService
from .docker import DockerService
from .ftp import FTPService
from .incus import IncusService
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
    SslService,
    SyslogdService,
    TimeservicesService,
    UserService,
)

all_services = [
    CIFSService,
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
    IncusService,
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
    SslService,
    SyslogdService,
    TimeservicesService,
    TruecommandService,
    TruesearchService,
    UserService,
]
