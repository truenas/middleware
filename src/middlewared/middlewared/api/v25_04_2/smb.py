from middlewared.api.base import (
    BaseModel,
    excluded_field,
    Excluded,
    ForUpdateMetaclass,
    NetbiosName,
    NetbiosDomain,
    NonEmptyString,
    single_argument_args,
    SID,
    UnixPerm,
)
from middlewared.utils.smb import SMBUnixCharset
from pydantic import Field, field_validator, IPvAnyInterface, model_validator
from typing import Literal, Self

__all__ = [
    'SharingSMBGetaclArgs', 'SharingSMBGetaclResult',
    'SharingSMBSetaclArgs', 'SharingSMBSetaclResult',
    'SMBEntry', 'SMBUpdateArgs', 'SMBUpdateResult',
    'SMBUnixcharsetChoicesArgs', 'SMBUnixcharsetChoicesResult',
    'SMBBindipChoicesArgs', 'SMBBindipChoicesResult',
    'SharingSMBPresetsArgs', 'SharingSMBPresetsResult',
]

EMPTY_STRING = ''

SMBCharsetType = Literal[
    SMBUnixCharset.UTF_8, SMBUnixCharset.GB2312, SMBUnixCharset.HZ_GB_2312,
    SMBUnixCharset.CP1361, SMBUnixCharset.BIG5, SMBUnixCharset.BIG5HKSCS, SMBUnixCharset.CP037,
    SMBUnixCharset.CP273, SMBUnixCharset.CP424, SMBUnixCharset.CP437, SMBUnixCharset.CP500,
    SMBUnixCharset.CP775, SMBUnixCharset.CP850, SMBUnixCharset.CP852, SMBUnixCharset.CP855,
    SMBUnixCharset.CP857, SMBUnixCharset.CP858, SMBUnixCharset.CP860, SMBUnixCharset.CP861,
    SMBUnixCharset.CP862, SMBUnixCharset.CP863, SMBUnixCharset.CP864, SMBUnixCharset.CP865,
    SMBUnixCharset.CP866, SMBUnixCharset.CP869, SMBUnixCharset.CP932, SMBUnixCharset.CP949,
    SMBUnixCharset.CP950, SMBUnixCharset.CP1026, SMBUnixCharset.CP1125, SMBUnixCharset.CP1140,
    SMBUnixCharset.CP1250, SMBUnixCharset.CP1251, SMBUnixCharset.CP1252, SMBUnixCharset.CP1253,
    SMBUnixCharset.CP1254, SMBUnixCharset.CP1255, SMBUnixCharset.CP1256, SMBUnixCharset.CP1257,
    SMBUnixCharset.CP1258, SMBUnixCharset.EUC_JIS_2004, SMBUnixCharset.EUC_JISX0213, SMBUnixCharset.EUC_JP,
    SMBUnixCharset.EUC_KR, SMBUnixCharset.GB18030, SMBUnixCharset.GBK, SMBUnixCharset.HZ, SMBUnixCharset.ISO2022_JP,
    SMBUnixCharset.ISO2022_JP_1, SMBUnixCharset.ISO2022_JP_2, SMBUnixCharset.ISO2022_JP_2004,
    SMBUnixCharset.ISO2022_JP_3, SMBUnixCharset.ISO2022_JP_EXT, SMBUnixCharset.ISO2022_KR, SMBUnixCharset.ISO8859_1,
    SMBUnixCharset.ISO8859_2, SMBUnixCharset.ISO8859_3, SMBUnixCharset.ISO8859_4, SMBUnixCharset.ISO8859_5,
    SMBUnixCharset.ISO8859_6, SMBUnixCharset.ISO8859_7, SMBUnixCharset.ISO8859_8, SMBUnixCharset.ISO8859_9,
    SMBUnixCharset.ISO8859_10, SMBUnixCharset.ISO8859_11, SMBUnixCharset.ISO8859_13,
    SMBUnixCharset.ISO8859_14, SMBUnixCharset.ISO8859_15, SMBUnixCharset.ISO8859_16, SMBUnixCharset.JOHAB,
    SMBUnixCharset.KOI8_R, SMBUnixCharset.KZ1048, SMBUnixCharset.LATIN_1, SMBUnixCharset.MAC_CYRILLIC,
    SMBUnixCharset.MAC_GREEK, SMBUnixCharset.MAC_ICELAND, SMBUnixCharset.MAC_LATIN2, SMBUnixCharset.MAC_ROMAN,
    SMBUnixCharset.MAC_TURKISH, SMBUnixCharset.PTCP154, SMBUnixCharset.SHIFT_JIS,
    SMBUnixCharset.SHIFT_JIS_2004, SMBUnixCharset.SHIFT_JISX0213, SMBUnixCharset.TIS_620, SMBUnixCharset.UTF_16,
    SMBUnixCharset.UTF_16_BE, SMBUnixCharset.UTF_16_LE,
]


class SMBShareAclEntryWhoId(BaseModel):
    id_type: Literal['USER', 'GROUP', 'BOTH']
    xid: int = Field(alias='id')


