from middlewared.api.base import (
    BaseModel,
    excluded_field,
    Excluded,
    ForUpdateMetaclass,
    LongNonEmptyString,
    NonEmptyString,
    single_argument_args,
    single_argument_result,
    LDAP_DN,
    LDAP_URL,
    NetbiosDomain,
    SID,
)
from middlewared.utils.directoryservices.credential import DSCredType
from middlewared.utils.lang import undefined
from middlewared.plugins.idmap_.idmap_constants import TRUENAS_IDMAP_MAX, TRUENAS_IDMAP_MIN

from pydantic import Field, Secret, model_validator, field_validator
from typing import Annotated, Literal

__all__ = [
    'DirectoryServicesCacheRefreshArgs', 'DirectoryServicesCacheRefreshResult',
    'DirectoryServicesStatusArgs', 'DirectoryServicesStatusResult',
    'DirectoryServicesEntry', 'DirectoryServicesUpdateArgs', 'DirectoryServicesUpdateResult',
    'DirectoryServicesLeaveArgs', 'DirectoryServicesLeaveResult',
]

IdmapId = Annotated[int, Field(ge=TRUENAS_IDMAP_MIN, le=TRUENAS_IDMAP_MAX)]

DSStatus = Literal['DISABLED', 'FAULTED', 'LEAVING', 'JOINING', 'HEALTHY']
DSType = Literal['ACTIVEDIRECTORY', 'IPA', 'LDAP']


class DirectoryServicesStatusArgs(BaseModel):
    pass


@single_argument_result
class DirectoryServicesStatusResult(BaseModel):
    dstype: DSType | None = Field(alias='type')
    """ The type of enabled directory service. """
    status: DSStatus | None = None
    """ This field shows the directory service status from the last health check. The status is null if directory \
    services are disabled. """
    status_msg: str | None = None
    """ This field shows the reason why the directory service is FAULTED after a failed health check. If the directory \
    service is not faulted, the field is null. """


class DirectoryServicesCacheRefreshArgs(BaseModel):
    pass


class DirectoryServicesCacheRefreshResult(BaseModel):
    result: Literal[None]


# Idmap domains are a configuration feature of winbindd when joined to an active directory or ipa domain.
# The latter case is a special situation in which the IPA_SMBDomain is used as described in documentation
# strings.

class IdmapDomainBase(BaseModel):
    name: NetbiosDomain | None = Field(default=None, example='IXDOM')
    """ Short name for the domain. This should match the NetBIOS domain name for Active Directory domains. \
    It may be null if the domain is configured as the base idmap for Active Directory. """
    range_low: IdmapId = 100000001
    """ The lowest UID or GID that the idmap backend can assign. """
    range_high: IdmapId = 200000000
    """ The highest UID or GID that the idmap backend can assign. """

    @model_validator(mode='after')
    def check_ranges(self):
        if self.range_low >= self.range_high:
            raise ValueError("The low range must be less than high range")

        if (self.range_high - self.range_low) < 10000:
            raise ValueError("The domain range must include at least 10,000 IDs")

        return self


class IPA_SMBDomain(IdmapDomainBase):
    """ This is a special idmap backend used when TrueNAS joins an IPA domain. The remote IPA server provides the \
    configuration information during the domain join process."""
    idmap_backend: Literal['SSS']
    domain_name: NonEmptyString | None = Field(default=None, example='IXDOM.INTERNAL')
    """ Name of the SMB domain as defined in the IPA configuration for the IPA domain to which TrueNAS is joined. """
    domain_sid: SID | None = Field(default=None, example='S-1-5-21-3696504179-2855309571-923743039')
    """ The domain SID for the IPA domain to which TrueNAS is joined. """


