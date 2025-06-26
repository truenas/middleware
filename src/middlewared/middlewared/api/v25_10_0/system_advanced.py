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
    advancedmode: bool
    autotune: bool
    """Execute autotune script which attempts to optimize the system based on the installed hardware."""
    kdump_enabled: bool
    boot_scrub: PositiveInt
    consolemenu: bool
    """Enable console menu. Default to standard login in the console if disabled."""
    consolemsg: bool
    """Deprecated: Please use `consolemsg` attribute in the `system.general` plugin instead."""
    debugkernel: bool
    fqdn_syslog: bool
    motd: str
    login_banner: str = Field(max_length=4096)
    powerdaemon: bool
    serialconsole: bool
    serialport: str
    anonstats_token: str
    serialspeed: Literal['9600', '19200', '38400', '57600', '115200']
    overprovision: NonNegativeInt | None
    traceback: bool
    uploadcrash: bool
    anonstats: bool
    sed_user: Literal['USER', 'MASTER']
    sysloglevel: Literal['F_EMERG', 'F_ALERT', 'F_CRIT', 'F_ERR', 'F_WARNING', 'F_NOTICE', 'F_INFO', 'F_DEBUG']
    syslogserver: str = NotRequired
    """When defined, logs of `sysloglevel` or higher are sent."""
    syslog_transport: Literal['UDP', 'TCP', 'TLS']
    syslog_tls_certificate: int | None
    syslog_audit: bool = NotRequired
    """The remote syslog server will also receive audit messages."""
    isolated_gpu_pci_ids: list[str]
    kernel_extra_options: str


class SystemAdvancedUpdate(SystemAdvancedEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    anonstats_token: Excluded = excluded_field()
    isolated_gpu_pci_ids: Excluded = excluded_field()
    sed_passwd: Secret[str]


class SystemAdvancedGetGpuPciChoicesArgs(BaseModel):
    pass


class SystemAdvancedGetGpuPciChoicesResult(BaseModel):
    result: dict


class SystemAdvancedLoginBannerArgs(BaseModel):
    pass


class SystemAdvancedLoginBannerResult(BaseModel):
    result: str


class SystemAdvancedSedGlobalPasswordArgs(BaseModel):
    pass


class SystemAdvancedSedGlobalPasswordResult(BaseModel):
    result: Secret[str]


class SystemAdvancedSedGlobalPasswordIsSetArgs(BaseModel):
    pass


class SystemAdvancedSedGlobalPasswordIsSetResult(BaseModel):
    result: bool


class SystemAdvancedSerialPortChoicesArgs(BaseModel):
    pass


class SystemAdvancedSerialPortChoicesResult(BaseModel):
    result: dict[str, str]


class SystemAdvancedSyslogCertificateAuthorityChoicesArgs(BaseModel):
    pass


class SystemAdvancedSyslogCertificateAuthorityChoicesResult(BaseModel):
    result: EmptyDict


class SystemAdvancedSyslogCertificateChoicesArgs(BaseModel):
    pass


class SystemAdvancedSyslogCertificateChoicesResult(BaseModel):
    result: dict[int, NonEmptyString]
    """IDs of certificates mapped to their names."""


class SystemAdvancedUpdateArgs(BaseModel):
    data: SystemAdvancedUpdate


class SystemAdvancedUpdateResult(BaseModel):
    result: SystemAdvancedEntry


class SystemAdvancedUpdateGpuPciIdsArgs(BaseModel):
    data: list[str]


class SystemAdvancedUpdateGpuPciIdsResult(BaseModel):
    result: None
