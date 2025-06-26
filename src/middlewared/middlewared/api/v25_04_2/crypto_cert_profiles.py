from typing import final

from middlewared.api.base import BaseModel

from pydantic import Field

__all__ = (
    "CertProfilesArgs",
    "CertProfilesModel",
    "CertProfilesResult",
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
    ca: bool = False
    extension_critical: bool = True


@final
class AuthorityKeyIdentifierModel(BaseModel):
    enabled: bool = True
    authority_cert_issuer: bool = True
    extension_critical: bool = False


@final
class ExtendedKeyUsageModel(BaseModel):
    # These days, most TLS certs want "ClientAuth".
    # LetsEncrypt appears to want this extension to issue.
    # https://community.letsencrypt.org/t/extendedkeyusage-tls-client-
    # authentication-in-tls-server-certificates/59140/7
    enabled: bool = True
    extension_critical: bool = True
    usages: list[str] = EX_KEY_USAGE


@final
class RSAKeyUsageModel(BaseModel):
    # RSA certs need "digitalSignature" for DHE,
    # and "keyEncipherment" for nonDHE
    # Include "keyAgreement" for compatibility (DH_DSS / DH_RSA)
    # See rfc5246
    enabled: bool = True
    extension_critical: bool = True
    digital_signature: bool = True
    key_encipherment: bool = True
    key_agreement: bool = True


@final
class ECCKeyUsageModel(BaseModel):
    # keyAgreement is not generally required for EC certs.
    # See Google, cloudflare certs
    enabled: bool = True
    extension_critical: bool = True
    digital_signature: bool = True


@final
class RSACertExtensionsModel(BaseModel):
    BasicConstraints: BasicConstraintsModel = BasicConstraintsModel()
    AuthorityKeyIdentifier: AuthorityKeyIdentifierModel = AuthorityKeyIdentifierModel()
    ExtendedKeyUsage: ExtendedKeyUsageModel = ExtendedKeyUsageModel()
    KeyUsage: RSAKeyUsageModel = RSAKeyUsageModel()


@final
class ECCCertExtensionsModel(BaseModel):
    BasicConstraints: BasicConstraintsModel = BasicConstraintsModel()
    AuthorityKeyIdentifier: AuthorityKeyIdentifierModel = AuthorityKeyIdentifierModel()
    ExtendedKeyUsage: ExtendedKeyUsageModel = ExtendedKeyUsageModel()
    KeyUsage: ECCKeyUsageModel = ECCKeyUsageModel()


@final
class RSACertExtensions(BaseModel):
    cert_extensions: RSACertExtensionsModel = RSACertExtensionsModel()
    key_length: int = KEY_LENGTH
    key_type: str = RSA
    lifetime: int = DEFAULT_LIFETIME_DAYS
    digest_algorithm: str = SHA256


@final
class ECCCertExtensions(BaseModel):
    cert_extensions: ECCCertExtensionsModel = ECCCertExtensionsModel()
    ec_curve: str = EC_CURVE
    key_type: str = EC
    lifetime: int = DEFAULT_LIFETIME_DAYS
    digest_algorithm: str = SHA256


@final
class CertProfilesModel(BaseModel):
    https_rsa_certificate: RSACertExtensions = Field(
        default_factory=RSACertExtensions, alias="HTTPS RSA Certificate"
    )
    https_ecc_certificate: ECCCertExtensions = Field(
        default_factory=ECCCertExtensions, alias="HTTPS ECC Certificate"
    )


class CertProfilesArgs(BaseModel):
    pass


@final
class CertProfilesResult(BaseModel):
    result: CertProfilesModel = CertProfilesModel()


@final
class RSACSRExtensionsModel(BaseModel):
    BasicConstraints: BasicConstraintsModel = BasicConstraintsModel()
    ExtendedKeyUsage: ExtendedKeyUsageModel = ExtendedKeyUsageModel()
    KeyUsage: RSAKeyUsageModel = RSAKeyUsageModel()


@final
class ECCCSRExtensionsModel(BaseModel):
    BasicConstraints: BasicConstraintsModel = BasicConstraintsModel()
    ExtendedKeyUsage: ExtendedKeyUsageModel = ExtendedKeyUsageModel()
    KeyUsage: ECCKeyUsageModel = ECCKeyUsageModel()


@final
class RSACSRExtensions(BaseModel):
    cert_extensions: RSACSRExtensionsModel = RSACSRExtensionsModel()
    key_length: int = KEY_LENGTH
    key_type: str = RSA
    lifetime: int = DEFAULT_LIFETIME_DAYS
    digest_algorithm: str = SHA256


@final
class ECCCSRExtensions(BaseModel):
    cert_extensions: ECCCSRExtensionsModel = ECCCSRExtensionsModel()
    ec_curve: str = EC_CURVE
    key_type: str = EC
    lifetime: int = DEFAULT_LIFETIME_DAYS
    digest_algorithm: str = SHA256


@final
class CSRProfilesModel(BaseModel):
    https_rsa_certificate: RSACSRExtensions = Field(
        default_factory=RSACSRExtensions, alias="HTTPS RSA Certificate"
    )
    https_ecc_certificate: ECCCSRExtensions = Field(
        default_factory=ECCCSRExtensions, alias="HTTPS ECC Certificate"
    )


class WebUICryptoCsrProfilesArgs(BaseModel):
    pass


@final
class WebUICryptoCsrProfilesResult(BaseModel):
    result: CSRProfilesModel = CSRProfilesModel()