class AD_Idmap(IdmapDomainBase):
    """ The AD backend reads UID and GID mappings from an Active Directory server that uses pre-existing RFC2307 / SFU \
    schema extensions. The administrator must add mappings for users and groups in Active Directory before use.

    NOTE: these schema extensions are not present by default in Active Directory."""
    idmap_backend: Literal['AD']
    schema_mode: Literal['RFC2307', 'SFU', 'SFU20']
    """ The schema mode the idmap backend uses to query Active Directory for user and group information. The RFC2307 \
    schema applies to Windows Server 2003 R2 and newer. The Services for Unix (SFU) schema applies to versions before \
    Windows Server 2003 R2. """
    unix_primary_group: bool = False
    """ Defines if the user's primary group is fetched from SFU attributes or the Active Directory primary group. \
    If True, the TrueNAS server uses the gidNumber LDAP attribute. If False, it uses the primaryGroupID LDAP attribute.
    """
    unix_nss_info: bool = False
    """ If True, the login shell and home directory are retrieved from LDAP attributes. If False, or if the Active \
    Directory LDAP entry lacks SFU attributes, the home directory defaults to `/var/empty`. """


class Autorid_Idmap(IdmapDomainBase):
    """ The AUTORID backend uses an algorithmic mapping scheme to map UIDs and GIDs to SIDs. It works like the RID \
    backend, but automatically configures the range for each domain in the forest. """
    idmap_backend: Literal['AUTORID']
    rangesize: int = Field(default=100000, ge=10000, le=1000000000)
    """ Defines the number of uids / gids available per domain range. SIDs with RIDs larger than this value will be \
    mapped into extension ranges depending on the number of available ranges."""
    readonly: bool = False
    """ Sets the module to read-only mode. The TrueNAS server will not create new ranges or mappings in the idmap \
    pool. """
    ignore_builtin: bool = False
    """ Do not process mapping requests for the BUILTIN domain. """


class LDAP_Idmap(IdmapDomainBase):
    """ The LDAP backend reads and writes UID / GID mapping tables from an external LDAP server. """
    idmap_backend: Literal['LDAP']
    ldap_base_dn: LDAP_DN
    """ Directory base suffix to use for mapping UIDs and GIDs to SIDs. """
    ldap_user_dn: LDAP_DN
    """ Defines the user DN to be used for authentication to the LDAP server. """
    ldap_user_dn_password: Secret[NonEmptyString]
    """ Secret to use for authenticating the user specified by `ldap_user_dn`. """
    ldap_url: LDAP_URL
    """ LDAP server to use for the idmap entries. """
    readonly: bool = True
    """ If readonly is set to True then TrueNAS will not attempt to write new idmap entries. """
    validate_certificates: bool = True
    """ If False, TrueNAS does not validate certificates from the remote LDAP server. It is better to use valid \
    certificates or import them into the TrueNAS server's trusted certificate store. """


class RFC2307_Idmap(IdmapDomainBase):
    """ The RFC2307 backend reads ID mappings from RFC2307 attributes on a standalone LDAP server. This backend is \
    read-only. Use the `AD` idmap backend if the server is an Active Directory domain controller. """
    idmap_backend: Literal['RFC2307']
    ldap_url: LDAP_URL
    """ The LDAP URL used to access the LDAP server. """
    ldap_user_dn: LDAP_DN
    """ Defines the DN used to authenticate to the LDAP server. """
    ldap_user_dn_password: Secret[NonEmptyString]
    """ The password used to authenticate the account specified in ldap_user_dn. """
    bind_path_user: LDAP_DN
    """ The search base that contains user objects in the LDAP server. """
    bind_path_group: LDAP_DN
    """ The search base that contains group objects in the LDAP server. """
    user_cn: bool = False
    """ If set, query the CN attribute instead of the UID attribute for the user name in LDAP. """
    ldap_realm: bool = False
    """ Append @realm to the CN for groups. Also append it to users if user_cn is specified. """
    validate_certificates: bool = True
    """ If False, TrueNAS does not validate certificates from the remote LDAP server. It is better to use valid \
    certificates or import them into the TrueNAS server's trusted certificate store. """


