import enum


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
