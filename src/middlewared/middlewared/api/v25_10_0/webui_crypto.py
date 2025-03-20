from middlewared.api.base import BaseModel

__all__ = (
    "WebUICryptoGetCertificateDomainNamesArgs",
    "WebUICryptoGetCertificateDomainNamesResult",
)


class WebUICryptoGetCertificateDomainNamesArgs(BaseModel):
    cert_id: int


class WebUICryptoGetCertificateDomainNamesResult(BaseModel):
    result: list