class RID_Idmap(IdmapDomainBase):
    """ The RID backend uses an algorithm to map UIDs and GIDs to SIDs. It determines the UID or GID by adding the RID \
    value from the Windows Account SID to the base value in range_low. RID values in an Active Directory domain can be \
    large, especially as the domain ages. Administrators should configure a range large enough to cover the current \
    RID values assigned by the RID master. One way to do this is to check the RID of a recently created account in \
    Active Directory. For example, if the RID is 500000, the range must include at least 500000 Unix IDs (for example, \
    1000000 to 2000000). """
    idmap_backend: Literal['RID']
    sssd_compat: bool = False
    """ Generate an idmap low range using the algorithm from SSSD. This works if the domain uses only a single SSSD \
    idmap slice, and is sufficient if the domain uses only a single SSSD idmap slice. """


class BuiltinDomainTdb(IdmapDomainBase):
    """ Idmap ranges and information for BUILTIN, system accounts, and other accounts not explicitly mapped to a known \
    domain. """
    range_low: IdmapId = 90000001
    """ The lowest UID or GID that the idmap backend can assign. """
    range_high: IdmapId = 100000000
    """ The highest UID or GID that the idmap backend can assign. """


DomainIdmap = Annotated[
    AD_Idmap | LDAP_Idmap | RFC2307_Idmap | RID_Idmap,
    Field(discriminator='idmap_backend', default=RID_Idmap(idmap_backend='RID'))
]


class PrimaryDomainIdmap(BaseModel):
    builtin: BuiltinDomainTdb = Field(default=BuiltinDomainTdb())
    """ UID and GID range configuration for automatically generated accounts linked to well-known and BUILTIN accounts \
    on Windows servers. """
    idmap_domain: DomainIdmap
    """ This configuration defines how domain accounts joined to TrueNAS are mapped to Unix UIDs and GIDs on the \
    TrueNAS server. Most TrueNAS deployments use the RID backend, which algorithmically assigns UIDs and GIDs based on \
    the Active Directory account SID. Another common option is the AD backend, which reads predefined Active Directory \
    LDAP schema attributes that assign explicit UID and GID numbers to accounts. """


class PrimaryDomainIdmapAutoRid(BaseModel):
    idmap_domain: Autorid_Idmap


class CredKRBPrincipal(BaseModel):
    credential_type: Literal[DSCredType.KERBEROS_PRINCIPAL]
    principal: NonEmptyString
    """ A kerberos principal is a unique identity to which Kerberos can assign tickets. The specified kerberos \
    principal must have an entry within a keytab on the TrueNAS server. """


class CredKRBUser(BaseModel):
    credential_type: Literal[DSCredType.KERBEROS_USER]
    username: NonEmptyString
    """ Username of the account to use to create a kerberos ticket for authentication to directory services. This \
    account must exist on the domain controller. """
    password: Secret[NonEmptyString]
    """ The password for the user account that will obtain the kerberos ticket. """


class CredLDAPPlain(BaseModel):
    credential_type: Literal[DSCredType.LDAP_PLAIN]
    binddn: LDAP_DN
    bindpw: Secret[NonEmptyString]


class CredLDAPAnonymous(BaseModel):
    credential_type: Literal[DSCredType.LDAP_ANONYMOUS]


class CredLDAPMTLS(BaseModel):
    credential_type: Literal[DSCredType.LDAP_MTLS]
    client_certificate: NonEmptyString
    """ The client certificate name used for mutual TLS authentication to the remote LDAP server. """


DSCred = Annotated[
    CredKRBUser | CredKRBPrincipal | CredLDAPPlain | CredLDAPAnonymous | CredLDAPMTLS,
    Field(discriminator='credential_type')
]


