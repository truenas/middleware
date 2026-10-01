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
    enabled: bool = Field(default=True, description="Whether the basic constraints extension is enabled.")
    ca: bool = Field(default=False, description="Whether this certificate can act as a certificate authority.")
    extension_critical: bool = Field(default=True, description="Whether this extension is marked as critical.")


@final
class ExtendedKeyUsageModel(BaseModel):
    # These days, most TLS certs want "ClientAuth".
    # LetsEncrypt appears to want this extension to issue.
    # https://community.letsencrypt.org/t/extendedkeyusage-tls-client-
    # authentication-in-tls-server-certificates/59140/7
    enabled: bool = Field(default=True, description="Whether the extended key usage extension is enabled.")
    extension_critical: bool = Field(default=True, description="Whether this extension is marked as critical.")
    usages: list[str] = Field(
        default=EX_KEY_USAGE,
        description="Array of extended key usage purposes for the certificate.",
    )


@final
class RSAKeyUsageModel(BaseModel):
    # RSA certs need "digitalSignature" for DHE,
    # and "keyEncipherment" for nonDHE
    # Include "keyAgreement" for compatibility (DH_DSS / DH_RSA)
    # See rfc5246
    enabled: bool = Field(default=True, description="Whether the key usage extension is enabled.")
    extension_critical: bool = Field(default=True, description="Whether this extension is marked as critical.")
    digital_signature: bool = Field(default=True, description="Whether the key can be used for digital signatures.")
    key_encipherment: bool = Field(default=True, description="Whether the key can be used for key encipherment.")
    key_agreement: bool = Field(default=True, description="Whether the key can be used for key agreement.")


@final
class ECCKeyUsageModel(BaseModel):
    # keyAgreement is not generally required for EC certs.
    # See Google, cloudflare certs
    enabled: bool = Field(default=True, description="Whether the key usage extension is enabled.")
    extension_critical: bool = Field(default=True, description="Whether this extension is marked as critical.")
    digital_signature: bool = Field(default=True, description="Whether the key can be used for digital signatures.")


@final
class RSACSRExtensionsModel(BaseModel):
    BasicConstraints: BasicConstraintsModel = Field(
        default=BasicConstraintsModel(),
        description="Basic constraints extension configuration.",
    )
    ExtendedKeyUsage: ExtendedKeyUsageModel = Field(
        default=ExtendedKeyUsageModel(),
        description="Extended key usage extension configuration.",
    )
    KeyUsage: RSAKeyUsageModel = Field(
        default=RSAKeyUsageModel(),
        description="Key usage extension configuration for RSA certificates.",
    )


@final
class ECCCSRExtensionsModel(BaseModel):
    BasicConstraints: BasicConstraintsModel = Field(
        default=BasicConstraintsModel(),
        description="Basic constraints extension configuration.",
    )
    ExtendedKeyUsage: ExtendedKeyUsageModel = Field(
        default=ExtendedKeyUsageModel(),
        description="Extended key usage extension configuration.",
    )
    KeyUsage: ECCKeyUsageModel = Field(
        default=ECCKeyUsageModel(),
        description="Key usage extension configuration for ECC certificates.",
    )


@final
class RSACSRExtensions(BaseModel):
    cert_extensions: RSACSRExtensionsModel = Field(
        default=RSACSRExtensionsModel(),
        description="Certificate extensions configuration for RSA certificates.",
    )
    key_length: int = Field(default=KEY_LENGTH, description="RSA key length in bits.")
    key_type: str = Field(default=RSA, description="Type of cryptographic key (RSA).")
    lifetime: int = Field(default=DEFAULT_LIFETIME_DAYS, description="Certificate validity period in days.")
    digest_algorithm: str = Field(default=SHA256, description="Hash algorithm for certificate signing.")


@final
class ECCCSRExtensions(BaseModel):
    cert_extensions: ECCCSRExtensionsModel = Field(
        default=ECCCSRExtensionsModel(),
        description="Certificate extensions configuration for ECC certificates.",
    )
    ec_curve: str = Field(default=EC_CURVE, description="Elliptic curve to use for key generation.")
    key_type: str = Field(default=EC, description="Type of cryptographic key (ECC).")
    lifetime: int = Field(default=DEFAULT_LIFETIME_DAYS, description="Certificate validity period in days.")
    digest_algorithm: str = Field(default=SHA256, description="Hash algorithm for certificate signing.")


@final
class CSRProfilesModel(BaseModel):
    https_rsa_certificate: RSACSRExtensions = Field(
        default_factory=RSACSRExtensions,
        alias="HTTPS RSA Certificate",
        description="Certificate profile configuration for HTTPS RSA certificates.",
    )
    https_ecc_certificate: ECCCSRExtensions = Field(
        default_factory=ECCCSRExtensions,
        alias="HTTPS ECC Certificate",
        description="Certificate profile configuration for HTTPS ECC certificates.",
    )


class WebUICryptoCsrProfilesArgs(BaseModel):
    pass


@final
class WebUICryptoCsrProfilesResult(BaseModel):
    result: CSRProfilesModel = Field(
        default=CSRProfilesModel(),
        description="Predefined certificate profiles for common use cases.",
    )
