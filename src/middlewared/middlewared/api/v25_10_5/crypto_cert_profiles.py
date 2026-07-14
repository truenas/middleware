from typing import final

from middlewared.api.base import BaseModel

from pydantic import Field

__all__ = (
    "WebUICryptoCsrProfilesArgs",
    "CSRProfilesModel",
    "WebUICryptoCsrProfilesResult",
)


# Defines the default lifetime of a certificate
# (https://support.apple.com/en-us/HT211025)
DEFAULT_LIFETIME_DAYS = 397
RSA = "RSA"
EC = "EC"
EC_CURVE = "SECP384R1"
SHA256 = "SHA256"
KEY_LENGTH = 2048
EX_KEY_USAGE = ["SERVER_AUTH", "CLIENT_AUTH"]


@final
class BasicConstraintsModel(BaseModel):
    enabled: bool = True
    """Whether the basic constraints extension is enabled."""
    ca: bool = False
    """Whether this certificate can act as a certificate authority."""
    extension_critical: bool = True
    """Whether this extension is marked as critical."""


@final
class ExtendedKeyUsageModel(BaseModel):
    # These days, most TLS certs want "ClientAuth".
    # LetsEncrypt appears to want this extension to issue.
    # https://community.letsencrypt.org/t/extendedkeyusage-tls-client-
    # authentication-in-tls-server-certificates/59140/7
    enabled: bool = True
    """Whether the extended key usage extension is enabled."""
    extension_critical: bool = True
    """Whether this extension is marked as critical."""
    usages: list[str] = EX_KEY_USAGE
    """Array of extended key usage purposes for the certificate."""


@final
class RSAKeyUsageModel(BaseModel):
    # RSA certs need "digitalSignature" for DHE,
    # and "keyEncipherment" for nonDHE
    # Include "keyAgreement" for compatibility (DH_DSS / DH_RSA)
    # See rfc5246
    enabled: bool = True
    """Whether the key usage extension is enabled."""
    extension_critical: bool = True
    """Whether this extension is marked as critical."""
    digital_signature: bool = True
    """Whether the key can be used for digital signatures."""
    key_encipherment: bool = True
    """Whether the key can be used for key encipherment."""
    key_agreement: bool = True
    """Whether the key can be used for key agreement."""


@final
class ECCKeyUsageModel(BaseModel):
    # keyAgreement is not generally required for EC certs.
    # See Google, cloudflare certs
    enabled: bool = True
    """Whether the key usage extension is enabled."""
    extension_critical: bool = True
    """Whether this extension is marked as critical."""
    digital_signature: bool = True
    """Whether the key can be used for digital signatures."""


@final
class RSACSRExtensionsModel(BaseModel):
    BasicConstraints: BasicConstraintsModel = BasicConstraintsModel()
    """Basic constraints extension configuration."""
    ExtendedKeyUsage: ExtendedKeyUsageModel = ExtendedKeyUsageModel()
    """Extended key usage extension configuration."""
    KeyUsage: RSAKeyUsageModel = RSAKeyUsageModel()
    """Key usage extension configuration for RSA certificates."""


@final
class ECCCSRExtensionsModel(BaseModel):
    BasicConstraints: BasicConstraintsModel = BasicConstraintsModel()
    """Basic constraints extension configuration."""
    ExtendedKeyUsage: ExtendedKeyUsageModel = ExtendedKeyUsageModel()
    """Extended key usage extension configuration."""
    KeyUsage: ECCKeyUsageModel = ECCKeyUsageModel()
    """Key usage extension configuration for ECC certificates."""


@final
class RSACSRExtensions(BaseModel):
    cert_extensions: RSACSRExtensionsModel = RSACSRExtensionsModel()
    """Certificate extensions configuration for RSA certificates."""
    key_length: int = KEY_LENGTH
    """RSA key length in bits."""
    key_type: str = RSA
    """Type of cryptographic key (RSA)."""
    lifetime: int = DEFAULT_LIFETIME_DAYS
    """Certificate validity period in days."""
    digest_algorithm: str = SHA256
    """Hash algorithm for certificate signing."""


@final
class ECCCSRExtensions(BaseModel):
    cert_extensions: ECCCSRExtensionsModel = ECCCSRExtensionsModel()
    """Certificate extensions configuration for ECC certificates."""
    ec_curve: str = EC_CURVE
    """Elliptic curve to use for key generation."""
    key_type: str = EC
    """Type of cryptographic key (ECC)."""
    lifetime: int = DEFAULT_LIFETIME_DAYS
    """Certificate validity period in days."""
    digest_algorithm: str = SHA256
    """Hash algorithm for certificate signing."""


@final
class CSRProfilesModel(BaseModel):
    https_rsa_certificate: RSACSRExtensions = Field(
        default_factory=RSACSRExtensions, alias="HTTPS RSA Certificate"
    )
    """Certificate profile configuration for HTTPS RSA certificates."""
    https_ecc_certificate: ECCCSRExtensions = Field(
        default_factory=ECCCSRExtensions, alias="HTTPS ECC Certificate"
    )
    """Certificate profile configuration for HTTPS ECC certificates."""


class WebUICryptoCsrProfilesArgs(BaseModel):
    pass


@final
class WebUICryptoCsrProfilesResult(BaseModel):
    result: CSRProfilesModel = CSRProfilesModel()
    """Predefined certificate profiles for common use cases."""