class ActiveDirectoryConfig(BaseModel):
    hostname: NonEmptyString
    """ Hostname of TrueNAS server to register in Active Directory. Example: "truenasnyc". """
    domain: NonEmptyString
    """ The full DNS domain name of the Active Directory domain. This must not be a domain controller. \
    Example: "mydomain.internal".  """
    idmap: PrimaryDomainIdmap | PrimaryDomainIdmapAutoRid = Field(default=PrimaryDomainIdmap(), examples=[
        {
            'builtin': {'range_low': 90000001, 'range_high': 100000000},
            'idmap_domain': {
                'name': 'MYDOMAIN',
                'idmap_backend': 'RID',
                'range_low': 100000001,
                'range_high': 200000000,
            },
        },
        {
            'idmap_domain': {
                'name': 'MYDOMAIN',
                'idmap_backend': 'AUTORID',
                'range_low': 90000001,
                'range_high': 2000000000
            }
        }
    ])
    """ Configuration for mapping Active Directory accounts to accounts on the TrueNAS server. The exact settings may \
    vary based on other servers and Linux clients in the domain. Defaults are suitable for new deployments without \
    existing support for unix-like operating systems. """
    site: NonEmptyString | None = None
    """ The Active Directory site where the TrueNAS server is located. TrueNAS detects this automatically during the \
    domain join process. """
    computer_account_ou: NonEmptyString | None = Field(default=None, example='TRUENAS_SERVERS/NYC')
    """ Use this setting to override the default organizational unit (OU) in which the TrueNAS computer account is \
    created during the domain join. Use it to set a custom location for TrueNAS computer accounts. """
    use_default_domain: bool = False
    """ Controls if the system removes the domain prefix from Active Directory user and group names. If enabled, users \
    appear as "administrator" instead of "EXAMPLE\\administrator". In most cases, disable this (default) to avoid name \
    conflicts between Active Directory and local accounts. """
    enable_trusted_domains: bool = False
    """ Enable support for trusted domains. If True, then separate trusted domain configuration must be set for all \
    trusted domains. """
    trusted_domains: list[DomainIdmap] = Field(default=[], examples=[
        {
            'name': 'BROOK',
            'idmap_backend': 'RID',
            'range_low': 200000001,
            'range_high': 300000000
        },
        {
            'name': 'DARVO',
            'idmap_backend': 'RID',
            'range_low': 300000001,
            'range_high': 400000000
        }
    ])
    """ Configuration for trusted domains. """

    @field_validator('trusted_domains')
    @classmethod
    def validate_trusted_domains(cls, value):
        # Check for range overlaps between trusted domains
        if any([entry.name is None for entry in value]):
            raise ValueError('Domain name is required for trusted domains')

        for idx, entry in enumerate(value):
            for idx2, entry2 in enumerate(value.copy()):
                if idx == idx2:
                    # skip ourselves
                    continue

                if entry.range_low >= entry2.range_low and entry.range_low <= entry2.range_high:
                    raise ValueError(f'Low range for {entry.name} conflicts with range for {entry2.name}.')

                if entry.range_high >= entry2.range_low and entry.range_high <= entry2.range_high:
                    raise ValueError(f'High range for {entry.name} conflicts with range for {entry2.name}.')

        return value


class LDAPSearchBases(BaseModel):
    """ Optional search paths to limit LDAP searches for attribute types. """
    base_user: LDAP_DN | None = None
    """ Optional base DN to limit LDAP user searches. If null (default) then the `base_dn` is used. """
    base_group: LDAP_DN | None = None
    """ Optional base DN to limit LDAP group searches. If null (default) then the `base_dn` is used. """
    base_netgroup: LDAP_DN | None = None
    """ Optional base DN to limit LDAP netgroup searches. If null (default) then the `base_dn` is used. """


class LDAPMapPasswd(BaseModel):
    """ Optional attribute mappings for non-compliant LDAP servers to generate passwd entries. \
    A value of null means to use the default according to the selected LDAP `schema`. """
    user_object_class: LDAP_DN | None = None
    """ The user entry object class in LDAP. """
    user_name: LDAP_DN | None = None
    """ The LDAP attribute for the user's login name. """
    user_uid: LDAP_DN | None = None
    """ The LDAP attribute for the user's id. """
    user_gid: LDAP_DN | None = None
    """ The LDAP attribute for the user's primary group id. """
    user_gecos: LDAP_DN | None = None
    """ The LDAP attribute for the user's gecos field. """
    user_home_directory: LDAP_DN | None = None
    """ The LDAP attribute for the user's home directory. """
    user_shell: LDAP_DN | None = None
    """ The LDAP attribute for the path to the user's default shell. """


