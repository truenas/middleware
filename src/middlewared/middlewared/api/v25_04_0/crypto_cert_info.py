from middlewared.api.base import BaseModel

__all__ = (
    'SystemGeneralCountryChoicesArgs',
    'SystemGeneralCountryChoicesResult',
    'CertificateAcmeServerChoicesArgs',
    'CertificateAcmeServerChoicesResult',
    'CertificateEcCurveChoicesArgs',
    'CertificateEcCurveChoicesResult',
    'CertificateExtendedKeyUsageChoicesArgs',
    'CertificateExtendedKeyUsageChoicesResult',
)


class SystemGeneralCountryChoicesArgs(BaseModel):
    pass


class SystemGeneralCountryChoicesResult(BaseModel):
    result: dict[str, str]


class CertificateAcmeServerChoicesArgs(BaseModel):
    pass


class CertificateAcmeServerChoicesResult(BaseModel):
    result: dict[str, str]


class CertificateEcCurveChoicesArgs(BaseModel):
    pass


class CertificateEcCurveChoicesResult(BaseModel):
    result: dict[str, str]


class CertificateExtendedKeyUsageChoicesArgs(BaseModel):
    pass


class CertificateExtendedKeyUsageChoicesResult(BaseModel):
    result: dict[str, str]
