from middlewared.api.base import BaseModel

__all__ = (
    'CertificateCountryChoicesArgs',
    'CertificateCountryChoicesResult',
    'CertificateAcmeServerChoicesArgs',
    'CertificateAcmeServerChoicesResult',
    'CertificateEcCurveChoicesArgs',
    'CertificateEcCurveChoicesResult',
    'CertificateExtendedKeyUsageChoicesArgs',
    'CertificateExtendedKeyUsageChoicesResult',
)


class CertificateCountryChoicesArgs(BaseModel):
    pass


class CertificateCountryChoicesResult(BaseModel):
    result: dict[str, str]
    """Object mapping country codes to country names for certificate creation."""


class CertificateAcmeServerChoicesArgs(BaseModel):
    pass


class CertificateAcmeServerChoicesResult(BaseModel):
    result: dict[str, str]
    """Object mapping ACME server identifiers to their directory URLs."""


class CertificateEcCurveChoicesArgs(BaseModel):
    pass


class CertificateEcCurveChoicesResult(BaseModel):
    result: dict[str, str]
    """Object mapping elliptic curve identifiers."""


class CertificateExtendedKeyUsageChoicesArgs(BaseModel):
    pass


class CertificateExtendedKeyUsageChoicesResult(BaseModel):
    result: dict[str, str]
    """Object mapping extended key usage OIDs."""
