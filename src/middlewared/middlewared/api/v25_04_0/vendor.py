from middlewared.api.base import BaseModel


class VendorNameArgs(BaseModel):
    pass


class VendorNameResult(BaseModel):
    result: str | None


class UnvendorArgs(BaseModel):
    pass


class UnvendorResult(BaseModel):
    result: None


class IsVendoredArgs(BaseModel):
    pass


class IsVendoredResult(BaseModel):
    result: None
