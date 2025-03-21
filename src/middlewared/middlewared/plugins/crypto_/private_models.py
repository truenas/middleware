from typing import Literal

from pydantic import EmailStr, Field

from middlewared.api.base import BaseModel, LongNonEmptyString, NonEmptyString, single_argument_args
from middlewared.api.current import ECCurves


@single_argument_args('certificate_create_acme')
class CertificateCreateACMEArgs(BaseModel):
    name: NonEmptyString
    tos: bool
    csr_id: int
    renew_days: int = Field(ge=1, le=30)
    acme_directory_uri: NonEmptyString
    dns_mapping: dict[str, int]


@single_argument_args('certificate_create_csr')
class CertificateCreateCSRArgs(BaseModel):
    name: NonEmptyString
    # Key specific
    key_length: int | None = None
    key_type: Literal['RSA', 'EC'] = 'RSA'
    ec_curve: Literal[tuple(s.value for s in ECCurves)] = 'SECP384R1'
    passphrase: NonEmptyString | None = None
    # CSR specific
    city: NonEmptyString | None = None
    common: NonEmptyString | None = None
    country: NonEmptyString | None = None
    email: EmailStr | None = None
    organization: NonEmptyString | None = None
    organizational_unit: NonEmptyString | None = None
    state: NonEmptyString | None = None
    digest_algorithm: Literal['SHA224', 'SHA256', 'SHA384', 'SHA512']
    cert_extensions: dict = Field(default_factory=dict)  # FIXME: Improve this
    san: list[NonEmptyString] = Field(min_length=1)


@single_argument_args('certificate_create_csr_imported')
class CertificateCreateImportedCSRArgs(BaseModel):
    name: NonEmptyString
    CSR: LongNonEmptyString
    privatekey: LongNonEmptyString
    passphrase: NonEmptyString | None = None


@single_argument_args('certificate_create_certificate_imported')
class CertificateCreateImportedCertificateArgs(BaseModel):
    name: NonEmptyString
    certificate: LongNonEmptyString
    privatekey: LongNonEmptyString | None
    passphrase: NonEmptyString | None = None


class CertificateCreateInternalResult(BaseModel):
    result: dict
