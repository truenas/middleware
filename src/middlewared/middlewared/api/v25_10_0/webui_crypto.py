from middlewared.api.base import BaseModel

__all__ = ()


class WebUICryptoGetCertificateDomainNamesArgs(BaseModel):
    cert_id: int


class WebUICryptoGetCertificateDomainNamesResult(BaseModel):
    result: list
