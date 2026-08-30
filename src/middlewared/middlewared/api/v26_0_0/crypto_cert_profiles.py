from typing import final

from pydantic import Field

from middlewared.api.base import BaseModel

__all__ = (
    "WebUICryptoCsrProfilesArgs",
    "CSRProfilesModel",
    "WebUICryptoCsrProfilesResult",
)


RSA = "RSA"
EC = "EC"
EC_CURVE = "SECP384R1"
SHA256 = "SHA256"
KEY_LENGTH = 2048


@final
class BasicConstraintsModel(BaseModel):
    enabled: bool = Field(default=True, description="Whether the basic constraints extension is enabled.")
    ca: bool = Field(default=False, description="Whether this certificate can act as a certificate authority.")
    extension_critical: bool = Field(default=True, description="Whether this extension is marked as critical.")


@final
class ServerAuthExtendedKeyUsageModel(BaseModel):
    # clientAuth is deliberately absent: Google Trust Services answers badCSR to any request asserting it,
    # and the Chrome root programme requires server certificates issued from March 2027 to assert serverAuth
    # alone. Naming serverAuth rather than staying silent matters for a private CA that copies extensions
    # from the request, since relying parties such as Apple require this purpose to be present on a TLS
    # server certificate. A public CA sets the purpose from its own profile regardless.
    enabled: bool = Field(default=True, description="Whether the extended key usage extension is enabled.")
    extension_critical: bool = Field(default=False, description="Whether this extension is marked as critical.")
    usages: list[str] = Field(
        default_factory=lambda: ["SERVER_AUTH"],
        description="Array of extended key usage purposes for the certificate.",
    )


@final
class ClientAuthExtendedKeyUsageModel(BaseModel):
    # A certificate carrying an extended key usage is only usable for the purposes it names, so a client
    # certificate has to say so or the peer rejects it. Requesting clientAuth means no public CA will issue
    # this, since the baseline requirements make serverAuth mandatory; these profiles target a private CA.
    enabled: bool = Field(default=True, description="Whether the extended key usage extension is enabled.")
    extension_critical: bool = Field(default=False, description="Whether this extension is marked as critical.")
    usages: list[str] = Field(
        default_factory=lambda: ["CLIENT_AUTH"],
        description="Array of extended key usage purposes for the certificate.",
    )


@final
class SigningKeyUsageModel(BaseModel):
    enabled: bool = Field(default=True, description="Whether the key usage extension is enabled.")
    extension_critical: bool = Field(default=True, description="Whether this extension is marked as critical.")
    digital_signature: bool = Field(default=True, description="Whether the key can be used for digital signatures.")


@final
class ServerRSAKeyUsageModel(BaseModel):
    # keyEncipherment is only exercised by the RSA key transport cipher suites, which TLS 1.3 dropped and the
    # nginx template no longer offers. It stays for FTPS and app workloads, which can still negotiate them over
    # TLS 1.2. CA/Browser Forum TLS Baseline Requirements v2.2.9 section 7.1.2.7.11 calls asserting it alongside
    # digitalSignature NOT RECOMMENDED, which is accepted here; the same section marks keyAgreement
    # "Permitted: N" for RSA subscriber certificates, so that one is left off.
    enabled: bool = Field(default=True, description="Whether the key usage extension is enabled.")
    extension_critical: bool = Field(default=True, description="Whether this extension is marked as critical.")
    digital_signature: bool = Field(default=True, description="Whether the key can be used for digital signatures.")
    key_encipherment: bool = Field(default=True, description="Whether the key can be used for key encipherment.")


@final
class ServerRSACSRExtensionsModel(BaseModel):
    BasicConstraints: BasicConstraintsModel = Field(
        default=BasicConstraintsModel(),
        description="Basic constraints extension configuration.",
    )
    ExtendedKeyUsage: ServerAuthExtendedKeyUsageModel = Field(
        default=ServerAuthExtendedKeyUsageModel(),
        description="Extended key usage extension configuration.",
    )
    KeyUsage: ServerRSAKeyUsageModel = Field(
        default=ServerRSAKeyUsageModel(),
        description="Key usage extension configuration for RSA certificates.",
    )


@final
class ServerECCSRExtensionsModel(BaseModel):
    BasicConstraints: BasicConstraintsModel = Field(
        default=BasicConstraintsModel(),
        description="Basic constraints extension configuration.",
    )
    ExtendedKeyUsage: ServerAuthExtendedKeyUsageModel = Field(
        default=ServerAuthExtendedKeyUsageModel(),
        description="Extended key usage extension configuration.",
    )
    KeyUsage: SigningKeyUsageModel = Field(
        default=SigningKeyUsageModel(),
        description="Key usage extension configuration for EC certificates.",
    )


@final
class ClientCSRExtensionsModel(BaseModel):
    BasicConstraints: BasicConstraintsModel = Field(
        default=BasicConstraintsModel(),
        description="Basic constraints extension configuration.",
    )
    ExtendedKeyUsage: ClientAuthExtendedKeyUsageModel = Field(
        default=ClientAuthExtendedKeyUsageModel(),
        description="Extended key usage extension configuration.",
    )
    KeyUsage: SigningKeyUsageModel = Field(
        default=SigningKeyUsageModel(),
        description="Key usage extension configuration for client certificates.",
    )


