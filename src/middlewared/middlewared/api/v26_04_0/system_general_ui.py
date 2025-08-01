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
    """Object of available IPv4 addresses and their interface names for UI binding."""


class SystemGeneralUiCertificateChoicesArgs(BaseModel):
    pass


class SystemGeneralUiCertificateChoicesResult(BaseModel):
    result: dict[int, str]
    """Object of available certificate IDs and their names for UI HTTPS."""


class SystemGeneralUiHttpsprotocolsChoicesArgs(BaseModel):
    pass


class SystemGeneralUiHttpsprotocolsChoicesResult(BaseModel):
    result: dict[str, str]
    """Object of available HTTPS protocol versions and their descriptions."""


class SystemGeneralLocalUrlArgs(BaseModel):
    pass


class SystemGeneralLocalUrlResult(BaseModel):
    result: str
    """The local URL for accessing the web UI."""


class SystemGeneralUiRestartArgs(BaseModel):
    delay: NonNegativeInt = 3
    """How long to wait before the UI is restarted."""


class SystemGeneralUiRestartResult(BaseModel):
    result: None
    """Returns `null` on successful UI restart initiation."""


class SystemGeneralUiV6addressChoicesArgs(BaseModel):
    pass


class SystemGeneralUiV6addressChoicesResult(BaseModel):
    result: dict[str, str]
    """Object of available IPv6 addresses and their interface names for UI binding."""
