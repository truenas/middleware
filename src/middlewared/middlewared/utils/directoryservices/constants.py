import enum
import os

from middlewared.plugins.system_dataset.utils import SYSDATASET_PATH

DS_HA_STATE_DIR = os.path.join(SYSDATASET_PATH, "directory_services")


class DSStatus(enum.StrEnum):
    DISABLED = 'DISABLED'
    FAULTED = 'FAULTED'
    LEAVING = 'LEAVING'
    JOINING = 'JOINING'
    HEALTHY = 'HEALTHY'


class DSType(enum.Enum):
    AD = 'ACTIVEDIRECTORY'
    IPA = 'IPA'
    LDAP = 'LDAP'

    @property
    def etc_files(self):
        match self:
            case DSType.AD:
                return ('pam', 'nss', 'smb', 'kerberos', 'ftp')
            case DSType.IPA:
                return ('ldap', 'ipa', 'pam', 'nss', 'smb', 'kerberos')
            case DSType.LDAP:
                return ('ldap', 'pam', 'nss', 'kerberos')


class SASL_Wrapping(enum.Enum):
    PLAIN = 'PLAIN'
    SIGN = 'SIGN'
    SEAL = 'SEAL'


class SSL(enum.Enum):
    NOSSL = 'OFF'
    USESSL = 'ON'
    USESTARTTLS = 'START_TLS'


class NSS_Info(enum.Enum):
    SFU = ('SFU', (DSType.AD,))
    SFU20 = ('SFU20', (DSType.AD,))
    RFC2307 = ('RFC2307', (DSType.AD, DSType.LDAP))
    RFC2307BIS = ('RFC2307BIS', (DSType.LDAP, DSType.IPA))
    TEMPLATE = ('TEMPLATE', (DSType.AD,))

    @property
    def nss_type(self):
        return self.value[0]

    @property
    def valid_services(self):
        return self.value[1]


class DomainJoinResponse(enum.StrEnum):
    PERFORMED_JOIN = 'PERFORMED_JOIN'
    ALREADY_JOINED = 'ALREADY_JOINED'


class DSCredType(enum.StrEnum):
    KERBEROS_USER = 'KERBEROS_USER'
    KERBEROS_PRINCIPAL = 'KERBEROS_PRINCIPAL'
    LDAP_PLAIN = 'LDAP_PLAIN'
    LDAP_ANONYMOUS = 'LDAP_ANONYMOUS'
    LDAP_MTLS = 'LDAP_MTLS'


DEF_SVC_OPTS = {'silent': False, 'ha_propagate': False}
