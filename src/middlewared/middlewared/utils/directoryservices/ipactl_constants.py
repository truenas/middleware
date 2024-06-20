# Shared constants between ipa_ctl script and middleware utils

import enum


class IpaOperation(enum.Enum):
    JOIN = enum.auto()
    LEAVE = enum.auto()
    SET_NFS_PRINCIPAL = enum.auto()
    DEL_NFS_PRINCIPAL = enum.auto()
    SET_SMB_PRINCIPAL = enum.auto()
    DEL_SMB_PRINCIPAL = enum.auto()
    SMB_DOMAIN_INFO = enum.auto()
    GET_CACERT_FROM_LDAP = enum.auto()


class ExitCode(enum.IntEnum):
    SUCCESS = 0
    GENERIC = 1
    USAGE = 2
    KERBEROS = 3
    FREEIPA_CONFIG = 4
    JSON_ERROR = 5
    NO_SMB_SUPPORT = 6
