from middlewared.api.base import BaseModel

__all__ = (
    "WebUICryptoGetCertificateDomainNamesArgs",
    "WebUICryptoGetCertificateDomainNamesResult",
)


class WebUICryptoGetCertificateDomainNamesArgs(BaseModel):
    cert_id: int
    """ID of the certificate to extract domain names from."""


class WebUICryptoGetCertificateDomainNamesResult(BaseModel):
    result: list
    """Array of domain names found in the certificate (CN and SAN entries)."""
