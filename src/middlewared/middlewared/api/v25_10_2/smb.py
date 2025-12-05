from typing import Annotated, Any, Literal, Self, Union
from pydantic import AfterValidator, Field, field_validator, IPvAnyInterface, model_validator
from middlewared.api.base import (
    BaseModel,
    excluded_field,
    Excluded,
    ForUpdateMetaclass,
    LongString,
    NetbiosName,
    NetbiosDomain,
    NonEmptyString,
    single_argument_args,
    SID,
    SmbShareName,
    UnixPerm,
)
from middlewared.plugins.smb_.constants import SMBShareField as share_field
from middlewared.plugins.smb_.constants import LEGACY_SHARE_FIELDS
from middlewared.utils.lang import undefined
from middlewared.utils.smb import SMBUnixCharset, SMBSharePurpose, validate_smb_path_suffix

__all__ = [
    'SharingSMBGetaclArgs', 'SharingSMBGetaclResult',
    'SharingSMBSetaclArgs', 'SharingSMBSetaclResult',
    'SMBEntry', 'SMBUpdateArgs', 'SMBUpdateResult',
    'SMBUnixcharsetChoicesArgs', 'SMBUnixcharsetChoicesResult',
    'SMBBindipChoicesArgs', 'SMBBindipChoicesResult',
    'SharingSMBPresetsArgs', 'SharingSMBPresetsResult',
    'SharingSMBSharePrecheckArgs', 'SharingSMBSharePrecheckResult',
    'SharingSMBEntry', 'SharingSMBCreateArgs', 'SharingSMBCreateResult',
    'SharingSMBUpdateArgs', 'SharingSMBUpdateResult',
    'SharingSMBDeleteArgs', 'SharingSMBDeleteResult',
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
    id_type: Literal['USER', 'GROUP']
    """ The type of Unix ID.
    If the type is `USER`, the `xid` value refers to a Unix UID.
    If the type is `GROUP`, the `xid` value refers to a Unix GID."""
    xid: int = Field(alias='id', ge=0, le=2147483647)
    """Unix user ID (UID) or group ID (GID) depending on the `id_type` field."""


class SMBShareAclEntry(BaseModel):
    """ An SMB Share ACL Entry that grants or denies specific permissions to a principal.
    You can identify the principal by a SID (`ae_who_sid`), Unix ID (`ae_who_id`), \
    or name (`ae_who_str`). """
    ae_perm: Literal['FULL', 'CHANGE', 'READ']
    """ Permissions granted or denied to the principal. """
    ae_type: Literal['ALLOWED', 'DENIED']
    """ The type of SMB share ACL entry.
    This value determines whether the permissions (ae_perm) are granted (ALLOWED) or denied (DENIED). """
    ae_who_sid: SID | None = None
    """ The SID of the principal to whom this ACL entry applies. """
    ae_who_id: SMBShareAclEntryWhoId | None = None
    """ The Unix ID of the principal to whom this ACL entry applies. """
    ae_who_str: NonEmptyString | None = None
    """ The User or group name of the principal to whom this ACL entry applies. """

    @model_validator(mode='after')
    def check_ae_who(self) -> Self:
        if self.ae_who_sid is None and self.ae_who_id is None and self.ae_who_str is None:
            raise ValueError(
                'You must set one of the following fields to identify the user or group that this ACL entry '
                'applies to: "ae_who_sid", "ae_who_str", or "ae_who_id"'
            )

        return self


class SMBShareAcl(BaseModel):
    """ The ACL that applies to a specific SMB share.

    NOTE: this is not the same as a filesystem ACL. It only affects access through the SMB protocol. """
    share_name: NonEmptyString
    """ Name of the SMB share. """
    share_acl: list[SMBShareAclEntry] = [SMBShareAclEntry(ae_who_sid='S-1-1-0', ae_perm='FULL', ae_type='ALLOWED')]
    """ List of SMB share ACL entries. """


@single_argument_args('smb_setacl')
class SharingSMBSetaclArgs(SMBShareAcl):
    pass


class SharingSMBSetaclResult(BaseModel):
    result: SMBShareAcl
    """The updated SMB share ACL configuration."""


@single_argument_args('smb_getacl')
class SharingSMBGetaclArgs(BaseModel):
    share_name: NonEmptyString
    """Name of the SMB share to retrieve ACL for."""


class SharingSMBGetaclResult(SharingSMBSetaclResult):
    pass


SMBEncryption = Literal['DEFAULT', 'NEGOTIATE', 'DESIRED', 'REQUIRED']


class SMBEntry(BaseModel):
    """ TrueNAS SMB server configuration. """
    id: int
    """Unique identifier for the SMB service configuration."""
    netbiosname: NetbiosName
    """ The NetBIOS name of this server. """
    netbiosalias: list[NetbiosName]
    """ Alternative netbios names of the TrueNAS server. These names are announced through NetBIOS name server and \
    registered in Active Directory when TrueNAS joins the domain."""
    workgroup: NetbiosDomain
    """ Workgroup name. When TrueNAS joins active directory, it automatically changes this value to match the NetBIOS \
    domain of the Active Directory domain. """
    description: str
    """ Description of the SMB server. SMB clients may see this description during some operations. """
    enable_smb1: bool
    """ Enable SMB1 support on the server. WARNING: using the SMB1 protocol is not recommended. """
    unixcharset: SMBCharsetType
    """ Select character set for file names on local filesystem. Use this option only if you know the names are not \
    UTF-8. """
    localmaster: bool
    """ When set to `true` the NetBIOS name server in TrueNAS participates in elections for the local master browser.
    When set to `false` the NetBIOS name server does not attempt to become a local master browser on a subnet and \
    loses all browsing elections.

    NOTE: This parameter has no effect if the NetBIOS name server is disabled. """
    syslog: bool
    """ Send log messages to syslog. Enable this option if you want SMB server error logs to be included in \
    information sent to a remote syslog server. NOTE: This requires that remote syslog is globally configured on \
    TrueNAS. """
    aapl_extensions: bool
    """ Enable support for SMB2/3 AAPL protocol extensions. This setting makes the TrueNAS server advertise support \
    for Apple protocol extensions as a MacOS server. Enabling this is required for Time Machine support. """
    admin_group: str | None
    """ The selected group has full administrator privileges on TrueNAS via the SMB protocol. """
    guest: NonEmptyString
    """ SMB guest account username. This username provides access to legacy SMB shares with guest access enabled. \
    It must be a valid, existing local user account. """
    filemask: UnixPerm | Literal['DEFAULT']
    """ `smb.conf` create mask. DEFAULT applies current server default which is 664. """
    dirmask: UnixPerm | Literal['DEFAULT']
    """ `smb.conf` directory mask. DEFAULT applies current server default which is 775. """
    ntlmv1_auth: bool
    """ Enable legacy and very insecure NTLMv1 authentication. This should never be done except \
    in extreme edge cases and may be against regulations in non-home environments. """
    multichannel: bool
    """ Enable SMB3 multi-channel support. """
    encryption: SMBEncryption
    """ SMB2/3 transport encryption setting for the TrueNAS SMB server.

    * `NEGOTIATE`: Enable negotiation of data encryption. Encrypt data only if the client explicitly requests it.
    * `DESIRED`: Enable negotiation of data encryption. Encrypt data on sessions and share connections for clients \
      that support it.
    * `REQUIRED`: Require data encryption for sessions and share connections.
      NOTE: Clients that do not support encryption cannot access SMB shares.
    * `DEFAULT`: Use the TrueNAS SMB server default encryption settings. Currently, this is the same as `NEGOTIATE`.
    """
    bindip: list[IPvAnyInterface]
    """ List of IP addresses used by the TrueNAS SMB server. """
    server_sid: SID | None
    """ The unique identifier for the TrueNAS SMB server. It also serves as the domain SID for all local SMB user and \
    group accounts. """
    smb_options: str
    """ Additional unvalidated and unsupported configuration options for the SMB server.
    WARNING: Using `smb_options` may produce unexpected server behavior. """
    debug: bool
    """ Set SMB log levels to debug. Use this setting only when troubleshooting a specific SMB issue. Do not use it \
    in production environments. """

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
    """The updated SMB service configuration."""


class SMBUnixcharsetChoicesArgs(BaseModel):
    pass


class SMBUnixcharsetChoicesResult(BaseModel):
    result: dict[str, SMBCharsetType]
    """Available character set choices for Unix charset configuration."""


class SMBBindipChoicesArgs(BaseModel):
    pass


class SMBBindipChoicesResult(BaseModel):
    result: dict[str, str]
    """Available IP addresses that the SMB service can bind to."""


class SharingSMBPresetsArgs(BaseModel):
    pass


class SharingSMBPresetsResult(BaseModel):
    result: dict[str, dict]
    """Available SMB share preset configurations by purpose."""


@single_argument_args('smb_share_precheck')
class SharingSMBSharePrecheckArgs(BaseModel):
    name: SmbShareName | None = None
    """Name of the SMB share to validate (optional)."""


class SharingSMBSharePrecheckResult(BaseModel):
    result: None
    """Returns `null` when the SMB share configuration passes validation checks."""


SmbNamingSchema = Annotated[str, AfterValidator(validate_smb_path_suffix)]


class SmbAuditConfig(BaseModel):
    """ Settings for auditing SMB shares.

    NOTE: If a user is a member of groups in the `watch_list` and the `ignore_list`, the `watch_list` \
    has priority, and the SMB session is audited. """
    enable: bool = False
    """ Turn on auditing for the SMB share. SMB share auditing may not be enabled if `enable_smb1` is `true` \
    in the SMB service configuration."""
    watch_list: list[NonEmptyString] = Field(default=[], examples=[['interns', 'contractors']])
    """ Only audit the listed group accounts. If the list is empty, all groups will be audited. """
    ignore_list: list[NonEmptyString] = Field(default=[], examples=[['automation', 'apps']])
    """ List of groups that will not be audited. """


class DefaultOpt(BaseModel):
    """ These configuration options apply to shares with the `DEFAULT_SHARE` purpose. """
    purpose: Literal[SMBSharePurpose.DEFAULT_SHARE] = Field(exclude=True, repr=False)
    aapl_name_mangling: bool = False
    """ If set, illegal NTFS characters commonly used by MacOS clients are stored with their native values on the SMB \
    server's local filesystem.

    NOTE: Files with illegal NTFS characters in their names may not be accessible to non-MacOS SMB clients.

    WARNING: This value should not be changed once data is written to the SMB share. """
    hostsallow: list[str] = Field(default=[], examples=[
        ['192.168.0.200', '150.203.'],
        ['150.203.15.0/255.255.255.0'],
        ['150.203. EXCEPT 150.203.6.66']
    ])
    """ A list of IP addresses or subnets that are allowed to access the SMB share. The EXCEPT keyword \
    may be used to limit a wildcard list.

    NOTE: Hostname lookups are disabled on the SMB server for performance reasons. """
    hostsdeny: list[str] = Field(default=[], examples=[['150.203.4.'], ['ALL'], ['0.0.0.0/0']])
    """ A list of IP addresses or subnets that are not allowed to access the SMB share. The keyword \
    `ALL` or the netmask `0.0.0.0/0` may be used to deny all by default. """


class LegacyOpt(BaseModel):
    """ These configuration options apply to shares with the `LEGACY_SHARE` purpose. """
    purpose: Literal[SMBSharePurpose.LEGACY_SHARE] = Field(exclude=True, repr=False)
    recyclebin: bool = False
    """ If set, deleted files are moved to per-user subdirectories in the `.recycle` directory. The \
    SMB server creates the `.recycle` directory at the root of the SMB share if the file is in the same \
    ZFS dataset as the share `path`. If the file is in a child ZFS dataset, the server uses the \
    `mountpoint` of that dataset to create the `.recycle` directory.

    NOTE: This feature does not work with recycle bin features in client operating systems.

    WARNING: Do not use this feature instead of backups or ZFS snapshots. """
    path_suffix: SmbNamingSchema | None = Field(default=None, examples=["%D/%U"])
    """Path suffix template for dynamic path generation. Uses SMB variable substitution patterns like `%D` (domain) \
    and `%U` (username)."""
    hostsallow: list[str] = Field(default=[], examples=[
        ['192.168.0.200', '150.203.'],
        ['150.203.15.0/255.255.255.0'],
        ['150.203. EXCEPT 150.203.6.66']
    ])
    """ A list of IP addresses or subnets that are allowed to access the SMB share. The EXCEPT keyword \
    may be used to limit a wildcard list.

    NOTE: Hostname lookups are disabled on the SMB server for performance reasons. """
    hostsdeny: list[str] = Field(default=[], examples=[['150.203.4.'], ['ALL'], ['0.0.0.0/0']])
    """ A list of IP addresses or subnets that are not allowed to access the SMB share. The keyword \
    `ALL` or the netmask `0.0.0.0/0` may be used to deny all by default. """
    guestok: bool = False
    """ If set, guest access to the share is allowed. This should not be used in production environments.

    NOTE: If a user account does not exist, the SMB server maps access to the guest account.

    WARNING: Additional client-side configuration downgrading security settings may be required in order \
    to use this feature. """
    streams: bool = True
    """ If set, support for SMB alternate data streams is enabled.

    WARNING: This value should not be changed once data is written to the SMB share. """
    durablehandle: bool = True
    """ If set, support for SMB durable handles is enabled.

    WARNING: This feature is incompatible with multiprotocol and local filesystem access. """
    shadowcopy: bool = True
    """ If set, previous versions of files contained in ZFS snapshots are accessible through standard SMB protocol \
    operations on previous versions of files. """
    fsrvp: bool = False
    """ If set, enable support for the File Server Remote VSS Protocol. This allows clients to manage \
    snapshots for the specified SMB share. """
    home: bool = False
    """ Use the `path` to store user home directories. Each user has a personal home directory and share. \
    Users cannot access other user directories when connecting to shares.

    NOTE: This parameter changes the share `name` to `homes`. It also creates a dynamic share that mirrors \
    the username of the user. Both shares use the same `path`. You can hide the homes share by turning off \
    `browsable`. The dynamic user home share cannot be hidden.

    WARNING: This parameter changes the global server configuration. The SMB server will not authenticate \
    users without a valid home directory or shell."""
    acl: bool = True
    """ If set, enable mapping of local filesystem ACLs to NT ACLs for SMB clients. """
    afp: bool = False
    """ If set, SMB server will read and store file metadata in an on-disk format compatible with the \
    legacy AFP file server.

    WARNING: This should not be set unless the SMB server is sharing data that was originally written \
    via the AFP protocol. """
    timemachine: bool = False
    """ If set, MacOS clients can use the share as a time machine target. """
    timemachine_quota: int = Field(default=0, ge=0, le=109951162777600)
    """ If set, it defines the maximum size of a single time machine sparsebundle volume by limiting the \
    reported disk size to the SMB client. A value of zero means no quota is applied to the share.

    NOTE: Modern MacOS versions you set Time Machine quotas client-side. This gives more predictable \
    server and client behavior."""
    aapl_name_mangling: bool = False
    """ If set, illegal NTFS characters commonly used by MacOS clients are stored with their native values on the SMB \
    server's local filesystem.

    NOTE: Files with illegal NTFS characters in their names may not be accessible to non-MacOS SMB clients.

    WARNING: This value should not be changed once data is written to the SMB share. """
    vuid: NonEmptyString | None = Field(default=None, examples=['d12aafdc-a7ac-4e3c-8bbd-6001f7f19819'])
    """ This value is the Time Machine volume UUID for the SMB share. The TrueNAS server uses this value in the mDNS \
    advertisement for the Time Machine share. MacOS clients may use it to identify the volume. When you create or \
    update a share, setting this value to null makes the TrueNAS server generate a new UUID for the share. """
    auxsmbconf: LongString = ''
    """ Additional parameters to set on the SMB share. Parameters must be separated by the new-line character.

    WARNING: These parameters are not validated and may cause undefined server behavior including \
    data corruption or data loss.

    WARNING: Auxiliary parameters are an unsupported configuration."""


class TimeMachineOpt(BaseModel):
    """ These configuration options apply to shares with the `TIMEMACHINE_SHARE` purpose. """
    purpose: Literal[SMBSharePurpose.TIMEMACHINE_SHARE] = Field(exclude=True, repr=False)
    timemachine_quota: int = Field(default=0, ge=0, le=109951162777600)
    """ If set, it defines the maximum size in bytes of a single time machine sparsebundle volume by limiting the \
    reported disk size to the SMB client. A value of zero means no quota is set.

    NOTE: Modern MacOS versions you set Time Machine quotas client-side. This gives more predictable \
    server and client behavior."""
    auto_snapshot: bool = False
    """ If set, the server makes a ZFS snapshot of the share dataset when the client makes a new \
    Time Machine backup. """
    auto_dataset_creation: bool = False
    """ If set, the server uses the `dataset_naming_schema` to make a new ZFS dataset when the client connects. \
    The server uses this dataset as the share path during the SMB session.

    NOTE: this setting requires the share path to be a dataset mountpoint."""
    dataset_naming_schema: SmbNamingSchema | None = Field(default=None, examples=["%D/%U"])
    """ The naming schema to use when `auto_dataset_creation` is specified. If you do not set a schema, \
    the server uses `%U` (username) if it is not joined to Active Directory. If the server is joined to \
    Active Directory it uses `%D/%U` (domain/username). See the `VARIABLE SUBSTITUTIONS` section in the smb.conf \
    manpage for valid strings.

    WARNING: ZFS dataset naming rules are more restrictive than normal path rules. For example, if `%u` is specified \
    then the character `\\` may be inserted in the username (which is not supported in ZFS)."""
    vuid: NonEmptyString | None = Field(default=None, examples=['d12aafdc-a7ac-4e3c-8bbd-6001f7f19819'])
    """ This value is the Time Machine volume UUID for the SMB share. The TrueNAS server uses this value in the mDNS \
    advertisement for the Time Machine share. MacOS clients may use it to identify the volume. When you create or \
    update a share, setting this value to null makes the TrueNAS server generate a new UUID for the share. """
    hostsallow: list[str] = Field(default=[], examples=[
        ['192.168.0.200', '150.203.'],
        ['150.203.15.0/255.255.255.0'],
        ['150.203. EXCEPT 150.203.6.66']
    ])
    """ A list of IP addresses or subnets that are allowed to access the SMB share. The EXCEPT keyword \
    may be used to limit a wildcard list.

    NOTE: Hostname lookups are disabled on the SMB server for performance reasons. """
    hostsdeny: list[str] = Field(default=[], examples=[['150.203.4.'], ['ALL'], ['0.0.0.0/0']])
    """ A list of IP addresses or subnets that are not allowed to access the SMB share. The keyword \
    `ALL` or the netmask `0.0.0.0/0` may be used to deny all by default. """


class MultiprotocolOpt(BaseModel):
    """ These configuration options apply to shares with the `MULTIPROTOCOL_SHARE` purpose. """
    purpose: Literal[SMBSharePurpose.MULTIPROTOCOL_SHARE] = Field(exclude=True, repr=False)
    aapl_name_mangling: bool = False
    """ If set, illegal NTFS characters commonly used by MacOS clients are stored with their native values on the SMB \
    server's local filesystem.

    NOTE: Files with illegal NTFS characters in their names may not be accessible to non-MacOS SMB clients.

    WARNING: This value should not be changed once data is written to the SMB share. """
    hostsallow: list[str] = Field(default=[], examples=[
        ['192.168.0.200', '150.203.'],
        ['150.203.15.0/255.255.255.0'],
        ['150.203. EXCEPT 150.203.6.66']
    ])
    """ A list of IP addresses or subnets that are allowed to access the SMB share. The EXCEPT keyword \
    may be used to limit a wildcard list.

    NOTE: Hostname lookups are disabled on the SMB server for performance reasons. """
    hostsdeny: list[str] = Field(default=[], examples=[['150.203.4.'], ['ALL'], ['0.0.0.0/0']])
    """ A list of IP addresses or subnets that are not allowed to access the SMB share. The keyword \
    `ALL` or the netmask `0.0.0.0/0` may be used to deny all by default. """


class TimeLockedOpt(BaseModel):
    """ These configuration options apply to shares with the `TIME_LOCKED_SHARE` purpose. """
    purpose: Literal[SMBSharePurpose.TIME_LOCKED_SHARE] = Field(exclude=True, repr=False)
    grace_period: int = Field(default=900, ge=60, le=86400 * 180)
    """ Time in seconds when write access to the file or directory is allowed. """
    aapl_name_mangling: bool = False
    """ If set, illegal NTFS characters commonly used by MacOS clients are stored with their native values on the SMB \
    server's local filesystem.

    NOTE: Files with illegal NTFS characters in their names may not be accessible to non-MacOS SMB clients.

    WARNING: This value should not be changed once data is written to the SMB share. """
    hostsallow: list[str] = Field(default=[], examples=[
        ['192.168.0.200', '150.203.'],
        ['150.203.15.0/255.255.255.0'],
        ['150.203. EXCEPT 150.203.6.66']
    ])
    """ A list of IP addresses or subnets that are allowed to access the SMB share. The EXCEPT keyword \
    may be used to limit a wildcard list.

    NOTE: Hostname lookups are disabled on the SMB server for performance reasons. """
    hostsdeny: list[str] = Field(default=[], examples=[['150.203.4.'], ['ALL'], ['0.0.0.0/0']])
    """ A list of IP addresses or subnets that are not allowed to access the SMB share. The keyword \
    `ALL` or the netmask `0.0.0.0/0` may be used to deny all by default. """


class PrivateDatasetOpt(BaseModel):
    """ These configuration options apply to shares with the `PRIVATE_DATASETS_SHARE` purpose. """
    purpose: Literal[SMBSharePurpose.PRIVATE_DATASETS_SHARE] = Field(exclude=True, repr=False)
    dataset_naming_schema: SmbNamingSchema | None = Field(default=None, examples=["%D/%U"])
    """ The naming schema to use. If you do not set a schema, the server uses `%U` (username) if it is not joined to \
    Active Directory. If the server is joined to Active Directory it uses `%D/%U` (domain/username).

    WARNING: ZFS dataset naming rules are more restrictive than normal path rules."""
    auto_quota: int = Field(default=0, examples=[10], ge=0)
    """ Set the specified ZFS quota (in gibibytes) on new datasets. If the value is zero, TrueNAS disables \
    automatic quotas for the share."""
    aapl_name_mangling: bool = False
    """ If set, illegal NTFS characters commonly used by MacOS clients are stored with their native values on the SMB \
    server's local filesystem.

    NOTE: Files with illegal NTFS characters in their names may not be accessible to non-MacOS SMB clients.

    WARNING: This value should not be changed once data is written to the SMB share. """
    hostsallow: list[str] = Field(default=[], examples=[
        ['192.168.0.200', '150.203.'],
        ['150.203.15.0/255.255.255.0'],
        ['150.203. EXCEPT 150.203.6.66']
    ])
    """ A list of IP addresses or subnets that are allowed to access the SMB share. The EXCEPT keyword \
    may be used to limit a wildcard list.

    NOTE: Hostname lookups are disabled on the SMB server for performance reasons. """
    hostsdeny: list[str] = Field(default=[], examples=[['150.203.4.'], ['ALL'], ['0.0.0.0/0']])
    """ A list of IP addresses or subnets that are not allowed to access the SMB share. The keyword \
    `ALL` or the netmask `0.0.0.0/0` may be used to deny all by default. """


class ExternalOpt(BaseModel):
    """ These configuration options apply to shares with the `EXTERNAL_SHARE` purpose. """
    purpose: Literal[SMBSharePurpose.EXTERNAL_SHARE] = Field(exclude=True, repr=False)
    remote_path: list[NonEmptyString] = Field(examples=[
        [r'192.168.0.200\SHARE'],
        [r'SERVER1.MYDOM.INTERNAL\SHARE'],
        [r'SERVER1.MYDOM.INTERNAL\SHARE, SERVER2.MYDOM.INTERNAL\SHARE']
    ])
    """ This is the path to the external server and share. Each server entry must include a full domain name or IP \
    address and share name. Separate the server and share with the `\\` character.

    WARNING: The SMB server and TrueNAS middleware do not check if external paths are reachable. """

    @field_validator('remote_path')
    @classmethod
    def validate_external_path(cls, remote_path: list[NonEmptyString]) -> list:
        """ Validate that our proxy addresses are not malformed. """
        for proxy in remote_path:
            if len(proxy.split('\\')) != 2:
                raise ValueError(f'{proxy}: DFS proxy must be of format SERVER\\SHARE')

            if proxy.startswith('\\') or proxy.endswith('\\'):
                raise ValueError(f'{proxy}: DFS proxy must be of format SERVER\\SHARE')

        return remote_path


class FCPStorageOpt(BaseModel):
    """ These configuration options apply to shares with the `FCP_SHARE` purpose as a storage location \
    for Final Cut Pro data. """
    purpose: Literal[SMBSharePurpose.FCP_SHARE] = Field(exclude=True, repr=False)
    aapl_name_mangling: Literal[True] = True  # This is just added for visibility of what feature actually does
    """ Illegal NTFS characters commonly used by MacOS clients are stored with their native values on the SMB \
    server's local filesystem.

    NOTE: Files with illegal NTFS characters in their names may not be accessible to non-MacOS SMB clients. """
    hostsallow: list[str] = Field(default=[], examples=[
        ['192.168.0.200', '150.203.'],
        ['150.203.15.0/255.255.255.0'],
        ['150.203. EXCEPT 150.203.6.66']
    ])
    """ A list of IP addresses or subnets that are allowed to access the SMB share. The EXCEPT keyword \
    may be used to limit a wildcard list.

    NOTE: Hostname lookups are disabled on the SMB server for performance reasons. """
    hostsdeny: list[str] = Field(default=[], examples=[['150.203.4.'], ['ALL'], ['0.0.0.0/0']])
    """ A list of IP addresses or subnets that are not allowed to access the SMB share. The keyword \
    `ALL` or the netmask `0.0.0.0/0` may be used to deny all by default. """


class VeeamRepositoryOpt(BaseModel):
    """ These configuration options apply to shares with the `VEEAM_REPOSITORY_SHARE` purpose. """
    purpose: Literal[SMBSharePurpose.VEEAM_REPOSITORY_SHARE] = Field(exclude=True, repr=False)
    hostsallow: list[str] = Field(default=[], examples=[
        ['192.168.0.200', '150.203.'],
        ['150.203.15.0/255.255.255.0'],
        ['150.203. EXCEPT 150.203.6.66']
    ])
    """ A list of IP addresses or subnets that are allowed to access the SMB share. The EXCEPT keyword \
    may be used to limit a wildcard list.

    NOTE: Hostname lookups are disabled on the SMB server for performance reasons. """
    hostsdeny: list[str] = Field(default=[], examples=[['150.203.4.'], ['ALL'], ['0.0.0.0/0']])
    """ A list of IP addresses or subnets that are not allowed to access the SMB share. The keyword \
    `ALL` or the netmask `0.0.0.0/0` may be used to deny all by default. """


SmbShareOptions = Annotated[
    Union[
        LegacyOpt, DefaultOpt, TimeMachineOpt, MultiprotocolOpt, TimeLockedOpt, PrivateDatasetOpt, ExternalOpt,
        VeeamRepositoryOpt, FCPStorageOpt,
    ],
    Field(discriminator='purpose')
]


class SharingSMBEntry(BaseModel):
    """ SMB share entry on the TrueNAS server. """
    id: int
    """Unique identifier for this SMB share."""
    purpose: Literal[
        SMBSharePurpose.DEFAULT_SHARE,
        SMBSharePurpose.LEGACY_SHARE,
        SMBSharePurpose.TIMEMACHINE_SHARE,
        SMBSharePurpose.MULTIPROTOCOL_SHARE,
        SMBSharePurpose.TIME_LOCKED_SHARE,
        SMBSharePurpose.PRIVATE_DATASETS_SHARE,
        SMBSharePurpose.EXTERNAL_SHARE,
        SMBSharePurpose.VEEAM_REPOSITORY_SHARE,
        SMBSharePurpose.FCP_SHARE
    ] = SMBSharePurpose.DEFAULT_SHARE.value
    """ This parameter sets the purpose of the SMB share. It controls how the SMB share behaves and what features are \
    available through options. The DEFAULT_SHARE setting is best for most applications, and should be used, unless \
    there is a specific reason to change it.

    * `DEFAULT_SHARE`: Set the SMB share for best compatibility with common SMB clients.

    * `LEGACY_SHARE`: Set the SMB share for compatibility with older TrueNAS versions. Automated backend migrations \
      use this to help the administrator move to better-supported share settings. It should not be used for new SMB \
      shares.

    * `TIMEMACHINE_SHARE`: The SMB share is presented to MacOS clients as a time machine target.
      NOTE: `aapl_extensions` must be set in the global `smb.config`.

    * `MULTIPROTOCOL_SHARE`: The SMB share is configured for multi-protocol access. Set this if the `path` is shared \
      through NFS, FTP, or used by containers or apps.
      NOTE: This setting can reduce SMB share performance because it turns off some SMB features for safer \
      interoperability with external processes.

    * `TIME_LOCKED_SHARE`: The SMB share makes files read-only through the SMB protocol after the set grace_period \
      ends.
      WARNING: This setting does not work if the `path` is accessed locally or if another SMB share without the \
      `TIME_LOCKED_SHARE` purpose uses the same path.
      WARNING: This setting might not meet regulatory requirements for write-once storage.

    * `PRIVATE_DATASETS_SHARE`: The server uses the specified `dataset_naming_schema` in `options` to make a new ZFS \
      dataset when the client connects. The server uses this dataset as the share path during the SMB session.

    * `EXTERNAL_SHARE`: The SMB share is a DFS proxy to a share hosted on an external SMB server.

    * `VEEAM_REPOSITORY_SHARE`: The SMB share is a repository for Veeam Backup & Replication and supports Fast Clone.
      NOTE: This feature is available only for TrueNAS Enterprise customers.

    * `FCP_SHARE`: The SMB share is a used for Final Cut Pro storage. This feature automatically configures the share \
      to provide storage according to Apple support guidelines described in https://support.apple.com/en-ca/101919. \
      NOTE: `aapl_extensions` must be set in the global `smb.config`. \
      WARNING: This feature forcibly enables `aapl_name_mangling` on the SMB share which may cause unexpected behavior \
      for data that was written without this feature enabled.
    """
    name: SmbShareName = Field(examples=['SHARE', 'Macrodata_refinement'])
    """ SMB share name. SMB share names are case-insensitive and must be unique, and are subject \
    to the following restrictions:

    * A share name must be no more than 80 characters in length.

    * The following characters are illegal in a share name: `\\ / [ ] : | < > + = ; , * ? "`

    * Unicode control characters are illegal in a share name.

    * The following share names are not allowed: global, printers, homes.
    """
    path: NonEmptyString | Literal['EXTERNAL'] = Field(examples=['/mnt/dozer/SHARE', 'EXTERNAL'])
    """ Local server path to share by using the SMB protocol. The path must start with `/mnt/` and must be in a \
    ZFS pool.

    Use the string `EXTERNAL` if the share works as a DFS proxy.

    WARNING: The TrueNAS server does not check if external paths are reachable. """
    enabled: bool = True
    """ If unset, the SMB share is not available over the SMB protocol. """
    comment: str = Field(default='', examples=['Mammalian nurturable'])
    """ Text field that is seen next to a share when an SMB client requests a list of SMB shares on the TrueNAS \
    server. """
    readonly: bool = False
    """ If set, SMB clients cannot create or change files and directories in the SMB share.

    NOTE: If set, the share path is still writeable by local processes or other file sharing protocols. """
    browsable: bool = True
    """ If set, the share is included when an SMB client requests a list of SMB shares on the TrueNAS server. """
    access_based_share_enumeration: bool = False
    """ If set, the share is only included when an SMB client requests a list of shares on the SMB server if \
    the share (not filesystem) access control list (see `sharing.smb.getacl`) grants access to the user. """
    locked: bool | None
    """ Read-only value indicating whether the share is located on a locked dataset.

    Returns:
        - True: The share is in a locked dataset.
        - False: The share is not in a locked dataset.
        - None: Lock status is not available because path locking information was not requested.
    """
    audit: SmbAuditConfig = Field(default_factory=SmbAuditConfig, examples=[
        {'enable': True, 'watch_list': ['interns'], 'ignore_list': []},
        {'enable': True, 'watch_list': [], 'ignore_list': ['automation']}
    ])
    """Audit configuration for monitoring SMB share access and operations."""
    options: SmbShareOptions | None = Field(default=None, examples=[
        {'auto_snapshot': True},
        {'auto_quota': 100},
    ])
    """ Additional configuration related to the configured SMB share purpose. If null, then the default \
    options related to the share purpose will be applied. """

    @classmethod
    def normalize_legacy_fields(cls, data_in: dict) -> dict:
        """ TODO: remove this once UI has accomodated change """
        if share_field.PURPOSE not in data_in:
            return data_in

        new = data_in.copy()
        opts = {}

        # First take care of fields that have been renamed to improve clarity
        if 'ro' in new:
            new[share_field.RO] = new.pop('ro')

        if 'abe' in new:
            new[share_field.ABE] = new.pop('abe')

        if (aapl_mangling := new.pop(share_field.AAPL_MANGLING, False)):
            opts[share_field.AAPL_MANGLING] = aapl_mangling

        match new.get(share_field.PURPOSE):
            case 'NO_PRESET':
                opts = {}
                for field in LEGACY_SHARE_FIELDS:
                    if field in new:
                        opts[field] = new.pop(field)
            case 'ENHANCED_TIMEMACHINE':
                new[share_field.PURPOSE] = SMBSharePurpose.TIMEMACHINE_SHARE
                opts = {
                    share_field.AUTO_DS: True,
                    share_field.AUTO_SNAP: True
                }
            case 'TIMEMACHINE':
                new[share_field.PURPOSE] = SMBSharePurpose.TIMEMACHINE_SHARE
            case 'WORM_DROPBOX':
                new[share_field.PURPOSE] = SMBSharePurpose.TIME_LOCKED_SHARE
            case _:
                pass

        new[share_field.OPTS] = opts
        new[share_field.OPTS][share_field.PURPOSE] = new[share_field.PURPOSE]

        for field in LEGACY_SHARE_FIELDS:
            new.pop(field, None)

        return new

    @model_validator(mode='before')
    @classmethod
    def parse_nested(cls, data_in: Any) -> Any:
        """ Normalize share `purpose` and insert into hidden field in `options` for discriminator """
        if not isinstance(data_in, dict):
            return data_in

        new = cls.normalize_legacy_fields(data_in)

        if share_field.PURPOSE not in new and share_field.OPTS not in new:
            return new

        if share_field.OPTS not in new:
            raise ValueError('You must set `options` if you set `purpose`.')

        if share_field.PURPOSE not in new:
            raise ValueError('You must set `purpose` if you set `options`.')

        new[share_field.OPTS] = data_in.get(share_field.OPTS, {}).copy()
        new[share_field.OPTS][share_field.PURPOSE] = new[share_field.PURPOSE]
        return new


class SmbShareCreate(SharingSMBEntry):
    id: Excluded = excluded_field()
    locked: Excluded = excluded_field()

    @model_validator(mode='after')
    def check_purpose_options(self) -> Self:
        """ Extra validation to perform after validating individual fields. Currently used to
        ensure that path is consistent for external shares. """
        if not isinstance(self, SmbShareCreate):
            return self

        if self.purpose == SMBSharePurpose.EXTERNAL_SHARE:
            if self.path is undefined or self.path != 'EXTERNAL':
                raise ValueError('You must set `path` to "EXTERNAL" for external shares.')

        if self.options is None:
            # user may have explicitly set `None` for options in which
            # case we apply purpose-related defaults
            if self.purpose is undefined:
                # Explicit handling in case we're in update method and have wonky options
                raise ValueError('purpose field is required if options are specified as null')

            match self.purpose:
                case SMBSharePurpose.DEFAULT_SHARE:
                    opt_model = DefaultOpt
                case SMBSharePurpose.LEGACY_SHARE:
                    opt_model = LegacyOpt
                case SMBSharePurpose.TIMEMACHINE_SHARE:
                    opt_model = TimeMachineOpt
                case SMBSharePurpose.MULTIPROTOCOL_SHARE:
                    opt_model = MultiprotocolOpt
                case SMBSharePurpose.TIME_LOCKED_SHARE:
                    opt_model = TimeLockedOpt
                case SMBSharePurpose.PRIVATE_DATASETS_SHARE:
                    opt_model = PrivateDatasetOpt
                case SMBSharePurpose.EXTERNAL_SHARE:
                    opt_model = ExternalOpt
                    raise ValueError('External shares require explicit options configuration')
                case SMBSharePurpose.VEEAM_REPOSITORY_SHARE:
                    opt_model = VeeamRepositoryOpt
                case SMBSharePurpose.FCP_SHARE:
                    opt_model = FCPStorageOpt
                case _:
                    raise ValueError(f'{self.purpose}: unexpected share purpose')

            # We're running validation on basically empty dict here so that we can catch
            # case where potentially a share purpose actually has mandatory options fields
            # and generate a sensible validation message
            self.options = opt_model.model_validate({share_field.PURPOSE: self.purpose})

        return self


class SharingSMBCreateArgs(BaseModel):
    data: SmbShareCreate
    """SMB share configuration data for the new share."""


class SharingSMBCreateResult(BaseModel):
    result: SharingSMBEntry
    """The created SMB share configuration."""


class SmbShareUpdate(SmbShareCreate, metaclass=ForUpdateMetaclass):
    pass


class SharingSMBUpdateArgs(BaseModel):
    id: int
    """ID of the SMB share to update."""
    data: SmbShareUpdate
    """Updated SMB share configuration data."""


class SharingSMBUpdateResult(BaseModel):
    result: SharingSMBEntry
    """The updated SMB share configuration."""


class SharingSMBDeleteArgs(BaseModel):
    id: int
    """ID of the SMB share to delete."""


class SharingSMBDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the SMB share is successfully deleted."""
