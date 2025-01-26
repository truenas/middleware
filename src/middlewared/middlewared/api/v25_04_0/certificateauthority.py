from typing import Any, Literal

from pydantic import EmailStr, Field

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongNonEmptyString, NonEmptyString, single_argument_args,
)
from middlewared.api.base.types import EkuOID

from .certificate import CertificateEntry, CertificateCreate
from .cryptokey import BasicConstraintsExtension, CertExtensions, ExtendedKeyUsageExtension, KeyUsageExtension


__all__ = [
    'CertificateAuthorityEntry', 'CertificateAuthorityCreateArgs', 'CertificateAuthorityCreateResult',
    'CertificateAuthorityCreateInternalArgs', 'CertificateAuthorityCreateInternalResult',
    'CertificateAuthorityCreateIntermediateCAArgs', 'CertificateAuthorityCreateIntermediateCAResult',
    'CertificateAuthorityUpdateArgs', 'CertificateAuthorityUpdateResult', 'CertificateAuthorityDeleteArgs',
    'CertificateAuthorityDeleteResult',
]


class CertificateAuthorityEntry(CertificateEntry):
    signed_certificates: int


class CACertExtensions(CertExtensions):
    BasicConstraints: BasicConstraintsExtension = Field(
        default_factory=lambda: BasicConstraintsExtension(enabled=True, ca=True, extension_critical=True),
    )

    KeyUsage: KeyUsageExtension = Field(
        default_factory=lambda: KeyUsageExtension(
            enabled=True, key_cert_sign=True, crl_sign=True, extension_critical=True,
        )
    )

    ExtendedKeyUsage: ExtendedKeyUsageExtension = Field(
        default_factory=lambda: ExtendedKeyUsageExtension(enabled=True, usages=[EkuOID.SERVER_AUTH])
    )


class CertificateAuthorityCreate(CertificateCreate):
    create_type: Literal['CA_CREATE_INTERNAL', 'CA_CREATE_IMPORTED', 'CA_CREATE_INTERMEDIATE']
    cert_extensions: CACertExtensions = Field(default_factory=CACertExtensions)
    dns_mapping: Excluded = excluded_field()


class CertificateAuthorityCreateArgs(BaseModel):
    ca_data: CertificateAuthorityCreate = Field(default_factory=CertificateAuthorityCreate)


class CertificateAuthorityCreateResult(BaseModel):
    result: CertificateAuthorityEntry


class CertificateAuthorityCreateInternal(CertificateAuthorityCreate):
    lifetime: int
    country: NonEmptyString
    state: NonEmptyString
    city: NonEmptyString
    organization: NonEmptyString
    email: EmailStr
    san: list[NonEmptyString]
    create_type: Excluded = excluded_field()


class CertificateAuthorityCreateInternalArgs(BaseModel):
    ca_data: CertificateAuthorityCreateInternal


class CertificateAuthorityCreateInternalResult(BaseModel):
    result: Any


@single_argument_args('certificate_create_intermediate_ca')
class CertificateAuthorityCreateIntermediateCAArgs(CertificateAuthorityCreateInternal):
    signedby: int


class CertificateAuthorityCreateIntermediateCAResult(BaseModel):
    result: Any


@single_argument_args('certificate_create_imported_ca')
class CertificateAuthorityCreateImportedCAArgs(CertificateAuthorityCreate):
    certificate: LongNonEmptyString
    create_type: Excluded = excluded_field()


class CertificateAuthorityCreateImportedCAResult(BaseModel):
    result: Any


class CertificateAuthorityUpdateOptions(BaseModel, metaclass=ForUpdateMetaclass):
    revoked: bool
    add_to_trusted_store: bool
    name: NonEmptyString


class CertificateAuthorityUpdateArgs(BaseModel):
    id: int
    options: CertificateAuthorityUpdateOptions = Field(default_factory=CertificateAuthorityUpdateOptions)


class CertificateAuthorityUpdateResult(BaseModel):
    result: CertificateAuthorityEntry


class CertificateAuthorityDeleteArgs(BaseModel):
    id: int


class CertificateAuthorityDeleteResult(BaseModel):
    result: Literal[True]