class LDAPMapShadow(BaseModel):
    """ Optional attribute mappings for non-compliant LDAP servers to generate shadow entries. \
    A value of null means to use the default according to the selected LDAP `schema`. """
    shadow_last_change: LDAP_DN | None = None
    """ This parameter contains the name of an LDAP attribute for its shadow(5) counterpart (date of the \
    last password change)."""
    shadow_min: LDAP_DN | None = None
    """ This parameter contains the name of an LDAP attribute for its shadow(5) counterpart (minimum \
    password age). """
    shadow_max: LDAP_DN | None = None
    """ This parameter contains the name of an LDAP attribute for its shadow(5) counterpart (maximum \
    password age). """
    shadow_warning: LDAP_DN | None = None
    """ This parameter contains the name of an LDAP attribute for its shadow(5) counterpart (password \
    warning period). """
    shadow_inactive: LDAP_DN | None = None
    """ This parameter contains the name of an LDAP attribute for its shadow(5) counterpart (password \
    inactivity period). """
    shadow_expire: LDAP_DN | None = None
    """ This parameter contains the name of an LDAP attribute for its shadow(5) counterpart (account \
    expiration date). """


class LDAPMapGroup(BaseModel):
    """ Optional attribute mappings for non-compliant LDAP servers to generate group entries. \
    A value of null means to use the default according to the selected LDAP `schema`. """
    group_object_class: LDAP_DN | None = None
    """ The LDAP object class for group entries. """
    group_gid: LDAP_DN | None = None
    """ The LDAP attribute for the group's id. """
    group_member: LDAP_DN | None = None
    """ The LDAP attribute for the names of the group's members. """


class LDAPMapNetgroup(BaseModel):
    """ Optional attribute mappings for non-compliant LDAP servers to generate netgroup entries """
    netgroup_object_class: LDAP_DN | None = None
    """ The LDAP object class for netgroup entries. """
    netgroup_member: LDAP_DN | None = None
    """ The LDAP attribute for the netgroup's members. """
    netgroup_triple: LDAP_DN | None = None
    """ The LDAP attribute for netgroup triples (host, user, domain). """


class LDAPAttributeMaps(BaseModel):
    passwd: LDAPMapPasswd = Field(default=LDAPMapPasswd())
    shadow: LDAPMapShadow = Field(default=LDAPMapShadow())
    group: LDAPMapGroup = Field(default=LDAPMapGroup())
    netgroup: LDAPMapNetgroup = Field(default=LDAPMapNetgroup())


class LDAPConfig(BaseModel):
    server_urls: list[LDAP_URL]
    """ List of LDAP server URIs used for LDAP binds. Each URI must begin with ldap:// or ldaps:// and may use either \
    a DNS name or an IP address. Example: `['ldaps://myldap.domain.internal']`."""
    basedn: LDAP_DN
    """ The base DN to use when performing LDAP operations. Example: `"dc=domain,dc=internal"`. """
    starttls: bool = False
    """ Establish TLS by transmitting a StartTLS request to the server. """
    validate_certificates: bool = True
    """ If `False`, TrueNAS does not validate certificates from the remote LDAP server. It is better to use valid \
    certificates or import them into the TrueNAS server's trusted certificate store. """
    ldap_schema: Literal['RFC2307', 'RFC2307BIS'] = Field(default='RFC2307', alias='schema')
    """ The type of LDAP attribute schema that the remote LDAP server uses. """
    search_bases: LDAPSearchBases = Field(default=LDAPSearchBases())
    """ Alternative LDAP search base settings. These settings define where to find user, group, and netgroup entries. \
    If unspecified (the default), TrueNAS uses the `basedn` to find users. groups, and netgroups. Use these settings \
    only if the LDAP server uses a non-standard LDAP schema or if you want to limit the accounts available on \
    TrueNAS. """
    attribute_maps: LDAPAttributeMaps = Field(default=LDAPAttributeMaps())
    """ Optional LDAP attribute mapping for LDAP servers that do not follow RFC2307 or RFC2307BIS. Use this only if \
    the LDAP server is non-standard. """
    auxiliary_parameters: LongNonEmptyString | None = None
    """ Additional paramaters to add to the SSSD configuration.

    WARNING: TrueNAS does not check the validity of these parameters. Incorrect values can cause production outages \
    when they are applied or after an operating system upgrade. """


