from typing import Any

from pydantic import EmailStr, Field, field_validator

from middlewared.api.base import BaseModel, LongNonEmptyString, NonEmptyString, single_argument_args
from middlewared.api.base.types import DigestAlgorithm, EkuOID


__all__ = [
    'CryptoKeyGenerateCertificateArgs', 'CryptoKeyGenerateCertificateResult', 'CryptoKeyGenerateSelfSignedCAArgs',
    'CryptoKeyGenerateSelfSignedCAResult', 'CryptoKeyGenerateCAArgs', 'CryptoKeyGenerateCAResult',
    'CryptoKeySignCSRWithCAArgs', 'CryptoKeySignCSRWithCAResult', 'CryptoKeyValidateExtensionArgs',
    'CryptoKeyValidateExtensionResult', 'CertExtensions',
]


class BasicConstraintsExtension(BaseModel):
    ca: bool = False
    enabled: bool = False
    path_length: int | None = None
    extension_critical: bool = False


class AuthorityKeyIdentifierExtension(BaseModel):
    authority_cert_issuer: bool = False
    enabled: bool = False
    extension_critical: bool = False


class ExtendedKeyUsageExtension(BaseModel):
    usages: list[EkuOID] = Field(default_factory=list)
    enabled: bool = False
    extension_critical: bool = False


class KeyUsageExtension(BaseModel):
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


class CertExtensions(BaseModel):
    BasicConstraints: BasicConstraintsExtension = Field(default_factory=BasicConstraintsExtension)
    AuthorityKeyIdentifier: AuthorityKeyIdentifierExtension = Field(default_factory=AuthorityKeyIdentifierExtension)
    ExtendedKeyUsage: ExtendedKeyUsageExtension = Field(default_factory=ExtendedKeyUsageExtension)
    KeyUsage: KeyUsageExtension = Field(default_factory=KeyUsageExtension)


class CertificateCertInfo(BaseModel):
    key_length: int | None = None
    serial: int | None = None
    lifetime: int
    ca_certificate: LongNonEmptyString | None = None
    ca_privatekey: LongNonEmptyString | None = None
    key_type: str | None = None
    ec_curve: str | None = None
    country: str
    state: str
    city: str
    organization: str
    organizational_unit: str | None = None
    common: str | None = None
    email: EmailStr
    digest_algorithm: DigestAlgorithm
    san: list[NonEmptyString]
    cert_extensions: CertExtensions = Field(default_factory=CertExtensions)

    @field_validator('san')
    @classmethod
    def validate_san(cls, v):
        if not v:
            raise ValueError('SAN must be specified')
        return v


class CryptoKeyGenerateCertificateArgs(BaseModel):
    data: CertificateCertInfo


class CryptoKeyGenerateCertificateResult(BaseModel):
    result: Any


class CryptoKeyGenerateSelfSignedCAArgs(BaseModel):
    data: CertificateCertInfo


class CryptoKeyGenerateSelfSignedCAResult(BaseModel):
    result: Any


class CryptoKeyGenerateCAArgs(BaseModel):
    data: CertificateCertInfo


class CryptoKeyGenerateCAResult(BaseModel):
    result: Any


@single_argument_args('cryptokey_sign_csr')
class CryptoKeySignCSRWithCAArgs(BaseModel):
    ca_certificate: LongNonEmptyString
    ca_privatekey: LongNonEmptyString
    csr: LongNonEmptyString
    csr_privatekey: LongNonEmptyString
    serial: int
    digest_algorithm: DigestAlgorithm
    cert_extensions: CertExtensions = Field(default_factory=CertExtensions)


class CryptoKeySignCSRWithCAResult(BaseModel):
    result: Any


@single_argument_args('cryptokey_validate_extension')
class CryptoKeyValidateExtensionArgs(BaseModel):
    cert_extensions: CertExtensions = Field(default_factory=CertExtensions)
    schema: NonEmptyString


class CryptoKeyValidateExtensionResult(BaseModel):
    result: Any
