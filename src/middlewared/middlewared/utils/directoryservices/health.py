import enum

from .constants import DSStatus, DSType
from threading import Lock

MAX_RECOVER_ATTEMPTS = 5
HEALTH_EVENT_NAME = 'directoryservices.status'


class KRB5HealthCheckFailReason(enum.IntEnum):
    KRB5_NO_CONFIG = enum.auto()
    KRB5_CONFIG_PERM = enum.auto()
    KRB5_NO_CCACHE = enum.auto()
    KRB5_CCACHE_PERM = enum.auto()
    KRB5_NO_KEYTAB = enum.auto()
    KRB5_KEYTAB_PERM = enum.auto()
    KRB5_TKT_EXPIRED = enum.auto()


class IPAHealthCheckFailReason(enum.IntEnum):
    IPA_NO_CONFIG = enum.auto()
    IPA_CONFIG_PERM = enum.auto()
    IPA_NO_CACERT = enum.auto()
    IPA_CACERT_PERM = enum.auto()
    NTP_EXCESSIVE_SLEW = enum.auto()
    LDAP_BIND_FAILED = enum.auto()
    SSSD_STOPPED = enum.auto()


class ADHealthCheckFailReason(enum.IntEnum):
    AD_SECRET_ENTRY_MISSING = enum.auto()
    AD_SECRET_FILE_MISSING = enum.auto()
    AD_SECRET_INVALID = enum.auto()
    AD_KEYTAB_INVALID = enum.auto()
    AD_NETLOGON_FAILURE = enum.auto()
    AD_WBCLIENT_FAILURE = enum.auto()
    NTP_EXCESSIVE_SLEW = enum.auto()
    WINBIND_STOPPED = enum.auto()


class LDAPHealthCheckFailReason(enum.IntEnum):
    LDAP_BIND_FAILED = enum.auto()
    SSSD_STOPPED = enum.auto()


class DirectoryServiceHealthError(Exception):
    reasons = None

    def __init__(self, fail_reason, errmsg):
        self.reason = self.reasons(fail_reason)
        self.errmsg = errmsg

    def __str__(self):
        return self.errmsg


class KRB5HealthError(DirectoryServiceHealthError):
    reasons = KRB5HealthCheckFailReason


class IPAHealthError(DirectoryServiceHealthError):
    reasons = IPAHealthCheckFailReason


class ADHealthError(DirectoryServiceHealthError):
    reasons = ADHealthCheckFailReason


class LDAPHealthError(DirectoryServiceHealthError):
    reasons = ADHealthCheckFailReason


class DirectoryServiceHealth:
    __slots__ = ('_dstype', '_status', '_status_msg', '_initialized', '_lock')

    def __init__(self):
        self._dstype = None
        self._status = None
        self._status_msg = None
        self._initialized = False
        self._lock = Lock()

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def dstype(self) -> DSType | None:
        return self._dstype

    @property
    def status(self) -> DSStatus | None:
        return self._status

    @property
    def status_msg(self):
        return self._status_msg

    def update(self, dstype_in, status_in, status_msg):
        dstype = DSType(dstype_in) if dstype_in is not None else None
        status = DSStatus(status_in) if status_in is not None else None
        if status_msg is not None and not isinstance(status_msg, str):
            raise ValueError(f'{type(status_msg)}: status_msg must be string or None type')

        with self._lock:
            self._initialized = True
            self._dstype = dstype
            self._status = status
            self._status_msg = status_msg

    def dump(self) -> dict:
        with self._lock:
            return {
                'type': self.dstype.value if self.dstype else None,
                'status': self.status.name if self.status else None,
                'status_msg': self.status_msg
            }


DSHealthObj = DirectoryServiceHealth()
