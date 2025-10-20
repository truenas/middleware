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
    """Unique identifier for this certificate entry."""
    type: int
    """Internal certificate type identifier used to determine certificate capabilities."""
    name: NonEmptyString
    """Human-readable name for this certificate. Must be unique and contain only alphanumeric characters, \
    dashes, and underscores."""
    certificate: LongString | None
    """PEM-encoded X.509 certificate data. `null` for certificate signing requests (CSR) that have not yet \
    been signed."""
    privatekey: Secret[LongString | None]
    """PEM-encoded private key corresponding to the certificate. `null` if no private key is available or for \
    imported certificates without keys."""
    CSR: LongString | None
    """PEM-encoded Certificate Signing Request (CSR) data. `null` for imported certificates or completed \
    ACME certificates."""
    acme_uri: str | None
    """ACME directory server URI used for automated certificate management. `null` for non-ACME certificates."""
    domains_authenticators: dict | None
    """Mapping of domain names to ACME DNS authenticator IDs for domain validation. `null` for non-ACME \
    certificates."""
    renew_days: int | None
    """Number of days before expiration to attempt automatic renewal. Only applicable for ACME certificates. \
    `null` for non-renewable certificates."""
    acme: dict | None
    """ACME registration and account information used for certificate lifecycle management. `null` for \
    non-ACME certificates."""
    add_to_trusted_store: bool
    """Whether this certificate should be added to the system's trusted certificate store."""
    # Normalized fields
    root_path: NonEmptyString
    """Filesystem path where certificate-related files are stored."""
    certificate_path: NonEmptyString | None
    """Filesystem path to the certificate file (.crt). `null` if no certificate is available."""
    privatekey_path: NonEmptyString | None
    """Filesystem path to the private key file (.key). `null` if no private key is available."""
    csr_path: NonEmptyString | None
    """Filesystem path to the certificate signing request file (.csr). `null` if no CSR is available."""
    cert_type: NonEmptyString
    """Human-readable certificate type, typically 'CERTIFICATE' for standard certificates."""
    cert_type_existing: bool
    """Whether this is an existing certificate (imported or generated)."""
    cert_type_CSR: bool
    """Whether this entry represents a Certificate Signing Request (CSR) rather than a signed certificate."""
    cert_type_CA: bool
    """Whether this certificate is a Certificate Authority (CA) certificate."""
    chain_list: list[LongString]
    """Array of PEM-encoded certificates in the certificate chain, starting with the leaf certificate."""
    key_length: int | None
    """Size of the cryptographic key in bits. `null` if key information is unavailable."""
    key_type: NonEmptyString | None
    """Type of cryptographic key algorithm (e.g., 'RSA', 'EC', 'DSA'). `null` if key information is unavailable."""
    # get x509 subject keys
    country: str | None
    """ISO 3166-1 alpha-2 country code from the certificate subject. `null` if not specified."""
    state: str | None
    """State or province name from the certificate subject. `null` if not specified."""
    city: str | None
    """City or locality name from the certificate subject. `null` if not specified."""
    organization: str | None
    """Organization name from the certificate subject. `null` if not specified."""
    organizational_unit: str | None
    """Organizational unit from the certificate subject. `null` if not specified."""
    common: str | None
    """Common name (CN) from the certificate subject. `null` if not specified."""
    san: list[str] | None
    """Subject Alternative Names (SAN) from the certificate extension. `null` if no SAN extension is present."""
    email: str | None
    """Email address from the certificate subject. `null` if not specified."""
    DN: str | None
    """Distinguished Name (DN) of the certificate subject in RFC 2253 format. `null` if certificate parsing failed."""
    subject_name_hash: int | None
    """Hash of the certificate subject name. `null` if certificate parsing failed."""
    extensions: dict
    """X.509 certificate extensions parsed into a dictionary structure."""
    digest_algorithm: str | None
    """Cryptographic hash algorithm used for certificate signing (e.g., 'SHA256'). `null` if unavailable."""
    lifetime: int | None
    """Certificate validity period in seconds. `null` if certificate parsing failed."""
    from_: str | None = Field(alias='from')
    """Certificate validity start date in ISO 8601 format. `null` if certificate parsing failed."""
    until: str | None
    """Certificate validity end date in ISO 8601 format. `null` if certificate parsing failed."""
    serial: int | None
    """Certificate serial number. `null` if certificate parsing failed."""
    chain: bool | None  # FIXME: Check usages and if it is reported correctly now
    """Whether this certificate has an associated certificate chain. `null` if unavailable."""
    fingerprint: str | None
    """SHA-256 fingerprint of the certificate in hexadecimal format. `null` if certificate parsing failed."""
    expired: bool | None
    """Whether the certificate has expired. `null` if certificate parsing failed."""
    # Normalized field
    parsed: bool
    """Whether the certificate data was successfully parsed and validated."""


class BasicConstraintsModel(BaseModel):
    ca: bool = False
    """Whether this certificate is authorized to sign other certificates as a Certificate Authority (CA)."""
    enabled: bool = False
    """Whether the Basic Constraints X.509 extension is present in the certificate."""
    path_length: int | None = None
    """Maximum number of intermediate CA certificates that may follow this certificate in a valid certificate chain. \
    `null` indicates no path length constraint."""
    extension_critical: bool = False
    """Whether the Basic Constraints extension is marked as critical. If `true`, applications that do not understand \
    this extension must reject the certificate."""


