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


class SyslogServer(BaseModel):
    host: str = Field(
        description=(
            "Remote syslog server DNS hostname or IP address.\n"
            "\n"
            "Nonstandard port numbers can be used by appending a colon and port number to the hostname, like "
            "mysyslogserver:1928.\n"
            "\n"
            "Port 514 is used by default for TCP and UDP transports as per RFC3164; port 6514 is used by default for "
            "TLS transport as per RFC5425."
        ),
    )
    transport: Literal['UDP', 'TCP', 'TLS'] = Field(
        default='UDP',
        description="Transport Protocol for the remote system log server connection.",
    )
    tls_certificate: int | None = Field(
        default=None,
        description=(
            "Applies only if `transport` is \"TLS\".\n"
            "\n"
            "ID of the local certificate to send for mutual TLS (mTLS) connections. `null` indicates one-way TLS in "
            "which only the server identified by `host` will need to provide a certificate."
        ),
    )


class SystemAdvancedEntry(BaseModel):
    id: int = Field(description="Placeholder identifier.  Not used as there is only one.")
    advancedmode: bool = Field(
        description="Enable advanced mode to show additional configuration options in the web interface.",
    )
    autotune: bool = Field(
        description="Execute autotune script which attempts to optimize the system based on the installed hardware.",
    )
    kdump_enabled: bool = Field(description="Enable kernel crash dumps for debugging system crashes.")
    boot_scrub: PositiveInt = Field(description="Number of days between automatic boot pool scrubs.")
    consolemenu: bool = Field(description="Enable console menu. Default to standard login in the console if disabled.")
    consolemsg: bool = Field(
        description="Deprecated: Please use `consolemsg` attribute in the `system.general` plugin instead.",
    )
    debugkernel: bool = Field(description="Enable debug kernel for additional logging and debugging capabilities.")
    fqdn_syslog: bool = Field(description="Include the full domain name in syslog messages.")
    motd: str = Field(description="Message of the day displayed after login.")
    login_banner: str = Field(max_length=4096, description="Banner message displayed before login prompt.")
    powerdaemon: bool = Field(description="Enable the power management daemon for automatic power management.")
    serialconsole: bool = Field(description="Enable serial console access.")
    serialport: str = Field(description="Serial port device for console access.")
    anonstats_token: str = Field(description="Token used for anonymous statistics reporting.")
    serialspeed: Literal['9600', '19200', '38400', '57600', '115200'] = Field(
        description="Baud rate for serial console communication.",
    )
    overprovision: NonNegativeInt | None = Field(
        description="Percentage of SSD overprovisioning to reserve for wear leveling.",
    )
    traceback: bool = Field(description="Enable generation and saving of tracebacks for debugging.")
    uploadcrash: bool = Field(description="Automatically upload crash reports to iXsystems for analysis.")
    anonstats: bool = Field(description="Enable anonymous usage statistics reporting to help improve TrueNAS.")
    sed_user: Literal['USER', 'MASTER'] = Field(
        description="SED (Self-Encrypting Drive) user type for drive encryption.",
    )
    sysloglevel: Literal['F_EMERG', 'F_ALERT', 'F_CRIT', 'F_ERR', 'F_WARNING', 'F_NOTICE', 'F_INFO', 'F_DEBUG'] = Field(
        description="Minimum log level for syslog messages. F_EMERG is most critical, F_DEBUG is least critical.",
    )
    syslogservers: list[SyslogServer] = Field(
        default=[],
        max_length=2,
        description="Configurations for up to two remote syslog servers.",
    )
    syslog_audit: bool = Field(
        default=NotRequired,
        description="The remote syslog server(s) will also receive audit messages.",
    )
    isolated_gpu_pci_ids: list[str] = Field(
        description="List of GPU PCI IDs to isolate from the host system for VM passthrough.",
    )
    kernel_extra_options: str = Field(description="Additional kernel boot parameters to pass to the Linux kernel.")


class SystemAdvancedUpdate(SystemAdvancedEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    anonstats_token: Excluded = excluded_field()
    syslogservers: list[SyslogServer] = Field(
        default=[],
        max_length=2,
        description=(
            "Configurations for up to two remote syslog servers.\n"
            "\n"
            "**If provided, will overwrite the entire array in the existing entry.**"
        ),
    )
    isolated_gpu_pci_ids: Excluded = excluded_field()
    sed_passwd: Secret[str] = Field(description="Password for SED (Self-Encrypting Drive) global unlock.")


class SystemAdvancedGetGpuPciChoicesArgs(BaseModel):
    pass


class SystemAdvancedGetGpuPciChoicesResult(BaseModel):
    result: dict = Field(description="Available GPU PCI devices that can be isolated for VM passthrough.")


class SystemAdvancedLoginBannerArgs(BaseModel):
    pass


class SystemAdvancedLoginBannerResult(BaseModel):
    result: str = Field(description="Current login banner message.")


class SystemAdvancedSedGlobalPasswordArgs(BaseModel):
    pass


class SystemAdvancedSedGlobalPasswordResult(BaseModel):
    result: Secret[str] = Field(description="Current SED global password (masked for security).")


class SystemAdvancedSedGlobalPasswordIsSetArgs(BaseModel):
    pass


class SystemAdvancedSedGlobalPasswordIsSetResult(BaseModel):
    result: bool = Field(description="Whether a SED global password has been configured.")


class SystemAdvancedSerialPortChoicesArgs(BaseModel):
    pass


class SystemAdvancedSerialPortChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Available serial ports for console configuration.")


class SystemAdvancedSyslogCertificateAuthorityChoicesArgs(BaseModel):
    pass


class SystemAdvancedSyslogCertificateAuthorityChoicesResult(BaseModel):
    result: EmptyDict = Field(description="Available certificate authorities for syslog TLS (currently empty).")


class SystemAdvancedSyslogCertificateChoicesArgs(BaseModel):
    pass


class SystemAdvancedSyslogCertificateChoicesResult(BaseModel):
    result: dict[int, NonEmptyString] = Field(description="IDs of certificates mapped to their names.")


class SystemAdvancedUpdateArgs(BaseModel):
    data: SystemAdvancedUpdate = Field(description="Updated system advanced configuration data.")


class SystemAdvancedUpdateResult(BaseModel):
    result: SystemAdvancedEntry = Field(description="The updated system advanced configuration.")


class SystemAdvancedUpdateGpuPciIdsArgs(BaseModel):
    data: list[str] = Field(description="List of GPU PCI IDs to isolate for VM passthrough.")


class SystemAdvancedUpdateGpuPciIdsResult(BaseModel):
    result: None