class IPAConfig(BaseModel):
    target_server: NonEmptyString
    """ The name of the IPA server that TrueNAS uses to build URLs when it joins or leaves the IPA domain. \
    Example: "ipa.example.internal". """
    hostname: NonEmptyString
    """ Hostname of TrueNAS server to register in IPA during the join process. Example: "truenasnyc". """
    domain: NonEmptyString
    """ The domain of the IPA server. Example "ipa.internal". """
    basedn: LDAP_DN
    """ The base DN to use when performing LDAP operations. Example: "dc=example,dc=internal". """
    smb_domain: IPA_SMBDomain | None = None
    """ Settings for the IPA SMB domain. TrueNAS detects these settings during IPA join. Some IPA domains may not \
    include SMB schema configuration. """
    validate_certificates: bool = True
    """ If `False`, TrueNAS does not validate certificates from the remote LDAP server. It is better to use valid \
    certificates or import them into the TrueNAS server's trusted certificate store. """


class DirectoryServicesEntry(BaseModel):
    id: int
    service_type: DSType | None
    """ The pre-existing directory service type to which to bind TrueNAS. Select ACTIVEDIRECTORY to join an Active \
    Directory domain. Select IPA to join a FreeIPA domain. Select LDAP to bind to one or more OpenLDAP-compatible \
    servers. """
    credential: DSCred | None = Field(examples=[
        {
            'credential_type': 'LDAP_PLAIN',
            'binddn': 'uid=truenasserver,ou=Users,dc=ldap01,dc=internal',
            'bindpw': 'Canary'
        },
        {
            'credential_type': 'LDAP_ANONYMOUS'
        },
        {
            'credential_type': 'LDAP_MTLS',
            'client_certificate': 'ldap01_client_cert'
        },
        {
            'credential_type': 'KERBEROS_USER',
            'username': 'truenas_user',
            'password': 'Canary'
        },
        {
            'credential_type': 'KERBEROS_PRINCIPAL',
            'principal': 'truenas@LDAP01.INTERNAL'
        }
    ])
    """ Credential used to bind to the specified directory service. Kerberos credentials are required for Active \
    Directory or IPA domains. Generic LDAP environments support various authentication methods. Available methods \
    depend on the remote LDAP server configuration. If Kerberos credentials are selected for LDAP, GSSAPI binds \
    replace plain LDAP binds. Use Kerberos or mutual TLS authentication when possible for better security. """
    enable: bool
    """ Enable the directory service.

    If TrueNAS has never joined the specified domain (IPA or Active Directory), setting this to True causes TrueNAS to \
    attempt to join the domain.

    NOTE: The domain join process for Active Directory and IPA will make changes to the domain such as creating a new \
    computer account for the TrueNAS server and creating DNS records for TrueNAS. """
    enable_account_cache: bool = Field(default=True)
    """ Enable backend caching for user and group lists. If enabled, then directory services users and groups will be \
    presented as choices in the UI dropdowns and in API responses for user and group queries. This setting also \
    controls whether users and groups appear in getent results. Disable this setting to reduce load on the directory \
    server when necessary. """
    enable_dns_updates: bool = Field(default=True)
    """ Enable automatic DNS updates for the TrueNAS server in the domain via nsupdate and gssapi / TSIG. """
    timeout: int = Field(default=10, ge=5, le=40)
    """ The timeout value for DNS queries that are performed as part of the join process and NETWORK_TIMEOUT for LDAP \
    requests. """
    kerberos_realm: NonEmptyString | None = Field(default=None)
    """ Name of kerberos realm used for authentication to the directory service. If set to null, then Kerberos \
    is not used for binding to the directory service. When joining an Active Directory or IPA domain for the first \
    time, the realm is detected and configured automatically if not specified. """
    configuration: ActiveDirectoryConfig | IPAConfig | LDAPConfig | None = Field(default=None, examples=[
        {
            'computer_account_ou': 'TRUENAS_SERVERS',
            'domain': 'ACME.INTERNAL',
            'hostname': 'TRUENASZ356'
        },
        {
            'hostname': 'TRUENASZ345',
            'target_server': 'ipasrv5.ipadom.internal',
            'domain': 'ipadom.internal',
            'basedn': 'dc=ipadom,dc=internal',
        },
        {
            'server_urls': ['ldap.ipadom.internal'],
            'basedn': 'dc=ipadom,dc=internal',
        }
    ])
    """ The service_type specific configuration for the directory sevices plugin. """


