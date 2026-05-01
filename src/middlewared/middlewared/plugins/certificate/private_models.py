from __future__ import annotations

from typing import Any, Literal

from pydantic import EmailStr, Field

from middlewared.api.base import BaseModel, LongNonEmptyString, NonEmptyString


__all__ = (
    'CertificateCreateImportedCertificatePayload',
    'CertificateCreateImportedCSRPayload',
    'CertificateCreateCSRPayload',
    'CertificateCreateACMEPayload',
)


class CertificateCreateImportedCertificatePayload(BaseModel):
    name: NonEmptyString
    certificate: LongNonEmptyString
    privatekey: LongNonEmptyString | None = None
    passphrase: NonEmptyString | None = None


class CertificateCreateImportedCSRPayload(BaseModel):
    name: NonEmptyString
    CSR: LongNonEmptyString
    privatekey: LongNonEmptyString
    passphrase: NonEmptyString | None = None


class CertificateCreateCSRPayload(BaseModel):
    name: NonEmptyString
    key_length: int | None = None
    key_type: Literal['RSA', 'EC'] = 'RSA'
    ec_curve: Literal['SECP256R1', 'SECP384R1', 'SECP521R1', 'ed25519'] = 'SECP384R1'
    passphrase: NonEmptyString | None = None
    city: NonEmptyString | None = None
    common: NonEmptyString | None = None
    country: NonEmptyString | None = None
    email: EmailStr | None = None
    organization: NonEmptyString | None = None
    organizational_unit: NonEmptyString | None = None
    state: NonEmptyString | None = None
    digest_algorithm: Literal['SHA224', 'SHA256', 'SHA384', 'SHA512']
    cert_extensions: dict[str, Any] = Field(default_factory=dict)
    san: list[NonEmptyString] = Field(min_length=1)


class CertificateCreateACMEPayload(BaseModel):
    name: NonEmptyString
    tos: bool
    csr_id: int
    renew_days: int = Field(ge=1, le=30)
    acme_directory_uri: NonEmptyString
    dns_mapping: dict[str, int]