class SMBShareAclEntry(BaseModel):
    ae_perm: Literal['FULL', 'CHANGE', 'READ']
    """ Permissions granted to the principal. """
    ae_type: Literal['ALLOWED', 'DENIED']
    """ The type of SMB share ACL entry. """
    ae_who_sid: SID | None = None
    """ SID value of the principal to whom ACL entry applies. """
    ae_who_id: SMBShareAclEntryWhoId | None = None
    """ Unix ID of the principal to whom ACL entry applies. """
    ae_who_str: NonEmptyString | None = None
    """ User or group name of the principal to whom the ACL entry applies """

    @model_validator(mode='after')
    def check_ae_who(self) -> Self:
        if self.ae_who_sid is None and self.ae_who_id is None and self.ae_who_str is None:
            raise ValueError(
                'One of the following fields is required to identify the user or group to whom the '
                'ACL entry applies: "ae_who_sid", "ae_who_str", or "ae_who_id"'
            )

        return self


class SMBShareAcl(BaseModel):
    share_name: NonEmptyString
    """ Name of the SMB share. """
    share_acl: list[SMBShareAclEntry] = [SMBShareAclEntry(ae_who_sid='S-1-1-0', ae_perm='FULL', ae_type='ALLOWED')]
    """ List of SMB share ACL entries """


@single_argument_args('smb_setacl')
class SharingSMBSetaclArgs(SMBShareAcl):
    pass


class SharingSMBSetaclResult(BaseModel):
    result: SMBShareAcl


@single_argument_args('smb_getacl')
class SharingSMBGetaclArgs(BaseModel):
    share_name: NonEmptyString


class SharingSMBGetaclResult(SharingSMBSetaclResult):
    pass


SMBEncryption = Literal['DEFAULT', 'NEGOTIATE', 'DESIRED', 'REQUIRED']


class SMBEntry(BaseModel):
    id: int
    netbiosname: NetbiosName
    """ Netbios name of this server """
    netbiosalias: list[NetbiosName]
    """ Alternative netbios names of the server that will be announced via
    netbios nameserver and registered in active directory when joined."""
    workgroup: NetbiosDomain
    """ Workgroup. When joined to active directory, this will be automatically
    reconfigured to match the netbios domain of the AD domain. """
    description: str
    """ Description of SMB server. May appear to clients during some operations. """
    enable_smb1: bool
    """ Enable SMB1 support for server. WARNING: using SMB1 protocol is not recommended """
    unixcharset: SMBCharsetType
    """ Select characterset for file names on local filesystem. This should only be used
    in cases where system administrator knows that the filenames are not UTF-8."""
    localmaster: bool
    syslog: bool
    """ Send log messages to syslog. This should be enabled if system administrator
    wishes for SMB server error logs to be included in information sent to remote syslog
    server if this is globally configured for TrueNAS."""
    aapl_extensions: bool
    """ Enable support for SMB2/3 AAPL protocol extensions. This changes the TrueNAS server
    so that it is advertised as supporting Apple protocol extensions as a MacOS server, and
    is required for Time Machine support. """
    admin_group: str | None
    """ The selected group will have full administrator privileges on TrueNAS over SMB protocol. """
    guest: NonEmptyString
    filemask: UnixPerm | Literal['DEFAULT']
    """ smb.conf create mask. DEFAULT applies current server default which is 664. """
    dirmask: UnixPerm | Literal['DEFAULT']
    """ smb.conf directory mask. DEFAULT applies current server default which is 775. """
    ntlmv1_auth: bool
    """ Enable legacy and very insecure NTLMv1 authentication. This should never be done except
    in extreme edge cases and may be against regulations in non-home environments. """
    multichannel: bool
    encryption: SMBEncryption
    bindip: list[IPvAnyInterface]
    server_sid: SID | None
    """ Universally-unique identifier for this particular SMB server that serves as domain SID
    for all local SMB user and group accounts """
    smb_options: str
    """ Additional unvalidated and unsupported configuration options for the SMB server.
    WARNING: using smb_options may produce unexpected server behavior. """
    debug: bool
    """ Set SMB log levels to debug. This should only be used when troubleshooting a specific SMB
    issue and should not be used in production environments. """

    @field_validator('bindip')
    @classmethod
    def normalize_bindips(cls, values: list[IPvAnyInterface]) -> list[str]:
        """We'll be passed a list of IPvAnyInterface types, and we
        deserialize these values by simply doing `str(value)`. Since this
        is an `Interface` type from `ipaddress` module, it will contain
        the netmask in the string (i.e. '192.168.1.150/32'). We don't
        need the netmask info because the smb.bindip_choices method
        returns a dictionary of addresses without the netmask info.
        (i.e. {'192.168.1.150': '192.168.1.150'})."""
        return [str(i.ip) for i in values]


@single_argument_args('smb_update')
class SMBUpdateArgs(SMBEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class SMBUpdateResult(BaseModel):
    result: SMBEntry


class SMBUnixcharsetChoicesArgs(BaseModel):
    pass


class SMBUnixcharsetChoicesResult(BaseModel):
    result: dict[str, SMBCharsetType]


class SMBBindipChoicesArgs(BaseModel):
    pass


class SMBBindipChoicesResult(BaseModel):
    result: dict[str, str]


class SharingSMBPresetsArgs(BaseModel):
    pass


class SharingSMBPresetsResult(BaseModel):
    result: dict[str, dict]
