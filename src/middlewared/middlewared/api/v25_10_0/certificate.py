from enum import Enum
from typing import Literal

from pydantic import EmailStr, Field

from middlewared.api.base import (
    BaseModel, single_argument_args, ForUpdateMetaclass, LongString, LongNonEmptyString, NonEmptyString,
)


__all__ = [
    'CertificateEntry', 'CertificateCreateArgs', 'CertificateCreateResult',
]


class ECCurve(str, Enum):
    SECP256R1 = 'SECP256R1'
    SECP384R1 = 'SECP384R1'
    SECP521R1 = 'SECP521R1'
    ED25519 = 'ed25519'


class CertificateEntry(BaseModel):
    id: int
    type: int
    name: NonEmptyString
    certificate: LongString | None
    privatekey: LongString | None
    CSR: LongString | None
    acme_uri: str | None
    domains_authenticators: dict | None
    renew_days: int
    root_path: NonEmptyString
    acme: dict | None
    certificate_path: NonEmptyString | None
    privatekey_path: NonEmptyString | None
    csr_path: NonEmptyString | None
    cert_type: NonEmptyString
    expired: bool | None
    chain_list: list[str]
    country: str | None
    state: str | None
    city: str | None
    organization: str | None
    organizational_unit: str | None
    san: list[str] | None
    email: str | None
    DN: str | None
    subject_name_hash: str | None
    digest_algorithm: str | None
    from_: str | None = Field(alias='from')
    common: str | None
    until: str | None
    fingerprint: str | None
    key_type: NonEmptyString | None
    lifetime: int | None
    serial: int | None
    key_length: int | None
    add_to_trusted_store: bool
    chain: bool | None  # FIXME: Check usages and if it is reported correctly now
    cert_type_existing: bool
    cert_type_CSR: bool
    parsed: bool
    extensions: dict


class CertificateCreate(BaseModel):
    name: NonEmptyString
    create_type: Literal[
        'CERTIFICATE_CREATE_IMPORTED',
        'CERTIFICATE_CREATE_CSR',
        'CERTIFICATE_CREATE_IMPORTED_CSR',
        'CERTIFICATE_CREATE_ACME',
    ]
    add_to_trusted_store: bool
    # Fields for importing certs/CSRs
    certificate: LongNonEmptyString | None = None
    privatekey: LongNonEmptyString | None = None
    CSR: LongNonEmptyString | None = None
    # Fields used for controlling what type of key is created
    key_length: Literal[2046, 4098, None] = None
    key_type: Literal['RSA', 'EC'] = 'RSA'
    ec_curve: ECCurve = 'SECP384R1'
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
    cert_extensions: dict = Field(default_factory=dict)  # FIXME: Improve this
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


class CertificateCreateArgs(BaseModel):
    data: CertificateCreate = CertificateCreate()


class CertificateCreateResult(BaseModel):
    result: CertificateEntry
