import enum


class IpaConfigName(enum.StrEnum):
    """ Names for IPA-related entries we create in our databases """
    IPA_CACERT = 'IPA_DOMAIN_CACERT'
    IPA_HOST_KEYTAB = 'IPA_MACHINE_ACCOUNT'
    IPA_SMB_KEYTAB = 'IPA_SMB_KEYTAB'
    IPA_NFS_KEYTAB = 'IPA_NFS_KEYTAB'


class IpaHealthCheckFailReason(enum.IntEnum):
    """
    Enum for different reasons why the IPA directory service health_check()
    method may fail. These are placed in the `extra` key in CallError that
    is raised.
    """
    IPA_NO_CONFIG = enum.auto()
    IPA_CONFIG_PERM = enum.auto()
    IPA_NO_CACERT = enum.auto()
    IPA_CACERT_PERM = enum.auto()
    NTP_EXCESSIVE_SLEW = enum.auto()
    LDAP_BIND_FAILED = enum.auto()
    SSSD_STOPPED = enum.auto()


class IPAPath(enum.Enum):
    """ IPA related paths and their permissions """
    IPADIR = ('/etc/ipa', 0o755)
    DEFAULTCONF = ('/etc/ipa/default.conf', 0o644)
    CACERT = ('/etc/ipa/ca.crt', 0o644)

    @property
    def path(self):
        return self.value[0]

    @property
    def perm(self):
        return self.value[1]


class IPACmd(enum.Enum):
    """ Scripts and commands that are relevant to an IPA domain """
    IPACTL = '/usr/local/libexec/ipa_ctl.py'
    IPA = '/bin/ipa'
