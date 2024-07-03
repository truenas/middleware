from middlewared.api.base import BaseModel


class VendorNameResult(BaseModel):
    result: str | None
