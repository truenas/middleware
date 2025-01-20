from middlewared.api.base import BaseModel

__all__ = (
    'CertifiateCountryChoicesArgs',
    'CertifiateCountryChoicesResult',
    'CertificateAcmeServerChoicesArgs',
    'CertificateAcmeServerChoicesResult',
    'CertificateECCurveChoicesArgs',
    'CertificateECCurveChoicesResult',
    'CertificateExtendedKeyUsageChoicesArgs',
    'CertificateExtendedKeyUsageChoicesResult',
)


class CertifiateCountryChoicesArgs(BaseModel):
    pass


class CertifiateCountryChoicesResult(BaseModel):
    result: dict[str, str]


class CertificateAcmeServerChoicesArgs(BaseModel):
    pass


class CertificateAcmeServerChoicesResult(BaseModel):
    result: dict[str, str]


class CertificateECCurveChoicesArgs(BaseModel):
    pass


class CertificateECCurveChoicesResult(BaseModel):
    result: dict[str, str]


class CertificateExtendedKeyUsageChoicesArgs(BaseModel):
    pass


class CertificateExtendedKeyUsageChoicesResult(BaseModel):
    result: dict[str, str]