class ExtendedKeyUsageModel(BaseModel):
    usages: list[Literal[*[s.value for s in EKU_OID]]] = Field(default_factory=list)
    """Array of Extended Key Usage (EKU) purposes that define what the certificate may be used for \
    (e.g., 'SERVER_AUTH', 'CLIENT_AUTH', 'CODE_SIGNING')."""
    enabled: bool = False
    """Whether the Extended Key Usage X.509 extension is present in the certificate."""
    extension_critical: bool = False
    """Whether the Extended Key Usage extension is marked as critical. If `true`, applications that do not understand \
    this extension must reject the certificate."""


class KeyUsageModel(BaseModel):
    enabled: bool = False
    """Whether the Key Usage X.509 extension is present in the certificate."""
    digital_signature: bool = False
    """Whether the certificate may be used for digital signatures to verify identity or integrity."""
    content_commitment: bool = False
    """Whether the certificate may be used for non-repudiation (proving content commitment)."""
    key_encipherment: bool = False
    """Whether the certificate's public key may be used for encrypting symmetric keys."""
    data_encipherment: bool = False
    """Whether the certificate's public key may be used for directly encrypting raw data."""
    key_agreement: bool = False
    """Whether the certificate's public key may be used for key agreement protocols (e.g., Diffie-Hellman)."""
    key_cert_sign: bool = False
    """Whether the certificate may be used to sign other certificates (CA functionality)."""
    crl_sign: bool = False
    """Whether the certificate may be used to sign Certificate Revocation Lists (CRLs)."""
    encipher_only: bool = False
    """Whether the public key may only be used for encryption when `key_agreement` is also set."""
    decipher_only: bool = False
    """Whether the public key may only be used for decryption when `key_agreement` is also set."""
    extension_critical: bool = False
    """Whether the Key Usage extension is marked as critical. If `true`, applications that do not understand \
    this extension must reject the certificate."""


class CertificateExtensions(BaseModel):
    BasicConstraints: BasicConstraintsModel = BasicConstraintsModel()
    """Basic Constraints extension configuration for certificate authority capabilities."""
    ExtendedKeyUsage: ExtendedKeyUsageModel = ExtendedKeyUsageModel()
    """Extended Key Usage extension configuration specifying certificate purposes."""
    KeyUsage: KeyUsageModel = KeyUsageModel()
    """Key Usage extension configuration defining permitted cryptographic operations."""


@single_argument_args('certificate_create')
class CertificateCreateArgs(BaseModel):
    name: CERT_NAME
    """Certificate name."""
    create_type: Literal[
        'CERTIFICATE_CREATE_IMPORTED',
        'CERTIFICATE_CREATE_CSR',
        'CERTIFICATE_CREATE_IMPORTED_CSR',
        'CERTIFICATE_CREATE_ACME',
    ]
    """Type of certificate creation operation."""
    add_to_trusted_store: bool = False
    """Whether to add this certificate to the trusted certificate store."""
    # Fields for importing certs/CSRs
    certificate: LongNonEmptyString | None = None
    """PEM-encoded certificate to import or `null`."""
    privatekey: Secret[LongNonEmptyString | None] = None
    """PEM-encoded private key to import or `null`."""
    CSR: LongNonEmptyString | None = None
    """PEM-encoded certificate signing request to import or `null`."""
    # Fields used for controlling what type of key is created
    key_length: Literal[2048, 4096] | None = None
    """RSA key length in bits or `null`."""
    key_type: Literal['RSA', 'EC'] = 'RSA'
    """Type of cryptographic key to generate."""
    ec_curve: Literal[tuple(s.value for s in ECCurves)] = 'SECP384R1'
    """Elliptic curve to use for EC keys."""
    passphrase: NonEmptyString | None = None
    """Passphrase to protect the private key or `null`."""
    # Fields for creating a CSR
    city: NonEmptyString | None = None
    """City or locality name for certificate subject or `null`."""
    common: NonEmptyString | None = None
    """Common name for certificate subject or `null`."""
    country: NonEmptyString | None = None
    """Country name for certificate subject or `null`."""
    email: EmailStr | None = None
    """Email address for certificate subject or `null`."""
    organization: NonEmptyString | None = None
    """Organization name for certificate subject or `null`."""
    organizational_unit: NonEmptyString | None = None
    """Organizational unit for certificate subject or `null`."""
    state: NonEmptyString | None = None
    """State or province name for certificate subject or `null`."""
    digest_algorithm: Literal['SHA224', 'SHA256', 'SHA384', 'SHA512'] = 'SHA256'
    """Hash algorithm for certificate signing."""
    san: list[NonEmptyString] = Field(default_factory=list)
    """Subject alternative names for the certificate."""
    cert_extensions: CertificateExtensions = Field(default_factory=CertificateExtensions)
    """Certificate extensions configuration."""
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
    """The created certificate configuration."""


class CertificateUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    renew_days: int = Field(ge=1, le=30)
    """Days before expiration to attempt renewal."""
    add_to_trusted_store: bool
    """Whether to add this certificate to the trusted certificate store."""
    name: CERT_NAME
    """Certificate name."""


class CertificateUpdateArgs(BaseModel):
    id: int
    """ID of the certificate to update."""
    certificate_update: CertificateUpdate = CertificateUpdate()
    """Updated certificate configuration data."""


class CertificateUpdateResult(BaseModel):
    result: CertificateEntry
    """The updated certificate configuration."""


class CertificateDeleteArgs(BaseModel):
    id: int
    """ID of the certificate to delete."""
    force: bool = False
    """Whether to force deletion even if certificate is in use."""


class CertificateDeleteResult(BaseModel):
    result: bool
    """Returns `true` when the certificate is successfully deleted."""
