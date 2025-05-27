import re
from enum import Enum
from typing import Annotated, Literal

from cryptography import x509
from pydantic import AfterValidator, EmailStr, Field, Secret, StringConstraints

from middlewared.api.base import (
    BaseModel, ForUpdateMetaclass, LongString, LongNonEmptyString, match_validator,
    NonEmptyString, single_argument_args,
)


__all__ = [
    'CertificateEntry', 'CertificateCreateArgs', 'CertificateCreateResult',
    'CertificateUpdateArgs', 'CertificateUpdateResult', 'CertificateDeleteArgs', 'CertificateDeleteResult',
    'ECCurves', 'EKU_OID',
]


EKU_OID = Enum('EKU_OID', {i: i for i in dir(x509.oid.ExtendedKeyUsageOID) if not i.startswith('__')})
RE_CERTIFICATE_NAME = re.compile(r'^[a-z0-9_\-]+$', re.I)
CERT_NAME = Annotated[NonEmptyString, AfterValidator(
    match_validator(
        RE_CERTIFICATE_NAME,
        'Name can only contain alphanumeric characters plus dash (-), and underscore (_)',
    )
), StringConstraints(max_length=120)]


class ECCurves(str, Enum):
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
    privatekey: Secret[LongString | None]
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


class BasicConstraintsModel(BaseModel):
    ca: bool = False
    enabled: bool = False
    path_length: int | None = None
    extension_critical: bool = False


class ExtendedKeyUsageModel(BaseModel):
    usages: list[Literal[*[s.value for s in EKU_OID]]] = Field(default_factory=list)
    enabled: bool = False
    extension_critical: bool = False


class KeyUsageModel(BaseModel):
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
    BasicConstraints: BasicConstraintsModel = BasicConstraintsModel()
    ExtendedKeyUsage: ExtendedKeyUsageModel = ExtendedKeyUsageModel()
    KeyUsage: KeyUsageModel = KeyUsageModel()


@single_argument_args('certificate_create')
class CertificateCreateArgs(BaseModel):
    name: CERT_NAME
    create_type: Literal[
        'CERTIFICATE_CREATE_IMPORTED',
        'CERTIFICATE_CREATE_CSR',
        'CERTIFICATE_CREATE_IMPORTED_CSR',
        'CERTIFICATE_CREATE_ACME',
    ]
    add_to_trusted_store: bool = False
    # Fields for importing certs/CSRs
    certificate: LongNonEmptyString | None = None
    privatekey: Secret[LongNonEmptyString | None] = None
    CSR: LongNonEmptyString | None = None
    # Fields used for controlling what type of key is created
    key_length: Literal[2048, 4096] | None = None
    key_type: Literal['RSA', 'EC'] = 'RSA'
    ec_curve: Literal[tuple(s.value for s in ECCurves)] = 'SECP384R1'
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
    cert_extensions: CertificateExtensions = Field(default_factory=CertificateExtensions)
    # ACME related fields
    acme_directory_uri: NonEmptyString | None = None
    """ACME directory URI to be used for ACME certificate creation."""
    csr_id: int | None = None
    """CSR to be used for ACME certificate creation."""
    tos: bool | None = None
    """Set this when creating an ACME certificate to accept terms of service of the ACME service."""
    dns_mapping: dict[str, int] = Field(default_factory=dict)
    """A mapping of domain to ACME DNS Authenticator ID for each domain listed in SAN or common name of the CSR."""
    renew_days: int = Field(ge=1, le=30, default=10)
    """
    Number of days before the certificate expiration date to attempt certificate renewal. If certificate renewal \
    fails, renewal will be reattempted every day until expiration.
    """


class CertificateCreateResult(BaseModel):
    result: CertificateEntry


class CertificateUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    renew_days: int = Field(ge=1, le=30)
    add_to_trusted_store: bool
    name: CERT_NAME


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
