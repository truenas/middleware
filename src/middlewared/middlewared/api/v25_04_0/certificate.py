from typing import Any, Literal

from pydantic import EmailStr, Field, Secret

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, LongNonEmptyString, NonEmptyString, single_argument_args,
)
from middlewared.api.base.types import DigestAlgorithm, EC_CURVES, EC_CURVE_DEFAULT

from .cryptokey import CertExtensions


__all__ = [
    'CertificateEntry', 'CertificateCreateArgs', 'CertificateCreateResult', 'CertificateAcmeCreateArgs',
    'CertificateAcmeCreateResult', 'CertificateAcmeCreateArgs', 'CertificateAcmeCreateResult',
    'CertificateInternalCreateArgs', 'CertificateInternalCreateResult', 'CertificateCSRCreateArgs',
    'CertificateCSRCreateResult', 'CertificateImportedCSRCreateArgs', 'CertificateImportedCSRCreateResult',
    'CertificateImportedCertificateCreateArgs', 'CertificateImportedCertificateCreateResult',
]


class CertificateEntry(BaseModel):
    id: int
    type: int
    name: NonEmptyString
    cert: LongNonEmptyString | None
    privatekey: Secret[LongNonEmptyString | None]
    CSR: LongNonEmptyString | None
    acme_uri: NonEmptyString | None
    domains_authenticators: dict | None
    renew_days: int
    revoked_date: str | None
    signedby: dict | None
    root_path: NonEmptyString
    acme: dict | None
    certificate_path: NonEmptyString | None
    privatekey_path: NonEmptyString | None
    csr_path: NonEmptyString | None
    cert_type: NonEmptyString
    revoked: bool
    expired: bool | None
    issuer: Secret[str | dict | None]
    chain_list: list[LongNonEmptyString]
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
    key_type: str | None
    internal: str | None
    lifetime: int | None
    serial: int | None
    key_length: int | None
    add_to_trusted_store: bool = False  # FIXME: this should probably not be here
    chain: bool | None
    CA_type_existing: bool
    CA_type_internal: bool
    CA_type_intermediate: bool
    cert_type_existing: bool
    cert_type_internal: bool
    cert_type_CSR: bool
    parsed: bool
    can_be_revoked: bool
    extensions: dict
    revoked_certs: list = Field(default_factory=list)
    crl_path: NonEmptyString | None = None
    signed_certificates: int | None = None  # FIXME: This should only be set for CAs


class CertificateCreate(BaseModel):
    tos: bool | None = None
    dns_mapping: dict = Field(default_factory=dict)
    csr_id: int | None = None
    signedby: int | None = None
    key_length: Literal[2048, 4096]
    renew_days: int | None = Field(ge=1, le=30, default=None)
    lifetime: int | None = Field(ge=1, default=None)
    serial: int | None = Field(ge=1, default=None)
    acme_directory_uri: NonEmptyString | None = None
    certificate: LongNonEmptyString | None = None
    city: LongNonEmptyString | None = None
    common: LongNonEmptyString | None = None
    country: NonEmptyString | None = None
    CSR: LongNonEmptyString | None = None
    ec_curve: EC_CURVES = EC_CURVE_DEFAULT
    email: EmailStr | None = None
    key_type: Literal['RSA', 'EC'] = 'RSA'
    name: NonEmptyString
    organization: NonEmptyString | None = None
    organizational_unit: NonEmptyString | None = None
    passphrase: Secret[NonEmptyString | None] = None
    privatekey: Secret[LongNonEmptyString | None] = None
    state: NonEmptyString | None = None
    create_type: Literal[
        'CERTIFICATE_CREATE_INTERNAL', 'CERTIFICATE_CREATE_IMPORTED', 'CERTIFICATE_CREATE_CSR',
        'CERTIFICATE_CREATE_IMPORTED_CSR', 'CERTIFICATE_CREATE_ACME',
    ]
    digest_algorithm: DigestAlgorithm | None = None
    san: list[NonEmptyString] | None = None
    cert_extensions: CertExtensions | None = None
    add_to_trusted_store: bool = False


class CertificateCreateArgs(BaseModel):
    certificate_create: CertificateCreate = Field(default_factory=CertificateCreate)


class CertificateCreateResult(BaseModel):
    result: CertificateEntry


@single_argument_args('certificate_create_acme')
class CertificateAcmeCreateArgs(BaseModel):
    tos: bool = False
    csr_id: int
    renew_days: int = Field(ge=1, le=30, default=10)
    acme_directory_uri: NonEmptyString
    name: NonEmptyString
    dns_mapping: dict


class CertificateAcmeCreateResult(BaseModel):
    result: Any


class CertificateInternalCreate(CertificateCreate):
    lifetime: int
    country: NonEmptyString
    state: NonEmptyString
    city: NonEmptyString
    organization: NonEmptyString
    email: EmailStr
    san: list[NonEmptyString]
    signedby: int
    create_type: Excluded = excluded_field()


class CertificateInternalCreateArgs(BaseModel):
    certificate_create_internal: CertificateInternalCreate


class CertificateInternalCreateResult(BaseModel):
    result: Any


@single_argument_args('certificate_create_CSR')
class CertificateCSRCreateArgs(CertificateInternalCreate):
    signedby: Excluded = excluded_field()
    lifetime: Excluded = excluded_field()


class CertificateCSRCreateResult(BaseModel):
    result: Any


@single_argument_args('create_imported_csr')
class CertificateImportedCSRCreateArgs(BaseModel):
    CSR: LongNonEmptyString
    name: NonEmptyString
    privatekey: Secret[LongNonEmptyString]
    passphrase: Secret[NonEmptyString | None] = None


class CertificateImportedCSRCreateResult(BaseModel):
    result: Any


@single_argument_args('create_imported_certificate')
class CertificateImportedCertificateCreateArgs(BaseModel):
    csr_id: int
    certificate: Secret[LongNonEmptyString]
    name: NonEmptyString
    passphrase: Secret[NonEmptyString | None] = None
    privatekey: Secret[LongNonEmptyString]


class CertificateImportedCertificateCreateResult(BaseModel):
    result: Any
