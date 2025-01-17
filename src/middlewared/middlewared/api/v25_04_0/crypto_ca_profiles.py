from typing import final

from middlewared.api.base import BaseModel

__all__ = ("CAProfilesArgs",  "CAProfilesModel", "CAProfilesResults")

# Defines the default lifetime of a certificate
# (https://support.apple.com/en-us/HT211025)
DEFAULT_LIFETIME_DAYS = 397


@final
class KeyUsageModel(BaseModel):
    enabled: bool = True
    key_cert_sign: bool = True
    crl_sign: bool = True
    extension_critical: bool = True


@final
class BasicConstraintsModel(BaseModel):
    enabled: bool = True
    ca: bool = True
    extension_critical: bool = True


@final
class ExtendedKeyUsageModel(BaseModel):
    enabled: bool = True
    extension_critical: bool = True
    usages: list[str] = ["SERVER_AUTH"]


@final
class CertExtensionsModel(BaseModel):
    KeyUsage: KeyUsageModel = KeyUsageModel()
    BasicConstraints: BasicConstraintsModel = BasicConstraintsModel()
    ExtentedKeyUsage: ExtendedKeyUsageModel = ExtendedKeyUsageModel()


@final
class CAProfilesModel(BaseModel):
    key_length: int = 2048
    key_type: str = "RSA"
    lifetime: int = DEFAULT_LIFETIME_DAYS
    digest_algorithm: str = "SHA256"
    cert_extensions: CertExtensionsModel = CertExtensionsModel()


class CAProfilesArgs(BaseModel):
    pass


class CAProfilesResults(BaseModel):
    result: CAProfilesModel = CAProfilesModel()
