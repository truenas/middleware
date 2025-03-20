from enum import Enum
from typing import Literal

from cryptography import x509
from pydantic import EmailStr, Field

from middlewared.api.base import (
    BaseModel, ForUpdateMetaclass, LongString, LongNonEmptyString, NonEmptyString, single_argument_args,
)


__all__ = [
    'CertificateEntry', 'CertificateCreateArgs', 'CertificateCreateResult',
    'CertificateUpdateArgs', 'CertificateUpdateResult', 'CertificateDeleteArgs', 'CertificateDeleteResult',
    'ECCurve', 'EKU_OID',
]


EKU_OID = Enum('EKU_OID', {i: i for i in dir(x509.oid.ExtendedKeyUsageOID) if not i.startswith('__')})

class ECCurve(str, Enum):
    SECP256R1 = 'SECP256R1'
    SECP384R1 = 'SECP384R1'
    SECP521R1 = 'SECP521R1'
    ED25519 = 'ed25519'


class CertificateEntry(BaseModel):
    # DB Fields
    id: int
    type: int
    name: NonEmptyString
    certificate: LongString | None
    privatekey: LongString | None
    CSR: LongString | None
    acme_uri: str | None
    domains_authenticators: dict | None
    renew_days: int | None
    acme: dict | None
    add_to_trusted_store: bool
    # Normalized fields
    root_path: NonEmptyString
    certificate_path: NonEmptyString | None
    privatekey_path: NonEmptyString | None
    csr_path: NonEmptyString | None
    cert_type: NonEmptyString
    cert_type_existing: bool
    cert_type_CSR: bool
    chain_list: list[LongString]
    key_length: int | None
    key_type: NonEmptyString | None
    # get x509 subject keys
    country: str | None
    state: str | None
    city: str | None
    organization: str | None
    organizational_unit: str | None
    common: str | None
    san: list[str] | None
    email: str | None
    DN: str | None
    subject_name_hash: int | None
    extensions: dict
    digest_algorithm: str | None
    lifetime: int | None
    from_: str | None = Field(alias='from')
    until: str | None
    serial: int | None
    chain: bool | None  # FIXME: Check usages and if it is reported correctly now
    fingerprint: str | None
    expired: bool | None
    # Normalized field
    parsed: bool


class BasicConstraints(BaseModel):
    ca: bool = False
    enabled: bool = False
    path_length: int | None = None
    extension_critical: bool = False


class ExtendedKeyUsage(BaseModel):
    usages: list[Literal[tuple(s.value for s in EKU_OID)]]
    enabled: bool = False
    extension_critical: bool = False


class KeyUsage(BaseModel):
    enabled: bool = False
    digital_signature: bool = False
    content_commitment: bool = False
    key_encipherment: bool = False
    data_encipherment: bool = False
    key_agreement: bool = False
    key_cert_sign: bool = False
    crl_sign: bool = False
    encipher_only: bool = False
    decipher_only: bool = False
    extension_critical: bool = False


class CertificateExtensions(BaseModel):
    BasicConstraints: BasicConstraints = BasicConstraints()
    ExtendedKeyUsage: ExtendedKeyUsage = ExtendedKeyUsage()
    KeyUsage: KeyUsage = KeyUsage()


@single_argument_args('certificate_create')
class CertificateCreateArgs(BaseModel):
    name: NonEmptyString  # TODO: Add regex
    create_type: Literal[
        'CERTIFICATE_CREATE_IMPORTED',
        'CERTIFICATE_CREATE_CSR',
        'CERTIFICATE_CREATE_IMPORTED_CSR',
        'CERTIFICATE_CREATE_ACME',
    ]
    add_to_trusted_store: bool = False
    # Fields for importing certs/CSRs
    certificate: LongNonEmptyString | None = None
    privatekey: LongNonEmptyString | None = None
    CSR: LongNonEmptyString | None = None
    # Fields used for controlling what type of key is created
    key_length: int | None = None  # FIXME: Validate key length
    key_type: Literal['RSA', 'EC'] = 'RSA'
    ec_curve: Literal[tuple(s.value for s in ECCurve)] = 'SECP384R1'
    passphrase: NonEmptyString | None = None
    # Fields for creating a CSR
    city: NonEmptyString | None = None
    common: NonEmptyString | None = None
    country: NonEmptyString | None = None
    email: EmailStr | None = None
    organization: NonEmptyString | None = None
    organizational_unit: NonEmptyString | None = None
    state: NonEmptyString | None = None
    digest_algorithm: Literal['SHA224', 'SHA256', 'SHA384', 'SHA512'] = 'SHA256'
    san: list[NonEmptyString] = Field(default_factory=list)
    cert_extensions: CertificateExtensions = CertificateExtensions()
    # ACME related fields
    acme_directory_uri: NonEmptyString | None = None
    '''
    ACME directory URI to be used for ACME cert creation.
    '''
    csr_id: int | None = None
    '''
    CSR to be used for ACME cert creation.
    '''
    tos: bool | None = None
    '''
    Set this when creating an ACME cert to accept terms of service of the ACME service.
    '''
    dns_mapping: dict[str, int] = Field(default_factory=dict)
    '''
    For each domain listed in SAN or common name of the CSR, this field should have a mapping of domain to ACME
    DNS Authenticator ID.
    '''
    renew_days: int = Field(min_length=1, max_length=30, default=10)
    '''
    If a cert is expiring on 30th day, and this field is set to 10. System will attempt to renew the cert on 20th day
    and if it fails will continue doing so until it expires.
    '''


class CertificateCreateResult(BaseModel):
    result: CertificateEntry


class CertificateUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    renew_days: int = Field(min_length=1, max_length=30)
    add_to_trusted_store: bool
    name: NonEmptyString


class CertificateUpdateArgs(BaseModel):
    id: int
    certificate_update: CertificateUpdate = CertificateUpdate()


class CertificateUpdateResult(BaseModel):
    result: CertificateEntry


class CertificateDeleteArgs(BaseModel):
    id: int
    force: bool = False


class CertificateDeleteResult(BaseModel):
    result: bool
