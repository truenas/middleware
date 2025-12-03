from middlewared.api.base import (
    BaseModel,
    excluded_field,
    Excluded,
    ForUpdateMetaclass,
    LongNonEmptyString,
    NonEmptyString,
    single_argument_args,
)
from middlewared.utils.directoryservices.krb5_conf import KRB5ConfSection, parse_krb_aux_params
from pydantic import field_validator, Secret

__all__ = [
    'KerberosEntry', 'KerberosRealmEntry', 'KerberosKeytabEntry',
    'KerberosUpdateArgs', 'KerberosUpdateResult',
    'KerberosRealmCreateArgs', 'KerberosRealmCreateResult',
    'KerberosRealmUpdateArgs', 'KerberosRealmUpdateResult',
    'KerberosRealmDeleteArgs', 'KerberosRealmDeleteResult',
    'KerberosKeytabCreateArgs', 'KerberosKeytabCreateResult',
    'KerberosKeytabUpdateArgs', 'KerberosKeytabUpdateResult',
    'KerberosKeytabDeleteArgs', 'KerberosKeytabDeleteResult',
]


class KerberosEntry(BaseModel):
    id: int
    """Unique identifier for the Kerberos configuration."""
    appdefaults_aux: str
    """
    Advanced field for manually setting additional parameters inside the \
    appdefaults section of the krb5.conf file. These are generally not required \
    as the required krb5.conf settings are automatically detected and set \
    for the environment. See manpage for MIT krb5.conf.
    """
    libdefaults_aux: str
    """
    Advanced field for manually setting additional parameters inside the \
    libdefaults section of the krb5.conf file. These are generally not required \
    as the required krb5.conf settings are automatically detected and set \
    for the environment. See manpage for MIT krb5.conf.
    """

    @field_validator('appdefaults_aux')
    @classmethod
    def validate_appdefaults(cls, v):
        parse_krb_aux_params(KRB5ConfSection.APPDEFAULTS, {}, v)
        return v

    @field_validator('libdefaults_aux')
    @classmethod
    def validate_libdefaults(cls, v):
        parse_krb_aux_params(KRB5ConfSection.LIBDEFAULTS, {}, v)
        return v


class KerberosRealmEntry(BaseModel):
    id: int
    """Unique identifier for the Kerberos realm configuration."""
    realm: NonEmptyString
    """
    Kerberos realm name. This is external to TrueNAS and is case-sensitive. \
    The general convention for kerberos realms is that they are upper-case.
    """
    primary_kdc: NonEmptyString | None = None
    """ The master Kerberos domain controller for this realm. TrueNAS uses this as a fallback if it cannot get \
    credentials because of an invalid password. This can help in environments where the domain uses a hub-and-spoke \
    topology. Use this setting to reduce credential errors after TrueNAS automatically changes its machine password. """
    kdc: list[NonEmptyString] = []
    """
    List of kerberos domain controllers. If the list is empty then the kerberos \
    libraries will use DNS to look up KDCs. In some situations this is undesirable \
    as kerberos libraries are, for intance, not active directory site aware and so \
    may be suboptimal.
    """
    admin_server: list[NonEmptyString] = []
    """
    List of kerberos admin servers. If the list is empty then the kerberos \
    libraries will use DNS to look them up.
    """
    kpasswd_server: list[NonEmptyString] = []
    """
    List of kerberos kpasswd servers. If the list is empty then DNS will be used \
    to look them up if needed.
    """


class KerberosKeytabEntry(BaseModel):
    id: int
    """Unique identifier for the Kerberos keytab entry."""
    name: NonEmptyString
    """
    Name of the kerberos keytab entry. This is an identifier for the keytab and not \
    the name of the keytab file. Some names are used for internal purposes such \
    as AD_MACHINE_ACCOUNT and IPA_MACHINE_ACCOUNT.
    """
    file: Secret[LongNonEmptyString | None]
    """ Base64 encoded kerberos keytab entries to append to the system keytab. """


@single_argument_args('kerberos_update')
class KerberosUpdateArgs(KerberosEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class KerberosUpdateResult(BaseModel):
    result: KerberosEntry
    """The updated Kerberos configuration."""


class KerberosRealmCreate(KerberosRealmEntry):
    id: Excluded = excluded_field()


class KerberosRealmCreateArgs(BaseModel):
    data: KerberosRealmCreate
    """Kerberos realm configuration data for creation."""


class KerberosRealmCreateResult(BaseModel):
    result: KerberosRealmEntry
    """The created Kerberos realm configuration."""


class KerberosRealmUpdate(KerberosRealmCreate, metaclass=ForUpdateMetaclass):
    pass


class KerberosRealmUpdateArgs(BaseModel):
    id: int
    """ID of the Kerberos realm to update."""
    data: KerberosRealmUpdate
    """Updated Kerberos realm configuration data."""


class KerberosRealmUpdateResult(BaseModel):
    result: KerberosRealmEntry
    """The updated Kerberos realm configuration."""


class KerberosRealmDeleteArgs(BaseModel):
    id: int
    """ID of the Kerberos realm to delete."""


class KerberosRealmDeleteResult(BaseModel):
    result: None
    """Returns `null` when the Kerberos realm is successfully deleted."""


class KerberosKeytabCreate(KerberosKeytabEntry):
    id: Excluded = excluded_field()


class KerberosKeytabCreateArgs(BaseModel):
    data: KerberosKeytabCreate
    """Kerberos keytab configuration data for creation."""


class KerberosKeytabCreateResult(BaseModel):
    result: KerberosKeytabEntry
    """The created Kerberos keytab entry."""


class KerberosKeytabUpdate(KerberosKeytabCreate, metaclass=ForUpdateMetaclass):
    pass


class KerberosKeytabUpdateArgs(BaseModel):
    id: int
    """ID of the Kerberos keytab entry to update."""
    data: KerberosKeytabUpdate
    """Updated Kerberos keytab configuration data."""


class KerberosKeytabUpdateResult(BaseModel):
    result: KerberosKeytabEntry
    """The updated Kerberos keytab entry."""


class KerberosKeytabDeleteArgs(BaseModel):
    id: int
    """ID of the Kerberos keytab entry to delete."""


class KerberosKeytabDeleteResult(BaseModel):
    result: None
    """Returns `null` when the Kerberos keytab entry is successfully deleted."""
