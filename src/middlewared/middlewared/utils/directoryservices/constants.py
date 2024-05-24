import enum


class DSStatus(enum.Enum):
    DISABLED = enum.auto()
    FAULTED = enum.auto()
    LEAVING = enum.auto()
    JOINING = enum.auto()
    HEALTHY = enum.auto()


class DSType(enum.Enum):
    AD = 'activedirectory'
    IPA = 'ipa'
    LDAP = 'ldap'


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
