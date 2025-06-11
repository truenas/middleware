from middlewared.api.base import BaseModel

from pydantic import NonNegativeInt


__all__ = [
    "SystemGeneralUiAddressChoicesArgs", "SystemGeneralUiAddressChoicesResult",
    "SystemGeneralUiCertificateChoicesArgs", "SystemGeneralUiCertificateChoicesResult",
    "SystemGeneralUiHttpsprotocolsChoicesArgs", "SystemGeneralUiHttpsprotocolsChoicesResult",
    "SystemGeneralLocalUrlArgs", "SystemGeneralLocalUrlResult", "SystemGeneralUiRestartArgs",
    "SystemGeneralUiRestartResult", "SystemGeneralUiV6addressChoicesArgs", "SystemGeneralUiV6addressChoicesResult",
]


class SystemGeneralUiAddressChoicesArgs(BaseModel):
    pass


class SystemGeneralUiAddressChoicesResult(BaseModel):
    result: dict[str, str]


class SystemGeneralUiCertificateChoicesArgs(BaseModel):
    pass


class SystemGeneralUiCertificateChoicesResult(BaseModel):
    result: dict[int, str]


class SystemGeneralUiHttpsprotocolsChoicesArgs(BaseModel):
    pass


class SystemGeneralUiHttpsprotocolsChoicesResult(BaseModel):
    result: dict[str, str]


class SystemGeneralLocalUrlArgs(BaseModel):
    pass


class SystemGeneralLocalUrlResult(BaseModel):
    result: str


class SystemGeneralUiRestartArgs(BaseModel):
    delay: NonNegativeInt = 3
    """How long to wait before the UI is restarted"""


class SystemGeneralUiRestartResult(BaseModel):
    result: None


class SystemGeneralUiV6addressChoicesArgs(BaseModel):
    pass


class SystemGeneralUiV6addressChoicesResult(BaseModel):
    result: dict[str, str]
