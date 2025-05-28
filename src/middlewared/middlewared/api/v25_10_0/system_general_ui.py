from middlewared.api.base import BaseModel

from pydantic import NonNegativeInt


__all__ = [
    "SystemGeneralUIAddressChoicesArgs", "SystemGeneralUIAddressChoicesResult",
    "SystemGeneralUICertificateChoicesArgs", "SystemGeneralUICertificateChoicesResult",
    "SystemGeneralUIHTTPSProtocolChoicesArgs", "SystemGeneralUIHTTPSProtocolChoicesResult",
    "SystemGeneralUILocalURLArgs", "SystemGeneralUILocalURLResult", "SystemGeneralUIRestartArgs",
    "SystemGeneralUIRestartResult", "SystemGeneralUIV6AddressChoicesArgs", "SystemGeneralUIV6AddressChoicesResult",
]


class SystemGeneralUIAddressChoicesArgs(BaseModel):
    pass


class SystemGeneralUIAddressChoicesResult(BaseModel):
    result: dict[str, str]


class SystemGeneralUICertificateChoicesArgs(BaseModel):
    pass


class SystemGeneralUICertificateChoicesResult(BaseModel):
    result: dict[int, str]


class SystemGeneralUIHTTPSProtocolChoicesArgs(BaseModel):
    pass


class SystemGeneralUIHTTPSProtocolChoicesResult(BaseModel):
    result: dict[str, str]


class SystemGeneralUILocalURLArgs(BaseModel):
    pass


class SystemGeneralUILocalURLResult(BaseModel):
    result: str


class SystemGeneralUIRestartArgs(BaseModel):
    delay: NonNegativeInt = 3
    """How long to wait before the UI is restarted."""


class SystemGeneralUIRestartResult(BaseModel):
    result: None


class SystemGeneralUIV6AddressChoicesArgs(BaseModel):
    pass


class SystemGeneralUIV6AddressChoicesResult(BaseModel):
    result: dict[str, str]
