from middlewared.api.base import BaseModel


class SystemGeneralTimezoneChoicesArgs(BaseModel):
    pass


class SystemGeneralTimezoneChoicesResult(BaseModel):
    result: dict[str, str]
