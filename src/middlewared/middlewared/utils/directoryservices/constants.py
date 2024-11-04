import enum


class DSStatus(enum.StrEnum):
    DISABLED = 'DISABLED'
    FAULTED = 'FAULTED'
    LEAVING = 'LEAVING'
    JOINING = 'JOINING'
    HEALTHY = 'HEALTHY'


class DSType(enum.StrEnum):
    STANDALONE = 'STANDALONE'
    AD = 'ACTIVEDIRECTORY'
    IPA = 'IPA'
    LDAP = 'LDAP'

    @property
    def etc_files(self):
        match self:
            case DSType.AD:
                return ('pam', 'nss', 'smb', 'kerberos')
            case DSType.IPA:
                return ('ldap', 'ipa', 'pam', 'nss', 'smb', 'kerberos')
            case DSType.LDAP:
                return ('ldap', 'pam', 'nss', 'kerberos')
            case DSType.STANDALONE:
                return tuple()

    @property
    def middleware_service(self):
        match self:
            case DSType.AD:
                return 'idmap'
            case DSType.IPA | DSType.LDAP:
                return 'sssd'
            case DSType.STANDALONE:
                return None


class SASL_Wrapping(enum.Enum):
    PLAIN = 'PLAIN'
    SIGN = 'SIGN'
    SEAL = 'SEAL'


class SSL(enum.StrEnum):
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
    NOT_JOINED = 'NOT_JOINED'
    PERFORMED_JOIN = 'PERFORMED_JOIN'
    ALREADY_JOINED = 'ALREADY_JOINED'


class DSCredentialType(enum.StrEnum):
    ANONYMOUS = 'ANONYMOUS'
    USERNAME_PASSWORD = 'USERNAME_PASSWORD'
    LDAPDN_PASSWORD = 'LDAPDN_PASSWORD'
    KERBEROS_PRINCIPAL = 'KERBEROS_PRINCIPAL'
    CERTIFICATE = 'CERTIFICATE'


class DSLdapSsl(enum.StrEnum):
    OFF = 'OFF'
    LDAPS = 'LDAPS'
    STARTTLS = 'STARTTLS'


class DSLdapNssInfo(enum.StrEnum):
    RFC2307 = 'RFC2307'
    RFC2307BIS = 'RFC2307BIS'


class DSActiveDirectoryNssInfo(enum.StrEnum):
    TEMPLATE = 'TEMPLATE'
    SFU = 'SFU'
    SFU20 = 'SFU20'
    RFC2307 = 'RFC2307'
