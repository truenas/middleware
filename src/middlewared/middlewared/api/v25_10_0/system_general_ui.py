from middlewared.api.base import BaseModel

from pydantic import Field


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
    delay: int = Field(ge=0, default=3)
    """How long to wait before the UI is restarted"""


class SystemGeneralUIRestartResult(BaseModel):
    result: None


class SystemGeneralUIV6AddressChoicesArgs(BaseModel):
    pass


class SystemGeneralUIV6AddressChoicesResult(BaseModel):
    result: dict[str, str]