@final
class TLSServerRSAProfile(BaseModel):
    cert_extensions: ServerRSACSRExtensionsModel = Field(
        default=ServerRSACSRExtensionsModel(),
        description="Certificate extensions configuration for RSA certificates.",
    )
    key_length: int = Field(default=KEY_LENGTH, description="RSA key length in bits.")
    key_type: str = Field(default=RSA, description="Type of cryptographic key (RSA).")
    digest_algorithm: str = Field(default=SHA256, description="Hash algorithm for certificate signing.")


@final
class TLSServerECProfile(BaseModel):
    cert_extensions: ServerECCSRExtensionsModel = Field(
        default=ServerECCSRExtensionsModel(),
        description="Certificate extensions configuration for EC certificates.",
    )
    ec_curve: str = Field(default=EC_CURVE, description="Elliptic curve to use for key generation.")
    key_type: str = Field(default=EC, description="Type of cryptographic key (EC).")
    digest_algorithm: str = Field(default=SHA256, description="Hash algorithm for certificate signing.")


@final
class TLSClientRSAProfile(BaseModel):
    cert_extensions: ClientCSRExtensionsModel = Field(
        default=ClientCSRExtensionsModel(),
        description="Certificate extensions configuration for RSA certificates.",
    )
    key_length: int = Field(default=KEY_LENGTH, description="RSA key length in bits.")
    key_type: str = Field(default=RSA, description="Type of cryptographic key (RSA).")
    digest_algorithm: str = Field(default=SHA256, description="Hash algorithm for certificate signing.")


@final
class TLSClientECProfile(BaseModel):
    cert_extensions: ClientCSRExtensionsModel = Field(
        default=ClientCSRExtensionsModel(),
        description="Certificate extensions configuration for EC certificates.",
    )
    ec_curve: str = Field(default=EC_CURVE, description="Elliptic curve to use for key generation.")
    key_type: str = Field(default=EC, description="Type of cryptographic key (EC).")
    digest_algorithm: str = Field(default=SHA256, description="Hash algorithm for certificate signing.")


@final
class CSRProfilesModel(BaseModel):
    # This catalogue is declared identically in v26_0_0 and v27_0_0, because v26_0_0 is the current version
    # on the stable branch and carries the to_previous conversion for earlier clients. Editing one copy alone
    # is caught by tests/api2/test_legacy_api.py::test_misc_methods rather than by anything at import time.
    tls_server_rsa: TLSServerRSAProfile = Field(
        default_factory=TLSServerRSAProfile,
        alias="TLS Server (e.g. Web UI, FTPS, Apps) - RSA",
        description=(
            "RSA certificate for services where TrueNAS accepts incoming TLS connections, such as the web UI, "
            "FTPS, and apps. Requests TLS Web Server Authentication only, which every public and ACME CA "
            "accepts."
        ),
    )
    tls_server_ec: TLSServerECProfile = Field(
        default_factory=TLSServerECProfile,
        alias="TLS Server (e.g. Web UI, FTPS, Apps) - EC",
        description=(
            "Elliptic curve certificate for services where TrueNAS accepts incoming TLS connections, such as the "
            "web UI, FTPS, and apps. Requests TLS Web Server Authentication only, which every public and ACME CA "
            "accepts."
        ),
    )
    tls_client_rsa: TLSClientRSAProfile = Field(
        default_factory=TLSClientRSAProfile,
        alias="TLS Client (e.g. Syslog, LDAP, KMIP) - RSA",
        description=(
            "RSA certificate for services where TrueNAS connects out and must authenticate itself, such as remote "
            "syslog over TLS, LDAP mutual TLS, and KMIP. Requests TLS Web Client Authentication and is intended "
            "for a private CA."
        ),
    )
    tls_client_ec: TLSClientECProfile = Field(
        default_factory=TLSClientECProfile,
        alias="TLS Client (e.g. Syslog, LDAP, KMIP) - EC",
        description=(
            "Elliptic curve certificate for services where TrueNAS connects out and must authenticate itself, such "
            "as remote syslog over TLS, LDAP mutual TLS, and KMIP. Requests TLS Web Client Authentication and is "
            "intended for a private CA."
        ),
    )

    @classmethod
    def to_previous(cls, value):
        # Older API versions declare a different set of profiles, which the adapter has already back-filled
        # from their own defaults. Our keys are aliases, so the adapter's field-name based cleanup will not
        # remove them; drop them here so the caller only sees the profiles its version knows about.
        for name, field in cls.model_fields.items():
            value.pop(field.alias or name, None)

        # Back-filled defaults arrive as model instances, and the adapter only descends into dicts and lists.
        # Left as instances they reach the next version down unconverted and fail validation against its own
        # equally named classes, so flatten them here.
        return {
            key: profile.model_dump() if isinstance(profile, BaseModel) else profile
            for key, profile in value.items()
        }


class WebUICryptoCsrProfilesArgs(BaseModel):
    pass


@final
class WebUICryptoCsrProfilesResult(BaseModel):
    result: CSRProfilesModel = Field(
        default=CSRProfilesModel(),
        description="Predefined certificate profiles for common use cases.",
    )
