from pydantic import Field

from middlewared.api.base import BaseModel


__all__ = ["SystemGeneralTimezoneChoicesArgs", "SystemGeneralTimezoneChoicesResult",]


class SystemGeneralTimezoneChoicesArgs(BaseModel):
    pass


class SystemGeneralTimezoneChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Object of available timezone identifiers and their descriptive names.")
