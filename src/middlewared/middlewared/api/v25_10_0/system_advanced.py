from typing import Literal

from pydantic import Field, PositiveInt, NonNegativeInt, Secret

from middlewared.api.base import (
    BaseModel, NotRequired, ForUpdateMetaclass, Excluded, excluded_field, NonEmptyString, EmptyDict
)


__all__ = [
    "SystemAdvancedEntry", "SystemAdvancedGetGpuPciChoicesArgs", "SystemAdvancedGetGpuPciChoicesResult",
    "SystemAdvancedLoginBannerArgs", "SystemAdvancedLoginBannerResult", "SystemAdvancedSedGlobalPasswordArgs",
    "SystemAdvancedSedGlobalPasswordResult", "SystemAdvancedSedGlobalPasswordIsSetArgs",
    "SystemAdvancedSedGlobalPasswordIsSetResult", "SystemAdvancedSerialPortChoicesArgs",
    "SystemAdvancedSerialPortChoicesResult", "SystemAdvancedSyslogCertificateAuthorityChoicesArgs",
    "SystemAdvancedSyslogCertificateAuthorityChoicesResult", "SystemAdvancedSyslogCertificateChoicesArgs",
    "SystemAdvancedSyslogCertificateChoicesResult", "SystemAdvancedUpdateArgs", "SystemAdvancedUpdateResult",
    "SystemAdvancedUpdateGpuPciIdsArgs", "SystemAdvancedUpdateGpuPciIdsResult",
]


class SystemAdvancedEntry(BaseModel):
    id: int
    """Placeholder identifier.  Not used as there is only one."""
    advancedmode: bool
    """Enable advanced mode to show additional configuration options in the web interface."""
    autotune: bool
    """Execute autotune script which attempts to optimize the system based on the installed hardware."""
    kdump_enabled: bool
    """Enable kernel crash dumps for debugging system crashes."""
    boot_scrub: PositiveInt
    """Number of days between automatic boot pool scrubs."""
    consolemenu: bool
    """Enable console menu. Default to standard login in the console if disabled."""
    consolemsg: bool
    """Deprecated: Please use `consolemsg` attribute in the `system.general` plugin instead."""
    debugkernel: bool
    """Enable debug kernel for additional logging and debugging capabilities."""
    fqdn_syslog: bool
    """Include the full domain name in syslog messages."""
    motd: str
    """Message of the day displayed after login."""
    login_banner: str = Field(max_length=4096)
    """Banner message displayed before login prompt."""
    powerdaemon: bool
    """Enable the power management daemon for automatic power management."""
    serialconsole: bool
    """Enable serial console access."""
    serialport: str
    """Serial port device for console access."""
    anonstats_token: str
    """Token used for anonymous statistics reporting."""
    serialspeed: Literal['9600', '19200', '38400', '57600', '115200']
    """Baud rate for serial console communication."""
    overprovision: NonNegativeInt | None
    """Percentage of SSD overprovisioning to reserve for wear leveling."""
    traceback: bool
    """Enable generation and saving of tracebacks for debugging."""
    uploadcrash: bool
    """Automatically upload crash reports to iXsystems for analysis."""
    anonstats: bool
    """Enable anonymous usage statistics reporting to help improve TrueNAS."""
    sed_user: Literal['USER', 'MASTER']
    """SED (Self-Encrypting Drive) user type for drive encryption."""
    sysloglevel: Literal['F_EMERG', 'F_ALERT', 'F_CRIT', 'F_ERR', 'F_WARNING', 'F_NOTICE', 'F_INFO', 'F_DEBUG']
    """Minimum log level for syslog messages. F_EMERG is most critical, F_DEBUG is least critical."""
    syslogserver: str = NotRequired
    """Remote syslog server DNS hostname or IP address. Nonstandard port numbers can be used by adding \
    a colon and the port number to the hostname, like mysyslogserver:1928.  Setting this field enables \
    the remote syslog function."""
    syslog_transport: Literal['UDP', 'TCP', 'TLS']
    """Transport Protocol for the remote system log server connection. \
    Choosing Transport Layer Security (TLS) also requires selecting a preconfigured system Certificate."""
    syslog_tls_certificate: int | None
    """Certificate ID for TLS-encrypted syslog connections or `null` for no certificate."""
    syslog_audit: bool = NotRequired
    """The remote syslog server will also receive audit messages."""
    isolated_gpu_pci_ids: list[str]
    """List of GPU PCI IDs to isolate from the host system for VM passthrough."""
    kernel_extra_options: str
    """Additional kernel boot parameters to pass to the Linux kernel."""


class SystemAdvancedUpdate(SystemAdvancedEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    anonstats_token: Excluded = excluded_field()
    isolated_gpu_pci_ids: Excluded = excluded_field()
    sed_passwd: Secret[str]
    """Password for SED (Self-Encrypting Drive) global unlock."""


class SystemAdvancedGetGpuPciChoicesArgs(BaseModel):
    pass


class SystemAdvancedGetGpuPciChoicesResult(BaseModel):
    result: dict
    """Available GPU PCI devices that can be isolated for VM passthrough."""


class SystemAdvancedLoginBannerArgs(BaseModel):
    pass


class SystemAdvancedLoginBannerResult(BaseModel):
    result: str
    """Current login banner message."""


class SystemAdvancedSedGlobalPasswordArgs(BaseModel):
    pass


class SystemAdvancedSedGlobalPasswordResult(BaseModel):
    result: Secret[str]
    """Current SED global password (masked for security)."""


class SystemAdvancedSedGlobalPasswordIsSetArgs(BaseModel):
    pass


class SystemAdvancedSedGlobalPasswordIsSetResult(BaseModel):
    result: bool
    """Whether a SED global password has been configured."""


class SystemAdvancedSerialPortChoicesArgs(BaseModel):
    pass


class SystemAdvancedSerialPortChoicesResult(BaseModel):
    result: dict[str, str]
    """Available serial ports for console configuration."""


class SystemAdvancedSyslogCertificateAuthorityChoicesArgs(BaseModel):
    pass


class SystemAdvancedSyslogCertificateAuthorityChoicesResult(BaseModel):
    result: EmptyDict
    """Available certificate authorities for syslog TLS (currently empty)."""


class SystemAdvancedSyslogCertificateChoicesArgs(BaseModel):
    pass


class SystemAdvancedSyslogCertificateChoicesResult(BaseModel):
    result: dict[int, NonEmptyString]
    """IDs of certificates mapped to their names."""


class SystemAdvancedUpdateArgs(BaseModel):
    data: SystemAdvancedUpdate
    """Updated system advanced configuration data."""


class SystemAdvancedUpdateResult(BaseModel):
    result: SystemAdvancedEntry
    """The updated system advanced configuration."""


class SystemAdvancedUpdateGpuPciIdsArgs(BaseModel):
    data: list[str]
    """List of GPU PCI IDs to isolate for VM passthrough."""


class SystemAdvancedUpdateGpuPciIdsResult(BaseModel):
    result: None