@single_argument_args('directoryservices_update')
class DirectoryServicesUpdateArgs(DirectoryServicesEntry, metaclass=ForUpdateMetaclass):
    """ Update the directory services configuration with the specified payload. If service_type is set to null and \
    enable is false, then the all existing directory service configuration will be cleared.

    About domain joins:
    When you enable IPA or Active Directory for the first time, TrueNAS joins the domain. This requires \
    a KERBEROS_USER credential type for an account with administrator privileges to the domain. This creates \
    a domain account for the TrueNAS server. TrueNAS stores the account credentials in a machine account keytab \
    and uses them for all domain-related actions.

    About disabling directory services or leaving a domain:
    To temporarily disable directory services, set `enable` to `false` with the full configuraiton. \
    This disables directory services but keeps the settings, so you can enable them later.

    To remove all directory service settings, set `enable` to `false and `service_type` to `null`. NOTE: this \
    does not remove the TrueNAS computer account from an Active Directory or IPA domain. If the domain status \
    is `HEALTHY`, use `directoryservices.leave` to remove the account and clear the directory services \
    configuration. """
    id: Excluded = excluded_field()
    force: bool = Field(default=False)
    """ Bypass validation to check if a server with this hostname and NetBIOS name is already registered in an IPA or \
    Active Directory domain. Use this option, for example, to replace an existing server with a TrueNAS server. Do not \
    use the force parameter indiscriminately. Using it may cause production outages for clients that rely on the \
    existing server. """
    def __check_configuration_type(self, service_type, configuration):
        match service_type:
            case 'ACTIVEDIRECTORY':
                if not isinstance(configuration, ActiveDirectoryConfig):
                    raise ValueError('Active Directory configuration is required')
            case 'IPA':
                if not isinstance(configuration, IPAConfig):
                    raise ValueError('IPA configuration is required')

            case 'LDAP':
                if not isinstance(configuration, LDAPConfig):
                    raise ValueError('LDAP configuration is required')

            case None:
                if configuration is not None:
                    raise ValueError('configuration must be set to null when setting service type to null')
            case _:
                raise ValueError(f'{service_type}: unexpected service_type')

    def __check_credential_type(self, service_type, credential_type, has_realm):
        match service_type:
            case 'LDAP':
                if credential_type.startswith('KERBEROS') and not has_realm:
                    raise ValueError(
                        'Kerberos realm is required for using kerberos credentials with a plain LDAP server'
                    )

            case _:
                if credential_type.startswith('LDAP'):
                    raise ValueError('LDAP authentication methods are only supported for the LDAP service type.')

    @model_validator(mode='after')
    def validate_ds(self):
        if self.service_type == undefined and self.enable is not False:
            raise ValueError('service_type is required in update payloads')

        if self.enable is True and self.service_type is not None:
            if self.configuration in (None, undefined):
                raise ValueError('Explicit configuration is required when service_type is specified')

            if self.credential in (None, undefined):
                raise ValueError('Explicit credential configuration is required when service_type is specified')

            self.__check_credential_type(
                self.service_type,
                self.credential.credential_type,
                self.kerberos_realm is not None
            )

        if self.enable is True:
            self.__check_configuration_type(self.service_type, self.configuration)

        return self


class DirectoryServicesUpdateResult(BaseModel):
    result: DirectoryServicesEntry


@single_argument_args('credential')
class DirectoryServicesLeaveArgs(BaseModel):
    credential: CredKRBUser


class DirectoryServicesLeaveResult(BaseModel):
    result: None
