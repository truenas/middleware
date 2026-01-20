import enum
from dataclasses import dataclass


class IpaConfigName(enum.StrEnum):
    """ Names for IPA-related entries we create in our databases """
    IPA_CACERT = 'IPA_DOMAIN_CACERT'
    IPA_HOST_KEYTAB = 'IPA_MACHINE_ACCOUNT'
    IPA_SMB_KEYTAB = 'IPA_SMB_KEYTAB'
    IPA_NFS_KEYTAB = 'IPA_NFS_KEYTAB'


class IPAPath(enum.Enum):
    """ IPA related paths and their permissions """
    IPADIR = ('/etc/ipa', 0o755)
    DEFAULTCONF = ('/etc/ipa/default.conf', 0o644)
    CACERT = ('/etc/ipa/ca.crt', 0o644)

    @property
    def path(self) -> str:
        return self.value[0]

    @property
    def perm(self) -> int:
        return self.value[1]


class IPACmd(enum.Enum):
    """ Scripts and commands that are relevant to an IPA domain """
    IPACTL = '/usr/local/libexec/ipa_ctl.py'
    IPA = '/bin/ipa'


@dataclass(frozen=True)
class IPASmbDomain:
    netbios_name: str
    domain_sid: str
    domain_name: str
    range_id_min: int
    range_id_max: int
